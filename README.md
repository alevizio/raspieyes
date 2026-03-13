# raspieyes

Video kiosk for Raspberry Pi 5 — loop videos fullscreen on an HDMI display.

## Quick Start

1. Flash **Pi OS Desktop (Bookworm)** using [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
   - Enable SSH, set username `pi` / password `raspberry`, set hostname `raspieyes`

2. Boot the Pi, then from your computer:

       scp -r raspieyes/ pi@raspieyes.local:~/
       ssh pi@raspieyes.local 'bash ~/raspieyes/setup.sh'

3. The Pi reboots and your video plays fullscreen.

## Adding Videos

Drop video files into the `videos/` directory:

    scp new_video.mp4 pi@raspieyes.local:~/raspieyes/videos/
    ssh pi@raspieyes.local 'sudo systemctl restart raspieyes'

Supported formats: MP4, GIF, WebM, MKV, AVI.

## Configuration

Edit `config.txt`:

    # Shuffle playlist? (yes/no)
    SHUFFLE=no

## Manual Playback

    ssh pi@raspieyes.local
    cd ~/raspieyes && ./play.sh

## Service Management

    sudo systemctl status raspieyes    # Check status
    sudo systemctl restart raspieyes   # Restart after adding videos
    sudo systemctl stop raspieyes      # Stop playback
    sudo systemctl disable raspieyes   # Disable auto-start

## Troubleshooting

- **No video:** Check `videos/` directory has files: `ls ~/raspieyes/videos/`
- **mpv not found:** `sudo apt install mpv`
- **Screen goes blank:** Run setup.sh again or `xset s off && xset -dpms`
- **Wrong user:** setup.sh auto-detects your username
