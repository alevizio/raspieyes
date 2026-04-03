#!/usr/bin/env bash
set -uo pipefail

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
TRACKING=no
IDLE_VIDEOS=all
DETECTED_VIDEOS=all
STATE_FILE="/tmp/raspieyes_state"
RENDER_MODE=video
EYE_COLOR=blue
DETECTION_MODE=motion

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

# --- Parallax render mode ---
if [[ "${RENDER_MODE:-video}" == "parallax" ]]; then
    echo "Render mode: parallax (real-time eye renderer)"

    # Build renderer args from config
    RENDERER_ARGS=(
        --eye-color "${EYE_COLOR:-blue}"
        --state-file "$STATE_FILE"
    )
    [[ -n "${SCLERA_PARALLAX:-}" ]] && RENDERER_ARGS+=(--sclera-parallax "$SCLERA_PARALLAX")
    [[ -n "${IRIS_PARALLAX:-}" ]] && RENDERER_ARGS+=(--iris-parallax "$IRIS_PARALLAX")
    [[ -n "${PUPIL_PARALLAX:-}" ]] && RENDERER_ARGS+=(--pupil-parallax "$PUPIL_PARALLAX")
    [[ -n "${MAX_OFFSET:-}" ]] && RENDERER_ARGS+=(--max-offset "$MAX_OFFSET")
    [[ -n "${LERP_SPEED:-}" ]] && RENDERER_ARGS+=(--lerp-speed "$LERP_SPEED")
    [[ -n "${PRESENCE_TIMEOUT:-}" ]] && RENDERER_ARGS+=(--presence-timeout "$PRESENCE_TIMEOUT")
    RENDERER_ARGS+=(--detection-mode "${DETECTION_MODE:-motion}")
    [[ -n "${MIN_CONTOUR_AREA:-}" ]] && RENDERER_ARGS+=(--min-contour-area "$MIN_CONTOUR_AREA")
    [[ "${TRACKING:-no}" != "yes" ]] && RENDERER_ARGS+=(--no-camera)
    [[ "${USB_WEBCAM:-no}" == "yes" ]] && RENDERER_ARGS+=(--test-webcam)

    # Mirror both screens at same position so one renderer drives both
    if command -v wlr-randr &>/dev/null; then
        wlr-randr --output HDMI-A-1 --pos 0,0 --output HDMI-A-2 --pos 0,0 2>/dev/null
        sleep 1  # let compositor settle
    fi

    RENDERER_ARGS+=(--single-eye)

    RENDERER_PID=""
    cleanup_renderer() {
        [[ -n "$RENDERER_PID" ]] && kill "$RENDERER_PID" 2>/dev/null
        wait 2>/dev/null
    }
    trap cleanup_renderer EXIT

    # Launch renderer
    python3 "$SCRIPT_DIR/eye_renderer.py" "${RENDERER_ARGS[@]}" &
    RENDERER_PID=$!
    echo "  Renderer PID: $RENDERER_PID"

    # Simple watchdog: restart if renderer crashes
    while true; do
        if ! kill -0 "$RENDERER_PID" 2>/dev/null; then
            echo "Renderer exited at $(date), restarting..."
            sleep 2
            python3 "$SCRIPT_DIR/eye_renderer.py" "${RENDERER_ARGS[@]}" &
            RENDERER_PID=$!
            echo "  Renderer PID: $RENDERER_PID"
        fi
        sleep 3
    done
    # Never reaches here — the while loop above runs until the script is killed
fi

# --- Video mode (original) ---

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

# --- Tracking: build separate idle/detected playlists ---
IDLE_PLAYLIST=()
DETECTED_PLAYLIST=()
CURRENT_STATE="idle"

if [[ "$TRACKING" == "yes" ]]; then
    echo "Eye tracking enabled"

    # Helper: filter videos by comma-separated basename list (or "all")
    filter_videos() {
        local spec="$1"
        local -a result=()
        if [[ "$spec" == "all" ]]; then
            result=("${VIDEO_FILES[@]}")
        else
            IFS=',' read -ra names <<< "$spec"
            for name in "${names[@]}"; do
                name="$(echo "$name" | xargs)"  # trim whitespace
                for v in "${VIDEO_FILES[@]}"; do
                    if [[ "$(basename "$v")" == "$name" ]]; then
                        result+=("$v")
                        break
                    fi
                done
            done
        fi
        printf '%s\n' "${result[@]}"
    }

    # Build idle playlist
    while IFS= read -r v; do
        [[ -z "$v" ]] && continue
        for ((r=0; r<REPEAT; r++)); do IDLE_PLAYLIST+=("$v"); done
    done < <(filter_videos "$IDLE_VIDEOS")

    # Build detected playlist
    while IFS= read -r v; do
        [[ -z "$v" ]] && continue
        for ((r=0; r<REPEAT; r++)); do DETECTED_PLAYLIST+=("$v"); done
    done < <(filter_videos "$DETECTED_VIDEOS")

    echo "  Idle playlist: ${#IDLE_PLAYLIST[@]} entries"
    echo "  Detected playlist: ${#DETECTED_PLAYLIST[@]} entries"

    # Start with idle playlist
    PLAYLIST=("${IDLE_PLAYLIST[@]}")
