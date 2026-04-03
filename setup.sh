#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIDEOS_DIR="$SCRIPT_DIR/videos"
BOOTSTRAP_AUTOSTART="/etc/xdg/autostart/raspieyes.desktop"
CURRENT_USER="${RASPIEYES_USER:-$(logname 2>/dev/null || whoami)}"
CURRENT_HOME="${RASPIEYES_HOME:-$(eval echo "~$CURRENT_USER")}"
CURRENT_UID=$(id -u "$CURRENT_USER")

echo "=== raspieyes setup ==="

if sudo test -f "$BOOTSTRAP_AUTOSTART" && sudo grep -q "$SCRIPT_DIR/setup.sh" "$BOOTSTRAP_AUTOSTART"; then
    echo "[bootstrap] Removing one-time setup autostart..."
    sudo rm -f "$BOOTSTRAP_AUTOSTART"
fi

# 1. Install mpv + unclutter (hide cursor)
echo "[1/5] Installing packages..."
sudo apt update -qq
sudo apt install -y mpv unclutter-xfixes wlr-randr ffmpeg socat

# Install eye tracking dependencies if camera is connected
if [[ -e /dev/video0 ]] || ls /dev/video* &>/dev/null 2>&1; then
    echo "  Camera detected, installing tracking packages..."
    sudo apt install -y python3-picamera2 python3-opencv
else
    echo "  No camera detected, skipping tracking packages"
    echo "  (run 'sudo apt install python3-picamera2 python3-opencv' later if needed)"
fi

# 2. Set up videos directory
echo "[2/5] Setting up videos directory..."
mkdir -p "$VIDEOS_DIR"

