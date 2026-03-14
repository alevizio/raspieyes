# Eye Tracking Plan for raspieyes

## Goal
Add a Raspberry Pi Camera Module 3 so the eye animations react to people nearby — the eyes on the bike "see" and respond to passersby.

## Hardware Needed
- **Raspberry Pi Camera Module 3 (wide-angle 120°)** ~$35
  - 12MP Sony IMX708, autofocus, HDR
  - Comes with 22-pin FPC cable for Pi 5
  - Connects to one of the Pi 5's CSI ports (separate from the two HDMI ports already in use)

## Software Approach
Use OpenCV or MediaPipe for face detection via the camera, then change which eye video plays based on what's detected.

### Reactive Behavior Ideas
| Detection | Eye Reaction |
|-----------|-------------|
| No one nearby | Normal blinking loop (current behavior) |
| Person detected | Eyes look toward them |
| Person very close | Wide-eye surprise animation |
| Person moving left/right | Eyes follow their direction |

### Key Libraries
- **picamera2** — Pi 5 camera access
- **OpenCV** — face/eye detection (Haar Cascades or HOG)
- **MediaPipe** (optional) — more accurate face mesh + gaze direction
- **dlib** (optional) — facial landmark detection

### Architecture
1. Camera runs in a background thread capturing frames at 5-10 FPS (low power)
2. Face detection runs on each frame
3. Detection results (face position, distance, direction) sent to play.sh via a simple mechanism (file, socket, or signal)
4. play.sh switches video based on detection state

### Power Considerations
- Run detection at low FPS (5-10) to save CPU
- Could add a motion sensor to only activate camera when something is nearby
- Camera draws ~250mW extra

## Reference Projects
- [PiGaze](https://github.com/CR1502/PiGaze) — real-time gaze tracking on Pi with PyTorch
- [Pi-Pupil-Detection](https://github.com/ankurrajw/Pi-Pupil-Detection) — pupil detection on Pi
- [eyetracker-raspberrypi](https://github.com/ZhaoyuDeng/eyetracker-raspberrypi) — dual-camera eye tracker
- [Furby Pi Eyes](https://www.raspberrypi.com/news/these-furby-controlled-raspberry-pi-powered-eyes-follow-you/) — Pi eyes that follow you
- [Watchman](https://grahamjessup.com/watchman/) — face-tracking robot eyes
- [Animatronic Eyes](https://hackaday.com/2025/08/28/animatronic-eyes-are-watching-you/) — MediaPipe face tracking
- [Face Tracking Pi](https://pyimagesearch.com/2019/04/01/pan-tilt-face-tracking-with-a-raspberry-pi-and-opencv/) — OpenCV pan/tilt tracking
- [Low Cost Eye Tracking](https://hackaday.io/project/153293-low-cost-open-source-eye-tracking) — Hackaday project
