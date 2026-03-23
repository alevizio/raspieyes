#!/usr/bin/env python3
"""
raspieyes — camera-based presence detector

Runs face detection via the Pi Camera Module 3 and writes the current state
("idle" or "detected") to a file that play.sh reads each watchdog cycle.

Usage:
    python3 eye_tracker.py                     # defaults (Pi camera, 5 fps)
    python3 eye_tracker.py --fps 2             # lower CPU usage
    python3 eye_tracker.py --test-webcam       # test on Mac with USB webcam
"""

import argparse
import os
import signal
import sys
import time

STATE_IDLE = "idle"
STATE_DETECTED = "detected"


def parse_args():
    p = argparse.ArgumentParser(description="raspieyes presence detector")
    p.add_argument("--fps", type=int, default=5, help="capture rate (default: 5)")
    p.add_argument("--width", type=int, default=320, help="capture width (default: 320)")
    p.add_argument("--height", type=int, default=240, help="capture height (default: 240)")
    p.add_argument("--state-file", default="/tmp/raspieyes_state", help="path to state file")
    p.add_argument("--detect-threshold", type=int, default=3,
                    help="consecutive face frames to trigger 'detected' (default: 3)")
    p.add_argument("--idle-threshold", type=int, default=10,
                    help="consecutive no-face frames to return to 'idle' (default: 10)")
    p.add_argument("--min-face-size", type=int, default=30,
                    help="minimum face width in pixels (default: 30)")
    p.add_argument("--scale-factor", type=float, default=1.3,
                    help="Haar cascade scaleFactor (default: 1.3)")
    p.add_argument("--min-neighbors", type=int, default=4,
                    help="Haar cascade minNeighbors (default: 4)")
    p.add_argument("--test-webcam", action="store_true",
                    help="use USB webcam instead of Pi camera (for testing on Mac)")
    return p.parse_args()


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[eye_tracker {ts}] {msg}", flush=True)


def write_state(state_file, state):
    """Atomic write: write to .tmp then rename to avoid partial reads."""
    tmp = state_file + ".tmp"
    with open(tmp, "w") as f:
        f.write(state)
    os.rename(tmp, state_file)


def setup_picamera(width, height):
    """Open the Pi Camera Module 3 via picamera2."""
    from picamera2 import Picamera2

    cam = Picamera2()
    config = cam.create_preview_configuration(
        main={"size": (width, height), "format": "RGB888"}
    )
    cam.configure(config)
    cam.start()
    log(f"Pi camera started at {width}x{height}")
    return cam


def setup_webcam(width, height):
    """Open a USB webcam via OpenCV (for Mac testing)."""
    import cv2
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        log("ERROR: could not open webcam")
        sys.exit(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    log(f"Webcam started at {width}x{height}")
    return cap


def grab_frame(source, use_webcam):
    """Capture a single frame from the camera source."""
    if use_webcam:
        ret, frame = source.read()
        return frame if ret else None
    return source.capture_array()


def cleanup_source(source, use_webcam):
    """Release the camera resource."""
    if use_webcam:
        source.release()
    else:
        source.stop()


def main():
    args = parse_args()

    import cv2

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        log(f"ERROR: could not load cascade from {cascade_path}")
        sys.exit(1)
    log("Haar cascade loaded")

    if args.test_webcam:
        source = setup_webcam(args.width, args.height)
    else:
        source = setup_picamera(args.width, args.height)

    current_state = STATE_IDLE
    write_state(args.state_file, current_state)
    log(f"Initial state: {current_state}")

    detect_count = 0
    idle_count = 0
    frame_interval = 1.0 / args.fps
    running = True

    def shutdown(signum, _frame):
        nonlocal running
        log(f"Received signal {signum}, shutting down...")
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log(f"Running at {args.fps} fps, detect={args.detect_threshold}, idle={args.idle_threshold}")

    try:
        while running:
            t0 = time.monotonic()

            frame = grab_frame(source, args.test_webcam)
            if frame is None:
                time.sleep(frame_interval)
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY) if not args.test_webcam else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            faces = detector.detectMultiScale(
                gray,
                scaleFactor=args.scale_factor,
                minNeighbors=args.min_neighbors,
                minSize=(args.min_face_size, args.min_face_size),
            )

            has_face = len(faces) > 0

            if has_face:
                detect_count += 1
                idle_count = 0
            else:
                idle_count += 1
                detect_count = 0

            new_state = current_state
            if current_state == STATE_IDLE and detect_count >= args.detect_threshold:
                new_state = STATE_DETECTED
            elif current_state == STATE_DETECTED and idle_count >= args.idle_threshold:
                new_state = STATE_IDLE

            if new_state != current_state:
                log(f"State: {current_state} -> {new_state}")
                current_state = new_state
                write_state(args.state_file, current_state)

            elapsed = time.monotonic() - t0
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        log("Cleaning up...")
        write_state(args.state_file, STATE_IDLE)
        cleanup_source(source, args.test_webcam)
        log("Stopped")


if __name__ == "__main__":
    main()