# Move any video files from project root into videos/
for ext in mp4 gif webm mkv avi; do
    for f in "$SCRIPT_DIR"/*."$ext"; do
        [[ -f "$f" ]] || continue
        echo "  Moving $(basename "$f") -> videos/"
        mv "$f" "$VIDEOS_DIR/"
    done
done

if [[ -z "$(ls "$VIDEOS_DIR"/*.mp4 "$VIDEOS_DIR"/*.gif "$VIDEOS_DIR"/*.webm "$VIDEOS_DIR"/*.mkv "$VIDEOS_DIR"/*.avi 2>/dev/null)" ]]; then
    echo "  WARNING: No video files found. Add some to $VIDEOS_DIR/"
fi

# 3. Set permissions
echo "[3/5] Setting permissions..."
chmod +x "$SCRIPT_DIR/play.sh"

# 4. Install systemd service (fallback) + labwc autostart (primary)
echo "[4/5] Installing autostart..."

# --- Systemd service (fallback) ---
cat > /tmp/raspieyes.service <<EOF
[Unit]
Description=raspieyes video kiosk
After=graphical.target
Wants=graphical.target

[Service]
Type=simple
User=$CURRENT_USER
Environment=DISPLAY=:0
Environment=WAYLAND_DISPLAY=wayland-1
Environment=XDG_RUNTIME_DIR=/run/user/$CURRENT_UID
ExecStartPre=/bin/sleep 10
ExecStart=$SCRIPT_DIR/play.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
EOF
sudo cp /tmp/raspieyes.service /etc/systemd/system/
rm /tmp/raspieyes.service
sudo systemctl daemon-reload
sudo systemctl enable raspieyes.service
echo "  Systemd service installed (fallback)"

# --- labwc autostart (primary — runs after compositor is ready) ---
LABWC_DIR="$CURRENT_HOME/.config/labwc"
AUTOSTART_FILE="$LABWC_DIR/autostart"
mkdir -p "$LABWC_DIR"

# Remove old entries if re-running setup
sed -i '/raspieyes/d' "$AUTOSTART_FILE" 2>/dev/null || true
sed -i '/unclutter/d' "$AUTOSTART_FILE" 2>/dev/null || true
sed -i '/wlr-randr/d' "$AUTOSTART_FILE" 2>/dev/null || true

# Add mirror displays + unclutter + play.sh to labwc autostart
cat >> "$AUTOSTART_FILE" <<EOF
# raspieyes: mirror both HDMI outputs
(sleep 1 && wlr-randr --output HDMI-A-2 --pos 0,0) &
unclutter --hide-on-touch &
# raspieyes: loop videos fullscreen
(sleep 2 && $SCRIPT_DIR/play.sh) &
EOF
echo "  labwc autostart configured (primary)"
sudo chown -R "$CURRENT_USER:$CURRENT_USER" "$LABWC_DIR"

# Disable the systemd service since labwc autostart is primary
# (keeps it installed but won't double-launch)
sudo systemctl disable raspieyes.service 2>/dev/null || true

# 5. Kiosk mode: disable screen blanking
echo "[5/5] Configuring kiosk mode..."

# Disable screen blanking via X11 (if available)
if command -v xset &>/dev/null; then
    xset s off 2>/dev/null || true
    xset -dpms 2>/dev/null || true
fi

# Disable screen blanking via labwc config
LABWC_RC="$LABWC_DIR/rc.xml"
if [[ ! -f "$LABWC_RC" ]] || ! grep -q "screenSaver" "$LABWC_RC" 2>/dev/null; then
    if [[ ! -f "$LABWC_RC" ]]; then
        cat > "$LABWC_RC" <<'RCEOF'
<?xml version="1.0"?>
<labwc_config>
  <core><screenSaver><timeout>0</timeout></screenSaver></core>
</labwc_config>
RCEOF
        echo "  Screen blanking disabled"
    fi
fi
sudo chown -R "$CURRENT_USER:$CURRENT_USER" "$LABWC_DIR"

# 6. Power optimizations (for battery operation)
echo "[6/6] Optimizing power consumption..."

# Disable WiFi
sudo rfkill block wifi 2>/dev/null || true
# Persist: add to /boot/firmware/config.txt
if ! grep -q "dtoverlay=disable-wifi" /boot/firmware/config.txt 2>/dev/null; then
    echo "dtoverlay=disable-wifi" | sudo tee -a /boot/firmware/config.txt >/dev/null
fi
echo "  WiFi disabled"

# Disable Bluetooth
sudo rfkill block bluetooth 2>/dev/null || true
if ! grep -q "dtoverlay=disable-bt" /boot/firmware/config.txt 2>/dev/null; then
    echo "dtoverlay=disable-bt" | sudo tee -a /boot/firmware/config.txt >/dev/null
fi
echo "  Bluetooth disabled"

# Disable onboard LEDs
if ! grep -q "act_led_trigger=none" /boot/firmware/config.txt 2>/dev/null; then
    sudo tee -a /boot/firmware/config.txt >/dev/null <<'BOOTEOF'
# Power saving: disable LEDs
act_led_trigger=none
act_led_activelow=off
pwr_led_trigger=none
pwr_led_activelow=off
BOOTEOF
fi
echo "  LEDs disabled"

# Disable HDMI audio (saves power, we only need video)
if ! grep -q "noaudio" /boot/firmware/config.txt 2>/dev/null; then
    echo "dtparam=noaudio" | sudo tee -a /boot/firmware/config.txt >/dev/null
fi
echo "  Audio disabled"

# Set CPU governor to powersave
echo powersave | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor >/dev/null 2>&1 || true
# Persist via cron
(sudo crontab -l 2>/dev/null | grep -v scaling_governor; echo "@reboot echo powersave | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor") | sudo crontab - 2>/dev/null || true
echo "  CPU governor set to powersave"

# Disable unnecessary services
for svc in cups bluetooth triggerhappy; do
    sudo systemctl disable "$svc" 2>/dev/null || true
    sudo systemctl stop "$svc" 2>/dev/null || true
done
echo "  Unnecessary services disabled"

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Videos directory: $VIDEOS_DIR"
echo "  Add videos: scp video.mp4 $(whoami)@$(hostname).local:$VIDEOS_DIR/"
echo ""
echo "Rebooting in 5 seconds..."
sleep 5
sudo reboot