fi

# IPC sockets for playlist switching without restart
MPV_SOCKETS=()

# Common mpv flags
MPV_BASE=(
    --fs
    --no-terminal
    --no-input-default-bindings
    --no-osc
    --no-osd-bar
    --force-window=yes
    --idle=yes
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
TRACKER_PID=""
cleanup_all() {
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null
    done
    [[ -n "$TRACKER_PID" ]] && kill "$TRACKER_PID" 2>/dev/null
    wait 2>/dev/null
    PIDS=()
}
trap cleanup_all EXIT

# Alias for internal use (keeps existing call sites working)
kill_all_mpv() {
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null
        wait "$pid" 2>/dev/null
    done
    PIDS=()
}

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
    MPV_SOCKETS=()

    if [[ $count -eq 1 ]]; then
        local sock="/tmp/mpv-sock-0"
        mpv "${MPV_BASE[@]}" --input-ipc-server="$sock" "${PLAYLIST[@]}" &
        PIDS+=($!)
        MPV_SOCKETS+=("$sock")
    else
        for i in "${!screens[@]}"; do
            local sock="/tmp/mpv-sock-$i"
            mpv "${MPV_BASE[@]}" --input-ipc-server="$sock" --fs-screen="$i" "${PLAYLIST[@]}" &
            PIDS+=($!)
            MPV_SOCKETS+=("$sock")
        done
    fi
    echo "  Launched ${#PIDS[@]} mpv instance(s)"
    return 0
}

# Switch playlist via IPC without restarting mpv (no black screen)
switch_playlist_ipc() {
    local -a new_playlist=("${PLAYLIST[@]}")

    if ! command -v socat &>/dev/null; then
        echo "  socat not installed, falling back to mpv restart"
        return 1
    fi

    for sock in "${MPV_SOCKETS[@]}"; do
        if [[ ! -S "$sock" ]]; then
            echo "  IPC socket $sock missing, falling back to restart"
            return 1
        fi

        # Load first video with "replace" — immediately starts playing it
        echo "{ \"command\": [\"loadfile\", \"${new_playlist[0]}\", \"replace\"] }" | socat - "$sock" 2>/dev/null

        # Append the rest
        for ((i=1; i<${#new_playlist[@]}; i++)); do
            echo "{ \"command\": [\"loadfile\", \"${new_playlist[$i]}\", \"append\"] }" | socat - "$sock" 2>/dev/null
        done
    done
    echo "  Switched playlist via IPC (${#new_playlist[@]} entries)"
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

# --- Launch eye tracker if enabled ---
if [[ "$TRACKING" == "yes" ]]; then
    if command -v python3 &>/dev/null && [[ -f "$SCRIPT_DIR/eye_tracker.py" ]]; then
        echo "Starting eye tracker..."
        python3 "$SCRIPT_DIR/eye_tracker.py" --state-file "$STATE_FILE" &
        TRACKER_PID=$!
        echo "  Tracker PID: $TRACKER_PID"
    else
        echo "WARNING: TRACKING=yes but eye_tracker.py or python3 not found, disabling"
        TRACKING=no
    fi
fi

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

    # --- Check eye tracker state ---
    if [[ "$TRACKING" == "yes" ]] && [[ -f "$STATE_FILE" ]]; then
        NEW_STATE=$(cat "$STATE_FILE" 2>/dev/null || echo "idle")
        if [[ "$NEW_STATE" != "$CURRENT_STATE" ]]; then
            echo "State change: $CURRENT_STATE -> $NEW_STATE at $(date)"
            CURRENT_STATE="$NEW_STATE"
            if [[ "$CURRENT_STATE" == "detected" ]]; then
                PLAYLIST=("${DETECTED_PLAYLIST[@]}")
            else
                PLAYLIST=("${IDLE_PLAYLIST[@]}")
            fi
            # Try seamless IPC switch first, fall back to restart
            if ! switch_playlist_ipc 2>/dev/null; then
                echo "  IPC failed, restarting mpv..."
                kill_all_mpv
                sleep 1
                LAST_SCREENS="$(detect_screens)"
                launch_mpv || echo "  WARNING: launch_mpv failed"
            fi
        fi
    fi

    # Check every 3 seconds
    sleep 3
done
