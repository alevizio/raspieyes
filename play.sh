#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.txt"
VIDEOS_DIR="$SCRIPT_DIR/videos"
LOG_FILE="$SCRIPT_DIR/raspieyes.log"

# Log everything for debugging
exec > >(tee -a "$LOG_FILE") 2>&1
echo ""
echo "=== raspieyes starting at $(date) ==="

# Defaults
SHUFFLE=no
REPEAT=3
PAUSE=2

# Source config if it exists
if [[ -f "$CONFIG_FILE" ]]; then
    source "$CONFIG_FILE"
fi

# --- Ensure display environment is set ---
# Auto-detect XDG_RUNTIME_DIR
if [[ -z "${XDG_RUNTIME_DIR:-}" ]]; then
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
    echo "Set XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR"
fi

# Auto-detect Wayland display
if [[ -z "${WAYLAND_DISPLAY:-}" ]]; then
    for wl in wayland-1 wayland-0; do
        if [[ -S "$XDG_RUNTIME_DIR/$wl" ]]; then
            export WAYLAND_DISPLAY="$wl"
            echo "Detected WAYLAND_DISPLAY=$wl"
            break
        fi
    done
fi

# Set DISPLAY for XWayland fallback
if [[ -z "${DISPLAY:-}" ]]; then
    export DISPLAY=:0
    echo "Set DISPLAY=:0"
fi

echo "Environment: WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-unset} DISPLAY=${DISPLAY:-unset} XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-unset}"

# Build list of video files
VIDEO_FILES=()
if [[ -d "$VIDEOS_DIR" ]]; then
    while IFS= read -r -d '' f; do
        VIDEO_FILES+=("$f")
    done < <(find "$VIDEOS_DIR" -maxdepth 1 -type f \( -name '*.mp4' -o -name '*.gif' -o -name '*.webm' -o -name '*.mkv' -o -name '*.avi' \) -print0 | sort -z)
fi

if [[ ${#VIDEO_FILES[@]} -eq 0 ]]; then
    echo "ERROR: No video files found in $VIDEOS_DIR" >&2
    echo "  Add videos: scp video.mp4 pi@$(hostname).local:~/raspieyes/videos/" >&2
    exit 1
fi

echo "raspieyes: found ${#VIDEO_FILES[@]} video(s) from $VIDEOS_DIR"
for v in "${VIDEO_FILES[@]}"; do echo "  - $(basename "$v")"; done

# Build playlist: each video repeated REPEAT times, then next video
PLAYLIST=()
for v in "${VIDEO_FILES[@]}"; do
    for ((r=0; r<REPEAT; r++)); do
        PLAYLIST+=("$v")
    done
done
echo "Playlist: ${#PLAYLIST[@]} entries (each video x${REPEAT})"

# Common mpv flags
MPV_BASE=(
    --fs
    --no-terminal
    --no-input-default-bindings
    --no-osc
    --no-osd-bar
    --force-window=yes
    --idle=no
    --background-color='#000000'
    --vo=gpu
    --gpu-api=opengl
    --hwdec=no
    --loop-playlist=inf
)

if ! command -v mpv &>/dev/null; then
    echo "ERROR: mpv not found. Run: sudo apt install mpv" >&2
    exit 1
fi

# --- Functions ---

# Detect currently connected screens
detect_screens() {
    local screens=()
    if command -v wlr-randr &>/dev/null; then
        while IFS= read -r name; do
            screens+=("$name")
        done < <(wlr-randr | grep -oP '^[A-Z]+-[A-Z]+-\d+(?= )')
    fi
    echo "${screens[@]:-}"
}

# Kill all running mpv child processes
PIDS=()
kill_all_mpv() {
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null
    done
    wait 2>/dev/null
    PIDS=()
}
trap kill_all_mpv EXIT

# Launch mpv on all detected screens
launch_mpv() {
    local -a screens
    read -ra screens <<< "$(detect_screens)"
    local count=${#screens[@]}

    if [[ $count -eq 0 ]]; then
        echo "  No screens detected"
        return 1
    fi

    echo "  Detected $count screen(s): ${screens[*]}"

    if [[ $count -eq 1 ]]; then
        mpv "${MPV_BASE[@]}" "${PLAYLIST[@]}" &
        PIDS+=($!)
    else
        for i in "${!screens[@]}"; do
            mpv "${MPV_BASE[@]}" --fs-screen="$i" "${PLAYLIST[@]}" &
            PIDS+=($!)
        done
    fi
    echo "  Launched ${#PIDS[@]} mpv instance(s)"
    return 0
}

# Check if all mpv processes are still alive
all_mpv_alive() {
    for pid in "${PIDS[@]}"; do
        if ! kill -0 "$pid" 2>/dev/null; then
            return 1
        fi
    done
    return 0
}

# --- Main watchdog loop ---
# Re-detects screens and restarts mpv on any change or crash.
# Handles: monitor unplug, replug, mpv crash, etc.

echo "Looping ${#VIDEO_FILES[@]} video(s) as playlist"
LAST_SCREENS=""

while true; do
    CURRENT_SCREENS="$(detect_screens)"

    # Restart mpv if: no mpv running, mpv crashed, or screens changed
    if [[ ${#PIDS[@]} -eq 0 ]] || ! all_mpv_alive || [[ "$CURRENT_SCREENS" != "$LAST_SCREENS" ]]; then
        if [[ ${#PIDS[@]} -gt 0 ]]; then
            if [[ "$CURRENT_SCREENS" != "$LAST_SCREENS" ]]; then
                echo "Screen change detected at $(date): was '$LAST_SCREENS' → now '$CURRENT_SCREENS'"
            else
                echo "An mpv instance exited at $(date), restarting..."
            fi
            kill_all_mpv
            sleep 1
        fi

        LAST_SCREENS="$CURRENT_SCREENS"

        if [[ -n "$CURRENT_SCREENS" ]]; then
            echo "Starting playback at $(date)..."
            launch_mpv || true
        else
            echo "Waiting for screens to connect..."
        fi
    fi

    # Check every 3 seconds
    sleep 3
done
