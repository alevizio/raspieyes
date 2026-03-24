# raspieyes 👁️

Lifelike eyes that follow you. Built with Raspberry Pi.

A real-time rendered parallax eye system that tracks faces, reacts to sound, and responds to depth — designed for Burning Man, Halloween, art installations, or anywhere you want something watching.

**[Live Demo](https://website-alevizio.vercel.app)** · **[Build Guide](#build-your-own)** · **[Hardware List](#hardware)**

---

## What it does

Two round HDMI displays show procedurally rendered 3D eyes that:

- **Track faces** — OpenCV DNN + MediaPipe detect faces and follow them with parallax layers
- **React to depth** — pupil dilates dramatically as you get closer (0.6x → 1.6x range)
- **Follow motion** — hands, bodies, any movement — not just faces
- **Pulse to music** — stereo microphone detects bass beats, pupil throbs in sync
- **Startle at sounds** — loud claps trigger a blink + pupil spike
- **Look toward noise** — stereo audio direction makes the eye turn toward sounds
- **Blink naturally** — randomized blink intervals with double-blink chance

## How it works

```
Camera (15 Hz) → Face/Motion Detection → Tracking State (position + velocity)
                                              ↓
Microphone (32 kHz) → Beat/Startle/Direction → Animation Engine
                                              ↓
                                    Render Loop (60 Hz) → Two Round Displays
```

The eye is rendered as three parallax layers (sclera, iris, pupil) that move independently — the pupil tracks furthest, the sclera barely moves. This creates a convincing depth illusion on flat screens.

Detection runs on a background thread at 15 fps. Rendering runs at 60 fps with smooth interpolation between detection frames.

## Hardware

| Part | Price | Why |
|------|-------|-----|
| Raspberry Pi 5 (8GB) | $80 | Quad-core ARM, dual HDMI, PCIe for AI HAT |
| 2x Round HDMI Display (1080x1080) | ~$50 each | The "eyeballs" |
| Pi Camera Module 3 (or USB webcam) | $25-35 | Face/motion detection |
| Pi AI HAT+ 13 TOPS (optional) | ~$77 | NPU acceleration for smoother tracking |
| Pi AI Camera IMX500 (optional) | $70 | On-sensor inference, zero CPU cost |
| USB-C Power Bank (20,000mAh+) | ~$30 | Portable power (~6 hours runtime) |

**Total minimal build: ~$240** · **Full build with AI acceleration: ~$380**

## Build Your Own

### 1. Flash Raspberry Pi OS

Flash **Pi OS Desktop (Bookworm 64-bit)** with [Raspberry Pi Imager](https://www.raspberrypi.com/software/). Enable SSH, set username `pi`, password `raspberry`, hostname `raspieyes`.

### 2. Connect Hardware

- Plug both round displays into HDMI ports
- Connect camera (CSI ribbon cable or USB)
- Power on

### 3. Clone & Install

```bash
scp -r raspieyes/ pi@raspieyes.local:~/
ssh pi@raspieyes.local 'bash ~/raspieyes/setup.sh'
```

### 4. Configure

Edit `config.txt`:

```ini
RENDER_MODE=parallax    # Real-time rendered eyes (or "video" for video loop)
TRACKING=yes            # Enable camera tracking
EYE_COLOR=blue          # blue, green, brown, amber, gray
USB_WEBCAM=no           # Set to "yes" if using USB webcam instead of Pi Camera
```

### 5. Reboot

```bash
sudo reboot
```

The eyes start automatically on boot. Walk in front of the camera!

## Configuration

All settings in `config.txt`:

```ini
# Rendering
RENDER_MODE=parallax          # "parallax" (real-time) or "video" (loop mp4s)
EYE_COLOR=blue                # Iris color

# Tracking
TRACKING=yes                  # Enable camera
DETECTION_MODE=motion         # "motion" or "face"
USB_WEBCAM=no                 # USB webcam instead of Pi Camera

# Tuning (uncomment to customize)
# MIN_CONTOUR_AREA=300        # Motion sensitivity
# PRESENCE_TIMEOUT=15         # Seconds to hold position after losing track
# SCLERA_PARALLAX=0.08        # Parallax intensity per layer
# IRIS_PARALLAX=0.6
# PUPIL_PARALLAX=0.95
# MAX_OFFSET=350              # Max pixel displacement
```

## Testing on Mac

You can test the eye renderer on your Mac before deploying to Pi:

```bash
# Mouse tracking (no camera needed)
python3 eye_renderer.py --mouse --windowed --single-eye

# Webcam tracking (run from Terminal.app for camera access)
python3 eye_renderer.py --test-webcam --windowed --single-eye

# Dual eyes
python3 eye_renderer.py --mouse --windowed
```

## Architecture

```
eye_renderer.py    — Main renderer: parallax eye, animation, audio, 60fps loop
eye_tracker.py     — Detection functions: face (DNN/Haar), motion (MOG2), camera setup
tracker.py         — Centroid tracker with Kalman filtering
play.sh            — Autostart script: screen setup, renderer launch, watchdog
config.txt         — Runtime configuration
setup.sh           — One-time Pi setup: deps, autostart service
```

## Service Management

```bash
sudo systemctl status raspieyes    # Check status
sudo systemctl restart raspieyes   # Restart
sudo systemctl stop raspieyes      # Stop
journalctl -u raspieyes -f         # Live logs
```

## License

MIT

## Credits

Built by [Alejandro](https://github.com/alevizio) for Burning Man 2026.
