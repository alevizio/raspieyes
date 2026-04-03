#!/bin/bash
# raspieyes-init.sh — One-time auto-setup script
# Runs via systemd.run on first boot after being placed on the boot partition.
# Copies project files, installs mpv, configures autostart, then cleans up.

set -euo pipefail

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
echo "[1/4] Copying project files..."
mkdir -p "$DEST_DIR"
cp -a "$SRC_DIR/." "$DEST_DIR/"
chmod +x "$DEST_DIR/play.sh" "$DEST_DIR/setup.sh" "$DEST_DIR/raspieyes-init.sh" 2>/dev/null || true
chown -R "$MAIN_USER:$MAIN_USER" "$DEST_DIR"
echo "  Files copied to $DEST_DIR"

# 2. Enable SSH
echo "[2/4] Enabling SSH..."
systemctl enable ssh 2>/dev/null || true
systemctl start ssh 2>/dev/null || true

# 3. Clean up: remove systemd.run from cmdline.txt so this only runs once
echo "[3/4] Cleaning up cmdline.txt..."
if [ -f "$BOOT_DIR/cmdline.txt" ]; then
    sed -i 's| systemd.run=[^ ]* systemd.run_success_trigger=[^ ]*||g' "$BOOT_DIR/cmdline.txt"
fi

# 4. Run the full setup now that the project is in place
echo "[4/4] Running full setup..."
RASPIEYES_USER="$MAIN_USER" RASPIEYES_HOME="$MAIN_HOME" bash "$DEST_DIR/setup.sh"
