#!/bin/bash
# raspieyes-init.sh — One-time auto-setup script
# Runs via systemd.run on first boot after being placed on the boot partition.
# Copies project files, installs mpv, configures autostart, then cleans up.

set -e

BOOT_DIR="/boot/firmware"
SRC_DIR="$BOOT_DIR/raspieyes"
LOG="$BOOT_DIR/raspieyes-init.log"

exec > "$LOG" 2>&1
echo "=== raspieyes init starting at $(date) ==="

# Find the main user (UID 1000)
MAIN_USER=$(id -nu 1000 2>/dev/null || echo "")
if [ -z "$MAIN_USER" ]; then
    echo "ERROR: No user with UID 1000 found"
    exit 1
fi
MAIN_HOME=$(eval echo "~$MAIN_USER")
echo "Main user: $MAIN_USER (home: $MAIN_HOME)"

DEST_DIR="$MAIN_HOME/raspieyes"

# 1. Copy project files to user's home
echo "[1/4] Copying files..."
mkdir -p "$DEST_DIR"
cp "$SRC_DIR/eye.mp4" "$DEST_DIR/"
cp "$SRC_DIR/play.sh" "$DEST_DIR/"
cp "$SRC_DIR/config.txt" "$DEST_DIR/"
cp "$SRC_DIR/setup.sh" "$DEST_DIR/"
cp "$SRC_DIR/raspieyes.service" "$DEST_DIR/"
cp "$SRC_DIR/README.md" "$DEST_DIR/"
chmod +x "$DEST_DIR/play.sh"
chown -R "$MAIN_USER:$MAIN_USER" "$DEST_DIR"
echo "  Files copied to $DEST_DIR"

# 2. Install mpv (if network available)
echo "[2/4] Installing mpv..."
if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y mpv || echo "  mpv install failed, will use vlc"
else
    echo "  No network, skipping mpv install (will use vlc if available)"
fi

# 3. Enable SSH
echo "[3/4] Enabling SSH..."
systemctl enable ssh 2>/dev/null || true
systemctl start ssh 2>/dev/null || true

# 4. Configure labwc autostart for the user
echo "[4/4] Setting up auto-start..."
LABWC_DIR="$MAIN_HOME/.config/labwc"
AUTOSTART_FILE="$LABWC_DIR/autostart"
mkdir -p "$LABWC_DIR"

if ! grep -q "raspieyes" "$AUTOSTART_FILE" 2>/dev/null; then
    cat >> "$AUTOSTART_FILE" <<AUTOSTARTEOF

# raspieyes: auto-start video display
sleep 3
$DEST_DIR/play.sh &
AUTOSTARTEOF
fi
chown -R "$MAIN_USER:$MAIN_USER" "$LABWC_DIR"
echo "  Autostart configured"

# 5. Clean up: remove systemd.run from cmdline.txt so this only runs once
echo "Cleaning up cmdline.txt..."
if [ -f "$BOOT_DIR/cmdline.txt" ]; then
    sed -i 's| systemd.run=[^ ]* systemd.run_success_trigger=[^ ]*||g' "$BOOT_DIR/cmdline.txt"
fi

echo "=== raspieyes init complete at $(date) ==="
echo "Reboot to start playing the video."
