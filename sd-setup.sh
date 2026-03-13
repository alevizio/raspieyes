#!/usr/bin/env bash
# sd-setup.sh — Write raspieyes directly to the Pi's SD card ext4 partition
# Run this on your Mac with: sudo bash sd-setup.sh
set -euo pipefail

DEBUGFS=/opt/homebrew/opt/e2fsprogs/sbin/debugfs
DISK=/dev/disk5s2
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PI_USER="pi"
PI_HOME="/home/$PI_USER"

echo "=== raspieyes SD card setup ==="
echo "Writing to $DISK (Pi user: $PI_USER)"

# Test read access
echo "Testing read access..."
if ! $DEBUGFS -R "ls $PI_HOME" "$DISK" 2>/dev/null | grep -q "."; then
    echo "ERROR: Cannot read $DISK or $PI_HOME doesn't exist"
    exit 1
fi
echo "  OK"

# Step 1: Disable first-boot wizard so Pi boots straight to desktop
echo "[1/7] Disabling first-boot wizard..."
# The wizard is launched by /etc/xdg/autostart/piwiz.desktop
# We disable it by writing Hidden=true into it
TMPWIZ=$(mktemp)
$DEBUGFS -R "cat /etc/xdg/autostart/piwiz.desktop" "$DISK" 2>/dev/null > "$TMPWIZ" || true
if [ -s "$TMPWIZ" ]; then
    # Append Hidden=true to disable the wizard
    echo "Hidden=true" >> "$TMPWIZ"
    $DEBUGFS -w -R "write $TMPWIZ /etc/xdg/autostart/piwiz.desktop" "$DISK" 2>/dev/null
    echo "  Wizard disabled"
else
    echo "  piwiz.desktop not found, skipping"
fi
rm "$TMPWIZ"

# Step 2: Set password for pi user so SSH works
echo "[2/7] Setting password for pi user..."
# Generate password hash for 'raspberry' (the classic default)
PASS_HASH=$(openssl passwd -6 'raspberry')
# Read current shadow file, update pi's password, write back
TMPSHADOW=$(mktemp)
$DEBUGFS -R "cat /etc/shadow" "$DISK" 2>/dev/null > "$TMPSHADOW"
if grep -q "^pi:" "$TMPSHADOW"; then
    sed -i '' "s|^pi:[^:]*:|pi:${PASS_HASH}:|" "$TMPSHADOW"
    $DEBUGFS -w -R "write $TMPSHADOW /etc/shadow" "$DISK" 2>/dev/null
    echo "  Password set (user: pi, password: raspberry)"
else
    echo "  WARNING: pi user not found in /etc/shadow"
fi
rm "$TMPSHADOW"

# Step 3: Create raspieyes directory and copy files
echo "[3/7] Creating directories..."
$DEBUGFS -w -R "mkdir $PI_HOME/raspieyes" "$DISK" 2>/dev/null || true

echo "[4/7] Copying project files..."
for f in eye.mp4 play.sh config.txt setup.sh raspieyes.service README.md; do
    echo "  $f"
    $DEBUGFS -w -R "write $PROJECT_DIR/$f $PI_HOME/raspieyes/$f" "$DISK" 2>/dev/null
done

# Step 5: Set up XDG autostart (same mechanism the Pi wizard uses — proven to work)
echo "[5/7] Setting up XDG autostart..."
TMPAUTO=$(mktemp)
cat > "$TMPAUTO" <<EOF
[Desktop Entry]
Type=Application
Name=raspieyes
Exec=$PI_HOME/raspieyes/play.sh
X-GNOME-Autostart-enabled=true
NoDisplay=true
EOF
$DEBUGFS -w -R "write $TMPAUTO /etc/xdg/autostart/raspieyes.desktop" "$DISK" 2>/dev/null
rm "$TMPAUTO"
echo "  XDG autostart configured"

# Step 6: Enable SSH
echo "[6/7] Enabling SSH..."
$DEBUGFS -w -R "symlink /etc/systemd/system/multi-user.target.wants/ssh.service /lib/systemd/system/ssh.service" "$DISK" 2>/dev/null || true
echo "  SSH enabled"

# Step 7: Fix ownership and permissions
echo "[7/7] Setting ownership and permissions..."
UIDGID=$($DEBUGFS -R "cat /etc/passwd" "$DISK" 2>/dev/null | grep "^$PI_USER:" | cut -d: -f3,4)
PI_UID=$(echo "$UIDGID" | cut -d: -f1)
PI_GID=$(echo "$UIDGID" | cut -d: -f2)
echo "  User $PI_USER: UID=$PI_UID GID=$PI_GID"

for f in raspieyes raspieyes/eye.mp4 raspieyes/play.sh raspieyes/config.txt raspieyes/setup.sh raspieyes/raspieyes.service raspieyes/README.md .config .config/labwc .config/labwc/autostart; do
    $DEBUGFS -w -R "set_inode_field $PI_HOME/$f uid $PI_UID" "$DISK" 2>/dev/null || true
    $DEBUGFS -w -R "set_inode_field $PI_HOME/$f gid $PI_GID" "$DISK" 2>/dev/null || true
done
$DEBUGFS -w -R "set_inode_field $PI_HOME/raspieyes/play.sh mode 0100755" "$DISK" 2>/dev/null || true

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Now:"
echo "  1. Eject the SD card (run: diskutil eject /Volumes/bootfs)"
echo "  2. Put it in the Pi and power on"
echo "  3. The eye video should play fullscreen!"
echo ""
echo "SSH credentials: user=pi password=raspberry"
