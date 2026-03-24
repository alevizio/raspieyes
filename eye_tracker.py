#!/usr/bin/env python3
"""
raspieyes — camera-based motion/presence detector

Detects people via motion (MOG2 background subtraction) or face detection
(Haar cascade) and writes tracking state to a file. The eye_renderer.py
imports functions from this module for real-time parallax tracking.

Usage:
    python3 eye_tracker.py                          # motion detection (default)
    python3 eye_tracker.py --detection-mode face    # face detection (legacy)
    python3 eye_tracker.py --test-webcam            # test on Mac with USB webcam
"""

import argparse
import os
import signal
import sys
import time

STATE_IDLE = "idle"
STATE_DETECTED = "detected"

# --- Reusable face detection for eye_renderer.py ---

def load_haar_cascade():
    """Load Haar cascade from the first available path. Returns CascadeClassifier."""
    import cv2
    cascade_candidates = [
        "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
        "/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml",
    ]
    if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
        cascade_candidates.insert(0, cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    for candidate in cascade_candidates:
        if os.path.isfile(candidate):
            detector = cv2.CascadeClassifier(candidate)
            if not detector.empty():
                return detector

    raise RuntimeError(f"Could not find Haar cascade in: {cascade_candidates}")


def detect_face_position(detector, gray, frame_width, frame_height,
                         scale_factor=1.1, min_neighbors=2, min_face_size=20):
    """Detect the largest face and return normalized position.

    Returns (nx, ny, nw) where:
        nx: horizontal position [-1, 1] (negative = left, positive = right)
        ny: vertical position [-1, 1] (negative = up, positive = down)
        nw: normalized face width [0, 1] (useful for depth estimation)
    Returns None if no face detected.
    """
    import cv2
    faces = detector.detectMultiScale(
        gray,
        scaleFactor=scale_factor,
        minNeighbors=min_neighbors,
        minSize=(min_face_size, min_face_size),
    )
    if len(faces) == 0:
        return None

    # Pick the largest face by area
    largest = max(faces, key=lambda f: f[2] * f[3])
    x, y, w, h = largest

    # Normalize center to [-1, 1] range
    cx = x + w / 2.0
    cy = y + h / 2.0
    nx = (cx / frame_width - 0.5) * 2.0
    ny = (cy / frame_height - 0.5) * 2.0
    nw = w / frame_width

    return (nx, ny, nw)


# --- Motion detection (MOG2 background subtraction) ---

def create_motion_detector(history=300, var_threshold=25):
    """Create a MOG2 background subtractor for motion detection.

    Works in low light — detects moving silhouettes against the background.
    Adaptive: handles dynamic lighting (fire flicker, LED flashes).
    """
    import cv2
    return cv2.createBackgroundSubtractorMOG2(
        history=history,
        varThreshold=var_threshold,
        detectShadows=False,
    )


# Reusable morphology kernel (created once)
_morph_kernel = None


def detect_motion_position(bg_subtractor, gray, frame_width, frame_height,
                           min_contour_area=300, _mask_cache=None):
    """Detect the largest moving object via background subtraction.

    Pass a pre-computed mask via _mask_cache to avoid double bg.apply().
    If _mask_cache is None, applies bg_subtractor to gray internally.

    Returns (nx, ny, nw) where:
        nx: horizontal position [-1, 1] (negative = left, positive = right)
        ny: vertical position [-1, 1] (negative = up, positive = down)
        nw: normalized width [0, 1] (useful for size/proximity estimation)
    Returns None if no significant motion detected.
    """
    import cv2
    global _morph_kernel

    if _morph_kernel is None:
        _morph_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    # Use pre-computed mask or apply background subtraction
    if _mask_cache is not None:
        mask = _mask_cache
    else:
        mask = bg_subtractor.apply(gray)

    # Morphological cleanup: remove noise, connect fragmented silhouettes
    mask = cv2.erode(mask, _morph_kernel, iterations=1)
    mask = cv2.dilate(mask, _morph_kernel, iterations=2)

    # Find contours of moving regions
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    # Filter by minimum area to ignore noise
    valid = [c for c in contours if cv2.contourArea(c) >= min_contour_area]
    if not valid:
        return None

    # Pick the largest contour (closest/most prominent person)
    largest = max(valid, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)

    # Normalize center to [-1, 1] range
    cx = x + w / 2.0
    cy = y + h / 2.0
    nx = (cx / frame_width - 0.5) * 2.0
    ny = (cy / frame_height - 0.5) * 2.0
    nw = w / frame_width

    return (nx, ny, nw)


def detect_all_motion_positions(bg_subtractor, gray, frame_width, frame_height,
                                min_contour_area=300, _mask_cache=None,
                                learning_rate=-1):
    """Detect ALL moving objects via background subtraction.

    Returns a list of (cx, cy, w) tuples in PIXEL coordinates (not normalized).
    The tracker.py CentroidTracker handles normalization and target selection.

    Returns empty list if no significant motion detected.
    """
    import cv2
    global _morph_kernel

    if _morph_kernel is None:
        _morph_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    if _mask_cache is not None:
        mask = _mask_cache
    else:
        mask = bg_subtractor.apply(gray, learningRate=learning_rate)

    mask = cv2.erode(mask, _morph_kernel, iterations=1)
    mask = cv2.dilate(mask, _morph_kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    results = []
    for c in contours:
        if cv2.contourArea(c) < min_contour_area:
            continue
        x, y, w, h = cv2.boundingRect(c)
        cx = x + w / 2.0
        cy = y + h / 2.0
        results.append((cx, cy, float(w)))

    return results


def parse_args():
    p = argparse.ArgumentParser(description="raspieyes presence detector")
    p.add_argument("--fps", type=int, default=5, help="capture rate (default: 5)")
    p.add_argument("--width", type=int, default=320, help="capture width (default: 320)")
    p.add_argument("--height", type=int, default=240, help="capture height (default: 240)")
    p.add_argument("--state-file", default="/tmp/raspieyes_state", help="path to state file")
    p.add_argument("--detect-threshold", type=int, default=3,
                    help="face frames in rolling window to trigger 'detected' (default: 3)")
    p.add_argument("--idle-threshold", type=int, default=28,
                    help="no-face frames in rolling window to return to 'idle' (default: 28)")
    p.add_argument("--window-size", type=int, default=30,
                    help="rolling window size for detection smoothing (default: 30)")
    p.add_argument("--min-face-size", type=int, default=20,
                    help="minimum face width in pixels (default: 20)")
    p.add_argument("--scale-factor", type=float, default=1.1,
                    help="Haar cascade scaleFactor (default: 1.1)")
    p.add_argument("--min-neighbors", type=int, default=2,
                    help="Haar cascade minNeighbors (default: 2)")
    p.add_argument("--test-webcam", action="store_true",
                    help="use USB webcam instead of Pi camera (for testing on Mac)")
    p.add_argument("--detection-mode", default="motion", choices=["motion", "face"],
                    help="detection method: 'motion' (MOG2, works in low light) or 'face' (Haar cascade)")
    p.add_argument("--min-contour-area", type=int, default=300,
                    help="minimum contour area for motion detection (default: 300)")
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
    """Open a USB webcam via OpenCV. Tries multiple device indices for Pi compatibility."""
    import cv2
    # On Pi, USB webcams may not be at index 0 (Pi Camera takes those)
    for idx in [8, 0, 2, 4, 6, 1]:
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            log(f"Webcam opened at /dev/video{idx}, {width}x{height}")
            return cap
        cap.release()
    log("ERROR: could not open webcam at any device index")
    sys.exit(1)


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

    # Set up detector based on mode
    use_motion = args.detection_mode == "motion"

    if use_motion:
        bg_subtractor = create_motion_detector()
        log(f"Motion detector (MOG2) initialized")
    else:
        try:
            detector = load_haar_cascade()
            log("Haar cascade loaded")
        except RuntimeError as e:
            log(f"ERROR: {e}")
            sys.exit(1)

    if args.test_webcam:
        source = setup_webcam(args.width, args.height)
    else:
        source = setup_picamera(args.width, args.height)

    current_state = STATE_IDLE
    write_state(args.state_file, current_state)
    log(f"Initial state: {current_state}")

    # Rolling window: track last N frames instead of requiring consecutive detections
    from collections import deque
    window = deque(maxlen=args.window_size)
    frame_interval = 1.0 / args.fps
    last_state_change = 0.0  # monotonic timestamp of last state change
    COOLDOWN = 30.0  # minimum seconds between state changes
    running = True

    def shutdown(signum, _frame):
        nonlocal running
        log(f"Received signal {signum}, shutting down...")
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    mode_label = "motion (MOG2)" if use_motion else "face (Haar)"
    log(f"Running at {args.fps} fps, mode={mode_label}, window={args.window_size}, "
        f"detect={args.detect_threshold}/{args.window_size}, "
        f"idle={args.idle_threshold}/{args.window_size}")

    try:
        while running:
            t0 = time.monotonic()

            frame = grab_frame(source, args.test_webcam)
            if frame is None:
                time.sleep(frame_interval)
                continue

            if args.test_webcam:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

            # Detect based on mode
            if use_motion:
                has_detection = detect_motion_position(
                    bg_subtractor, gray, args.width, args.height,
                    min_contour_area=args.min_contour_area,
                ) is not None
            else:
                has_detection = detect_face_position(
                    detector, gray, args.width, args.height,
                    scale_factor=args.scale_factor,
                    min_neighbors=args.min_neighbors,
                    min_face_size=args.min_face_size,
                ) is not None

            window.append(1 if has_detection else 0)
            detect_count = sum(window)
            no_detect_count = len(window) - detect_count

            new_state = current_state
            if current_state == STATE_IDLE and detect_count >= args.detect_threshold:
                new_state = STATE_DETECTED
            elif current_state == STATE_DETECTED and no_detect_count >= args.idle_threshold:
                new_state = STATE_IDLE

            now = time.monotonic()
            if new_state != current_state and (now - last_state_change) >= COOLDOWN:
                log(f"State: {current_state} -> {new_state} "
                    f"(detections {detect_count}/{len(window)} in window)")
                current_state = new_state
                last_state_change = now
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
