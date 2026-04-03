#!/usr/bin/env python3
"""
raspieyes — real-time parallax eye renderer

Renders multi-layered eyes (sclera, iris, pupil, eyelids) with parallax
offsets driven by motion tracking from the Pi Camera Module 3. Features
micro-saccades, pupil dilation, and organic idle behavior.

Usage:
    python3 eye_renderer.py                          # Pi with camera
    python3 eye_renderer.py --test-webcam --windowed # Mac testing
    python3 eye_renderer.py --no-camera --windowed   # idle animation only
"""

import argparse
import math
import os
import random
import signal
import sys
import threading
import time
from collections import deque

import pygame
import pygame.gfxdraw

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCREEN_SIZE = 1080
TARGET_FPS = 60  # VR-style: render fast, predict between observations
DETECTION_FPS = 15

# Parallax multipliers (0 = stationary, 1 = full tracking)
DEFAULT_SCLERA_PARALLAX = 0.08
DEFAULT_IRIS_PARALLAX = 0.6
DEFAULT_PUPIL_PARALLAX = 0.95
DEFAULT_MAX_OFFSET = 350  # max pixel displacement from center

# Interpolation
DEFAULT_LERP_SPEED = 12.0     # tracking responsiveness
IDLE_LERP_SPEED = 2.0         # slower when idle

# Idle behavior
IDLE_DRIFT_RANGE = 0.18       # how far eyes drift when idle
PRESENCE_TIMEOUT = 15.0       # seconds to hold position after losing all tracks
IDLE_CURIOSITY_MIN = 5.0      # seconds between curiosity glances
IDLE_CURIOSITY_MAX = 12.0

# Blink timing (seconds)
BLINK_CLOSE_DURATION = 0.07
BLINK_PAUSE_DURATION = 0.03
BLINK_OPEN_DURATION = 0.11
IDLE_BLINK_MIN = 3.0
IDLE_BLINK_MAX = 7.0
TRACK_BLINK_MIN = 2.0
TRACK_BLINK_MAX = 5.0
DOUBLE_BLINK_CHANCE = 0.15    # 15% chance of double-blink

# Eye dimensions relative to SCREEN_SIZE
SCLERA_RADIUS_RATIO = 0.44
IRIS_RADIUS_RATIO = 0.24      # larger iris
PUPIL_RADIUS_RATIO = 0.13     # larger pupil
HIGHLIGHT_RADIUS_RATIO = 0.035

# Cross-eye offset (pixels)
CROSS_EYE_OFFSET = 20

# Eyelid color
EYELID_COLOR = (15, 10, 8)  # dark skin tone, not pure black

# Micro-saccade parameters
SACCADE_INTERVAL = 0.3        # seconds between micro-saccades
SACCADE_SMALL = 0.008         # normal jitter magnitude (subtle tremor)
SACCADE_LARGE = 0.025         # occasional big jump magnitude
SACCADE_LARGE_CHANCE = 0.05   # 5% chance of big jump
SACCADE_PIXEL_SCALE = 10      # multiply saccade by this for pixel offset

# Pupil dilation
PUPIL_DILATION_BASE = 1.0
PUPIL_DILATION_BREATHE_AMP = 0.03    # ±3% oscillation
PUPIL_DILATION_BREATHE_FREQ = 0.2    # Hz
PUPIL_DILATION_SURPRISE = 1.2        # spike on first detection
PUPIL_DILATION_DECAY = 3.0           # decay speed back to normal

# Iris color presets
EYE_COLORS = {
    "blue":  {"base": (70, 130, 200), "ring": (30, 65, 130), "inner": (110, 170, 230), "limbal": (20, 50, 100)},
    "green": {"base": (80, 160, 90),  "ring": (30, 90, 40),  "inner": (130, 200, 120), "limbal": (20, 60, 30)},
    "brown": {"base": (140, 90, 50),  "ring": (70, 40, 20),  "inner": (180, 130, 80),  "limbal": (50, 30, 15)},
    "amber": {"base": (190, 150, 50), "ring": (130, 90, 15), "inner": (220, 190, 90),  "limbal": (100, 70, 10)},
    "gray":  {"base": (140, 145, 150),"ring": (80, 85, 90),  "inner": (180, 185, 190), "limbal": (60, 65, 70)},
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="raspieyes parallax eye renderer")
    p.add_argument("--eye-color", default="blue", choices=EYE_COLORS.keys())
    p.add_argument("--fps", type=int, default=TARGET_FPS)
    p.add_argument("--detection-fps", type=int, default=DETECTION_FPS)
    p.add_argument("--test-webcam", action="store_true")
    p.add_argument("--no-camera", action="store_true")
    p.add_argument("--mouse", action="store_true",
                   help="track mouse position instead of camera (for testing)")
    p.add_argument("--detection-mode", default="motion", choices=["motion", "face"])
    p.add_argument("--min-contour-area", type=int, default=300)
    p.add_argument("--windowed", action="store_true")
    p.add_argument("--single-eye", action="store_true")
    p.add_argument("--state-file", default="/tmp/raspieyes_state")
    p.add_argument("--sclera-parallax", type=float, default=DEFAULT_SCLERA_PARALLAX)
    p.add_argument("--iris-parallax", type=float, default=DEFAULT_IRIS_PARALLAX)
    p.add_argument("--pupil-parallax", type=float, default=DEFAULT_PUPIL_PARALLAX)
    p.add_argument("--max-offset", type=int, default=DEFAULT_MAX_OFFSET)
    p.add_argument("--lerp-speed", type=float, default=DEFAULT_LERP_SPEED)
    p.add_argument("--capture-width", type=int, default=640)
    p.add_argument("--capture-height", type=int, default=480)
    p.add_argument("--presence-timeout", type=float, default=PRESENCE_TIMEOUT)
    return p.parse_args()


# ---------------------------------------------------------------------------
# Thread-safe tracking state
# ---------------------------------------------------------------------------

class TrackingState:
    """VR-style predict-to-vsync tracking state with velocity estimation."""

    def __init__(self, presence_timeout=PRESENCE_TIMEOUT):
        self._lock = threading.Lock()
        self.presence_timeout = presence_timeout
        self.state = "idle"
        self.pos_x = 0.0       # last observed position
        self.pos_y = 0.0
        self.vel_x = 0.0       # velocity (units/sec)
        self.vel_y = 0.0
        self.face_w = 0.0      # depth proxy
        self.last_obs_time = 0.0

    def update(self, state, fx=0.0, fy=0.0, fw=0.0):
        """Called by detection thread with new observation."""
        with self._lock:
            t_now = time.monotonic()
            if state == "detected" and self.state == "detected" and self.last_obs_time > 0:
                dt = max(t_now - self.last_obs_time, 0.001)
                new_vx = (fx - self.pos_x) / dt
                new_vy = (fy - self.pos_y) / dt
                # Heavy low-pass on velocity — prevents overshoot from detection jitter
                self.vel_x = 0.2 * new_vx + 0.8 * self.vel_x
                self.vel_y = 0.2 * new_vy + 0.8 * self.vel_y
                # Clamp velocity to prevent runaway
                max_vel = 3.0  # max ~3 units/sec (full screen in ~0.7s)
                self.vel_x = max(-max_vel, min(max_vel, self.vel_x))
                self.vel_y = max(-max_vel, min(max_vel, self.vel_y))
            elif state != "detected":
                # Decay velocity when idle
                self.vel_x *= 0.8
                self.vel_y *= 0.8
            self.pos_x = fx
            self.pos_y = fy
            self.face_w = fw
            self.state = state
            self.last_obs_time = t_now

    def get(self):
        """Called by render loop — returns latest smoothed position."""
        with self._lock:
            t_now = time.monotonic()
            staleness = t_now - self.last_obs_time if self.last_obs_time > 0 else 999
            state = self.state if staleness < self.presence_timeout else "idle"
            return (state, self.pos_x, self.pos_y,
                    self.face_w, self.last_obs_time)


class AudioState:
    """Thread-safe audio analysis state."""

    def __init__(self):
        self._lock = threading.Lock()
        self.beat_intensity = 0.0   # 0-1, current bass beat strength
        self.volume_level = 0.0     # 0-1, current ambient volume
        self.startle = False        # True briefly after loud sudden sound
        self.sound_direction = 0.0  # -1 (left) to 1 (right)
        self.timestamp = 0.0

    def update(self, beat=0.0, volume=0.0, startle=False, direction=0.0):
        with self._lock:
            self.beat_intensity = beat
            self.volume_level = volume
            self.startle = startle
            self.sound_direction = direction
            self.timestamp = time.monotonic()

    def get(self):
        with self._lock:
            return (self.beat_intensity, self.volume_level,
                    self.startle, self.sound_direction, self.timestamp)


# ---------------------------------------------------------------------------
# Audio thread
# ---------------------------------------------------------------------------

def audio_thread(audio_state):
    """Background thread: captures stereo audio, detects beats, startles, and direction."""
    try:
        import sounddevice as sd
        import numpy as np
    except ImportError:
        print("[audio] sounddevice not available, audio features disabled", flush=True)
        return

    SAMPLE_RATE = 32000
    CHUNK = 1024  # ~32ms per chunk
    BASS_LOW = 60   # Hz
    BASS_HIGH = 200  # Hz

    # Find the microphone device
    mic_device = None
    for i, d in enumerate(sd.query_devices()):
        if d['max_input_channels'] >= 2 and 'C925e' in d.get('name', ''):
            mic_device = i
            break
    if mic_device is None:
        # Try any stereo input
        for i, d in enumerate(sd.query_devices()):
            if d['max_input_channels'] >= 2:
                mic_device = i
                break
    if mic_device is None:
        print("[audio] No stereo microphone found, audio disabled", flush=True)
        return

    print(f"[audio] Using device {mic_device}, {SAMPLE_RATE}Hz stereo", flush=True)

    # Rolling state
    bass_history = deque(maxlen=30)   # ~1 second of bass energy
    rms_history = deque(maxlen=15)     # ~500ms of volume
    smooth_direction = 0.0
    startle_cooldown = 0.0

    # FFT bin indices for bass range
    freqs = np.fft.rfftfreq(CHUNK, 1.0 / SAMPLE_RATE)
    bass_mask = (freqs >= BASS_LOW) & (freqs <= BASS_HIGH)

    def process_chunk(data):
        nonlocal smooth_direction, startle_cooldown

        left = data[:, 0]
        right = data[:, 1]
        mono = (left + right) / 2.0

        # --- Volume (RMS) ---
        rms = float(np.sqrt(np.mean(mono ** 2)))
        rms_history.append(rms)
        avg_rms = sum(rms_history) / len(rms_history) if rms_history else 0.001
        volume = min(1.0, rms / 0.1)  # normalize to ~0-1

        # --- Beat detection (bass energy) ---
        fft_data = np.abs(np.fft.rfft(mono))
        bass_energy = float(np.mean(fft_data[bass_mask])) if np.any(bass_mask) else 0.0
        bass_history.append(bass_energy)
        avg_bass = sum(bass_history) / len(bass_history) if bass_history else 0.001
        beat = 0.0
        if avg_bass > 0.001 and bass_energy > avg_bass * 1.2:
            beat = min(1.0, (bass_energy / avg_bass - 1.0) / 2.0)

        # --- Startle detection ---
        startle = False
        startle_cooldown = max(0.0, startle_cooldown - CHUNK / SAMPLE_RATE)
        if avg_rms > 0.001 and rms > avg_rms * 2.0 and startle_cooldown <= 0:
            startle = True
            startle_cooldown = 0.5  # 500ms cooldown

        # --- Sound direction (stereo) ---
        left_rms = float(np.sqrt(np.mean(left ** 2)))
        right_rms = float(np.sqrt(np.mean(right ** 2)))
        total = left_rms + right_rms
        if total > 0.005:
            raw_dir = (right_rms - left_rms) / total  # -1 left, +1 right
            smooth_direction += (raw_dir - smooth_direction) * 0.3
        else:
            smooth_direction *= 0.95  # decay toward center

        audio_state.update(
            beat=beat,
            volume=volume,
            startle=startle,
            direction=smooth_direction,
        )

    try:
        with sd.InputStream(device=mic_device, channels=2, samplerate=SAMPLE_RATE,
                            blocksize=CHUNK, dtype='float32') as stream:
            print("[audio] Microphone stream started", flush=True)
            while True:
                data, overflowed = stream.read(CHUNK)
                if overflowed:
                    continue
                process_chunk(data)
    except Exception as e:
        print(f"[audio] Error: {e}", flush=True)
    finally:
        print("[audio] Stopped", flush=True)


# ---------------------------------------------------------------------------
# Detection thread
# ---------------------------------------------------------------------------

def detection_loop(tracking, args):
    """Background thread: MediaPipe face + MOG2 motion hybrid detection."""
    import cv2
    from eye_tracker import (
        detect_face_position, load_haar_cascade,
        detect_all_motion_positions, create_motion_detector,
        setup_picamera, setup_webcam, grab_frame, cleanup_source,
    )
    from tracker import CentroidTracker

    # --- Initialize detectors ---
    bg_subtractor = create_motion_detector()
    centroid_tracker = CentroidTracker(
        max_disappeared=75,
        max_distance=180,
        process_noise=0.05,
        measurement_noise=0.5,
        presence_timeout=args.presence_timeout,
    )

    # Try MediaPipe first (much better than Haar), fall back to Haar
    use_mediapipe = False
    mp_face_detector = None
    face_detector = None

    try:
        import mediapipe as mp
        # Find model file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(script_dir, "blaze_face_short_range.tflite")
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")
        base_options = mp.tasks.BaseOptions(model_asset_path=model_path)
        options = mp.tasks.vision.FaceDetectorOptions(
            base_options=base_options,
            min_detection_confidence=0.5,
            min_suppression_threshold=0.3,
        )
        mp_face_detector = mp.tasks.vision.FaceDetector.create_from_options(options)
        use_mediapipe = True
        print("[detector] MediaPipe face detection initialized", flush=True)
    except (ImportError, Exception) as e:
        print(f"[detector] MediaPipe unavailable ({e}), trying OpenCV DNN...", flush=True)

    # Try OpenCV DNN face detector (much better than Haar, works on Pi)
    dnn_net = None
    if not use_mediapipe:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        prototxt = os.path.join(script_dir, "deploy.prototxt")
        caffemodel = os.path.join(script_dir, "res10_300x300_ssd_iter_140000_fp16.caffemodel")
        if os.path.isfile(prototxt) and os.path.isfile(caffemodel):
            try:
                dnn_net = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
                print("[detector] OpenCV DNN face detection initialized", flush=True)
            except Exception as e2:
                print(f"[detector] OpenCV DNN failed ({e2}), trying Haar...", flush=True)

    # Last resort: Haar cascade
    if not use_mediapipe and dnn_net is None:
        try:
            face_detector = load_haar_cascade()
            print("[detector] Haar cascade fallback initialized", flush=True)
        except RuntimeError:
            print("[detector] No face detector available, motion-only", flush=True)

    use_webcam = args.test_webcam
    cap_w = getattr(args, "capture_width", 640)
    cap_h = getattr(args, "capture_height", 480)
    if use_webcam:
        source = setup_webcam(cap_w, cap_h)
    else:
        source = setup_picamera(cap_w, cap_h)

    frame_interval = 1.0 / args.detection_fps
    print(f"[detector] Running at {args.detection_fps} fps, {cap_w}x{cap_h}", flush=True)

    warmup_frames = args.detection_fps * 2
    warmup_count = 0
    learning_rate = 0.01

    last_face_time = 0.0  # monotonic time of last face detection
    # Double-EMA cascade: stage1 (fast) → stage2 (smooth) — like a 2nd order filter
    s1_x, s1_y, s1_w = 0.0, 0.0, 0.0  # stage 1: fast tracking
    s2_x, s2_y, s2_w = 0.0, 0.0, 0.0  # stage 2: smooth output
    prev_x, prev_y = 0.0, 0.0          # last emitted position (for dead zone)
    DEAD_ZONE = 0.02  # ignore movements smaller than this (~7px)

    try:
        while True:
            t0 = time.monotonic()
            frame = grab_frame(source, use_webcam)
            if frame is None:
                time.sleep(frame_interval)
                continue

            if use_webcam:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                rgb = frame  # picamera2 already gives RGB

            # Equalize histogram — critical for NoIR cameras with pink/IR tint
            gray = cv2.equalizeHist(gray)

            h, w = gray.shape[:2]

            # Feed MOG2 every frame (maintains background model for motion fallback)
            mask = bg_subtractor.apply(gray, learningRate=0.01)

            # --- Face detection (primary) ---
            face_result = None

            if use_mediapipe and mp_face_detector is not None:
                # MediaPipe tasks API needs mp.Image
                import mediapipe as mp
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                results = mp_face_detector.detect(mp_image)
                if results.detections:
                    # Pick the highest-confidence detection
                    best = max(results.detections, key=lambda d: d.categories[0].score)
                    bbox = best.bounding_box
                    # Bounding box center normalized to [-1, 1]
                    bcx = (bbox.origin_x + bbox.width / 2.0) / w
                    bcy = (bbox.origin_y + bbox.height / 2.0) / h
                    # Use nose keypoint if available (index 2), else bbox center
                    if best.keypoints and len(best.keypoints) > 2:
                        nose = best.keypoints[2]
                        nx = (nose.x - 0.5) * 2.0
                        ny = (nose.y - 0.5) * 2.0
                    else:
                        nx = (bcx - 0.5) * 2.0
                        ny = (bcy - 0.5) * 2.0
                    nw = bbox.width / w
                    face_result = (nx, ny, nw)

            elif dnn_net is not None:
                # OpenCV DNN face detector — stable bounding boxes
                blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), (104, 177, 123))
                dnn_net.setInput(blob)
                detections = dnn_net.forward()
                best_conf = 0.0
                best_box = None
                for i in range(detections.shape[2]):
                    conf = float(detections[0, 0, i, 2])
                    if conf > 0.5 and conf > best_conf:
                        best_conf = conf
                        best_box = detections[0, 0, i, 3:7]
                if best_box is not None:
                    x1, y1, x2, y2 = best_box
                    cx = (x1 + x2) / 2.0
                    cy = (y1 + y2) / 2.0
                    bw = x2 - x1
                    nx = (cx - 0.5) * 2.0
                    ny = (cy - 0.5) * 2.0
                    face_result = (nx, ny, bw)

            elif face_detector is not None:
                face_result = detect_face_position(
                    face_detector, gray, w, h,
                    scale_factor=1.05,
                    min_neighbors=2,
                    min_face_size=20,
                )

            # --- Double-EMA + dead zone: smooth AND responsive ---
            if face_result is not None:
                nx, ny, nw = face_result
                # Stage 1: fast EMA (catches real movement quickly)
                s1_x += (nx - s1_x) * 0.5
                s1_y += (ny - s1_y) * 0.5
                s1_w += (nw - s1_w) * 0.5
                # Stage 2: smooth EMA (kills remaining jitter)
                s2_x += (s1_x - s2_x) * 0.25
                s2_y += (s1_y - s2_y) * 0.25
                s2_w += (s1_w - s2_w) * 0.25
                # Dead zone: only update tracking if movement is significant
                delta = abs(s2_x - prev_x) + abs(s2_y - prev_y)
                if delta > DEAD_ZONE:
                    tracking.update("detected", -s2_x, s2_y, s2_w)
                    prev_x, prev_y = s2_x, s2_y
                else:
                    tracking.update("detected", -prev_x, prev_y, s2_w)
                last_face_time = time.monotonic()

            else:
                # No face — try motion detection (hands, bodies, movement)
                motion_blobs = detect_all_motion_positions(
                    bg_subtractor, gray, w, h,
                    min_contour_area=args.min_contour_area, _mask_cache=mask,
                )
                now = time.monotonic()
                motion_target = centroid_tracker.update(motion_blobs, w, h)
                within_presence_timeout = (now - last_face_time) < args.presence_timeout

                if motion_target is not None and (motion_blobs or within_presence_timeout):
                    nx, ny, nw = motion_target
                    # Slower EMA for motion (noisier than face detection)
                    s1_x += (nx - s1_x) * 0.3
                    s1_y += (ny - s1_y) * 0.3
                    s2_x += (s1_x - s2_x) * 0.2
                    s2_y += (s1_y - s2_y) * 0.2
                    tracking.update("detected", -s2_x, s2_y, nw * 0.5)
                    prev_x, prev_y = s2_x, s2_y
                    if motion_blobs:
                        last_face_time = now
                elif within_presence_timeout:
                    pass  # hold last position
                else:
                    tracking.update("idle")

            elapsed = time.monotonic() - t0
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except Exception as e:
        print(f"[detector] Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        if mp_face_detector is not None:
            mp_face_detector.close()
        cleanup_source(source, use_webcam)
        print("[detector] Stopped", flush=True)


# ---------------------------------------------------------------------------
# Eye layer generation
# ---------------------------------------------------------------------------

class EyeLayers:
    """Pre-rendered eye layer surfaces with realistic detail."""

    def __init__(self, eye_color_name="blue"):
        colors = EYE_COLORS.get(eye_color_name, EYE_COLORS["blue"])
        size = SCREEN_SIZE

        # Check for PNG overrides
        assets_dir = os.path.join(os.path.dirname(__file__) or ".", "assets")
        self.sclera = self._try_load_png(assets_dir, "sclera.png") if os.path.isdir(assets_dir) else None
        self.iris = self._try_load_png(assets_dir, "iris.png") if os.path.isdir(assets_dir) else None
        self.pupil = self._try_load_png(assets_dir, "pupil.png") if os.path.isdir(assets_dir) else None

        if self.sclera is None:
            self.sclera = self._gen_sclera(size)
        if self.iris is None:
            self.iris = self._gen_iris(size, colors)
        if self.pupil is None:
            self.pupil = self._gen_pupil(size)

        self.lid_top = self._gen_eyelid(size, top=True)
        self.lid_bottom = self._gen_eyelid(size, top=False)
        self.gloss_overlay = self._gen_gloss_overlay(size)

        # Pre-cache scaled pupils for dilation (avoid per-frame allocation)
        base_w, base_h = self.pupil.get_size()
        self._pupil_cache = {}
        for scale_pct in range(50, 180, 2):  # 0.50x to 1.78x in 2% steps (covers full depth + surprise range)
            s = scale_pct / 100.0
            new_w = max(1, int(base_w * s))
            new_h = max(1, int(base_h * s))
            self._pupil_cache[scale_pct] = pygame.transform.smoothscale(self.pupil, (new_w, new_h))

    def get_dilated_pupil(self, dilation):
        """Get pupil surface scaled by dilation factor. Uses cached surfaces."""
        scale_pct = max(50, min(178, int(round(dilation * 100 / 2) * 2)))
        return self._pupil_cache.get(scale_pct, self.pupil)

    @staticmethod
    def _try_load_png(assets_dir, filename):
        path = os.path.join(assets_dir, filename)
        if os.path.isfile(path):
            try:
                surf = pygame.image.load(path).convert_alpha()
                print(f"[assets] Loaded {filename}", flush=True)
                return surf
            except pygame.error:
                pass
        return None

    @staticmethod
    def _gen_sclera(size):
        """3D-looking eyeball with spherical shading, glossy reflection, veins, and iris shadow."""
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        center = size // 2
        radius = int(size * SCLERA_RADIUS_RATIO)

        # Light source: upper-left
        light_x, light_y = -0.35, -0.4

        # --- Pass 1: Base sphere with directional lighting ---
        for r in range(radius, 0, -1):
            t = r / radius  # 1 at edge, 0 at center
            # Edge darkening (ambient occlusion)
            edge_darken = (1 - t) ** 0.5 * 0.15

            # For each ring, sample a representative angle to get shading
            # Use the overall spherical normal at this radius
            # Approximate: lighter toward light, darker away
            base_brightness = 0.92 - edge_darken

            red = max(0, min(255, int(base_brightness * 255)))
            green = max(0, min(255, int(base_brightness * 250)))
            blue = max(0, min(255, int(base_brightness * 245)))
            alpha = 255
            if r > radius - 6:
                alpha = max(0, min(255, int(255 * (radius - r + 6) / 6)))
            pygame.draw.circle(surf, (red, green, blue, alpha), (center, center), r)

        # --- Pass 2: Spherical shading overlay (light from upper-left) ---
        shade_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        for y_off in range(-radius, radius, 3):
            for x_off in range(-radius, radius, 3):
                dist = math.sqrt(x_off * x_off + y_off * y_off)
                if dist > radius:
                    continue
                # Normal on sphere surface
                nx_n = x_off / radius
                ny_n = y_off / radius
                # Dot product with light direction (normalized)
                dot = -(nx_n * light_x + ny_n * light_y)
                dot = max(0, min(1, (dot + 0.3) / 1.3))  # bias and clamp

                # Light side: brighten. Dark side: darken.
                if dot > 0.5:
                    # Highlight
                    brightness = int((dot - 0.5) * 2 * 50)
                    shade_surf.fill((255, 255, 255, brightness),
                                    (center + x_off, center + y_off, 3, 3))
                else:
                    # Shadow
                    darkness = int((0.5 - dot) * 2 * 80)
                    shade_surf.fill((20, 15, 30, darkness),
                                    (center + x_off, center + y_off, 3, 3))
        surf.blit(shade_surf, (0, 0))

        # --- Pass 3: Glossy specular reflection (large arc, upper-left) ---
        gloss_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        gloss_cx = center + int(light_x * radius * 0.4)
        gloss_cy = center + int(light_y * radius * 0.4)
        gloss_r = int(radius * 0.7)
        for r in range(gloss_r, 0, -1):
            t = r / gloss_r
            # Soft falloff
            alpha = max(0, min(90, int(90 * (1 - t ** 2) * t ** 0.3)))
            pygame.draw.circle(gloss_surf, (255, 255, 255, alpha), (gloss_cx, gloss_cy), r)
        surf.blit(gloss_surf, (0, 0))

        # --- Pass 4: Veins with subsurface glow ---
        random.seed(42)
        vein_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        glow_surf = pygame.Surface((size, size), pygame.SRCALPHA)

        for _ in range(18):
            angle = random.uniform(0, math.pi * 2)
            vein_len = random.uniform(radius * 0.18, radius * 0.55)
            start_r = radius * random.uniform(0.68, 0.95)
            segments = 12
            points = []
            for s in range(segments + 1):
                frac = s / segments
                r_pos = start_r - frac * vein_len
                a_wobble = angle + math.sin(frac * math.pi * 2.5) * 0.2
                px = center + int(math.cos(a_wobble) * r_pos)
                py = center + int(math.sin(a_wobble) * r_pos)
                points.append((px, py))

            for i in range(len(points) - 1):
                thickness = max(1, 3 - i // 3)
                alpha = max(20, 110 - i * 9)
                vein_surf.fill((0, 0, 0, 0))  # not needed per line
                pygame.draw.line(vein_surf, (170, 30, 30, alpha),
                                 points[i], points[i + 1], thickness)
                # Subsurface glow: pinkish blur around each vein segment
                mid_x = (points[i][0] + points[i + 1][0]) // 2
                mid_y = (points[i][1] + points[i + 1][1]) // 2
                for gr in range(12, 0, -2):
                    ga = max(0, min(15, int(15 * (1 - gr / 12))))
                    pygame.draw.circle(glow_surf, (180, 50, 50, ga), (mid_x, mid_y), gr)

            # Branches
            if len(points) > 4 and random.random() > 0.3:
                branch_angle = angle + random.uniform(-0.6, 0.6)
                prev_bp = points[3]
                for b in range(5):
                    frac = b / 5
                    br = start_r - 0.3 * vein_len - frac * vein_len * 0.4
                    bx = center + int(math.cos(branch_angle + frac * 0.2) * br)
                    by = center + int(math.sin(branch_angle + frac * 0.2) * br)
                    if b > 0:
                        pygame.draw.line(vein_surf, (160, 40, 40, max(15, 65 - b * 12)),
                                         prev_bp, (bx, by), max(1, 2 - b // 2))
                    prev_bp = (bx, by)

            # Fine capillary network
            if random.random() > 0.5 and len(points) > 6:
                for ci in range(2):
                    cp = points[5 + ci] if 5 + ci < len(points) else points[-1]
                    ca = angle + random.uniform(-1.0, 1.0)
                    cp2 = (cp[0] + int(math.cos(ca) * random.randint(8, 20)),
                           cp[1] + int(math.sin(ca) * random.randint(8, 20)))
                    pygame.draw.line(vein_surf, (155, 50, 50, 30), cp, cp2, 1)

        surf.blit(glow_surf, (0, 0))  # glow under veins
        surf.blit(vein_surf, (0, 0))
        random.seed()

        # --- Pass 5: Deep iris shadow (3D depth ring) ---
        iris_r = int(size * IRIS_RADIUS_RATIO)
        shadow_r = int(iris_r * 1.25)
        for r in range(shadow_r, iris_r, -1):
            t = (r - iris_r) / (shadow_r - iris_r)
            alpha = max(0, min(120, int(120 * (1 - t) ** 1.5)))
            pygame.draw.circle(surf, (15, 10, 20, alpha), (center, center), r)

        return surf.convert_alpha()

    @staticmethod
    def _gen_iris(size, colors):
        """Dense, organic iris with per-pixel gradient, crypts, fibers, and gloss."""
        iris_r = int(size * IRIS_RADIUS_RATIO)
        surf_size = iris_r * 2 + 30
        surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        center = surf_size // 2

        base = colors["base"]
        ring = colors["ring"]
        inner = colors["inner"]
        limbal = colors["limbal"]

        # AA limbal ring (thick dark border — sells 3D depth)
        pygame.gfxdraw.aacircle(surf, center, center, iris_r, limbal)
        pygame.gfxdraw.filled_circle(surf, center, center, iris_r, limbal)
        inner_edge = int(iris_r * 0.92)
        pygame.gfxdraw.filled_circle(surf, center, center, inner_edge, ring)

        # Per-pixel radial gradient with 5-stop smooth interpolation
        # Pre-compute color stops for hermite-like smoothness
        bright = tuple(min(255, inner[j] + 50) for j in range(3))
        glow = tuple(min(255, inner[j] + 80) for j in range(3))
        stops = [
            (0.00, ring),       # outer edge
            (0.15, tuple((ring[j] + base[j]) // 2 for j in range(3))),  # ring→base mid
            (0.35, base),       # mid iris
            (0.60, inner),      # inner iris
            (0.80, bright),     # bright center
            (1.00, glow),       # glow near pupil
        ]

        outer_r = int(iris_r * 0.90)
        inner_r_stop = int(iris_r * 0.22)
        total_range = outer_r - inner_r_stop
        random.seed(77)
        for r in range(outer_r, inner_r_stop, -1):
            t = 1.0 - (r - inner_r_stop) / total_range  # 0=outer, 1=inner
            # Find surrounding color stops
            c = list(stops[0][1])
            for si in range(len(stops) - 1):
                t0, c0 = stops[si]
                t1, c1 = stops[si + 1]
                if t0 <= t <= t1:
                    lt = (t - t0) / (t1 - t0)
                    # Smoothstep interpolation (hermite) for ultra-smooth blending
                    lt = lt * lt * (3 - 2 * lt)
                    c = [c0[j] + (c1[j] - c0[j]) * lt for j in range(3)]
                    break
            # Very subtle noise — just enough to prevent digital banding
            noise = random.uniform(-3, 3)
            c = tuple(max(0, min(255, int(v + noise))) for v in c)
            pygame.draw.circle(surf, c, (center, center), r)
        random.seed()

        # Iris crypts — dark radial furrows for depth
        random.seed(13)
        crypt_surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        for i in range(30):
            angle = (i / 30) * math.pi * 2 + random.uniform(-0.08, 0.08)
            r_start = random.uniform(iris_r * 0.30, iris_r * 0.45)
            r_end = random.uniform(iris_r * 0.65, iris_r * 0.85)
            segments = 8
            points = []
            for s in range(segments + 1):
                frac = s / segments
                r_pos = r_start + frac * (r_end - r_start)
                a_off = angle + math.sin(frac * math.pi * 2) * 0.12
                px = center + int(math.cos(a_off) * r_pos)
                py = center + int(math.sin(a_off) * r_pos)
                points.append((px, py))
            # Wider, darker furrows
            alpha = random.randint(30, 70)
            for s in range(len(points) - 1):
                pygame.draw.line(crypt_surf, (0, 0, 0, alpha), points[s], points[s + 1],
                                 random.choice([2, 3, 3, 4]))
        surf.blit(crypt_surf, (0, 0))
        random.seed()

        # Dense radial fibers (100+ for organic look)
        random.seed(7)
        for i in range(100):
            angle = (i / 100) * math.pi * 2 + random.uniform(-0.04, 0.04)
            inner_start = random.uniform(iris_r * 0.15, iris_r * 0.28)
            outer_end = random.uniform(iris_r * 0.55, iris_r * 0.88)
            segments = 8
            points = []
            for s in range(segments + 1):
                frac = s / segments
                r_pos = inner_start + frac * (outer_end - inner_start)
                a_off = angle + math.sin(frac * math.pi * 3) * 0.07
                px = center + int(math.cos(a_off) * r_pos)
                py = center + int(math.sin(a_off) * r_pos)
                points.append((px, py))

            thickness = random.choice([1, 1, 1, 2, 2])
            color_shift = random.randint(-40, 40)
            streak_color = (
                max(0, min(255, base[0] + color_shift + random.randint(-12, 12))),
                max(0, min(255, base[1] + color_shift + random.randint(-12, 12))),
                max(0, min(255, base[2] + color_shift + random.randint(-12, 12))),
                random.randint(50, 170),
            )
            for s in range(len(points) - 1):
                pygame.draw.line(surf, streak_color, points[s], points[s + 1], thickness)

        # Bright accent fibers (fewer, bolder)
        for i in range(25):
            angle = random.uniform(0, math.pi * 2)
            r_start = random.uniform(iris_r * 0.22, iris_r * 0.38)
            r_end = random.uniform(iris_r * 0.55, iris_r * 0.82)
            sx = center + int(math.cos(angle) * r_start)
            sy = center + int(math.sin(angle) * r_start)
            ex = center + int(math.cos(angle + 0.03) * r_end)
            ey = center + int(math.sin(angle + 0.03) * r_end)
            bright = tuple(min(255, inner[j] + 45 + random.randint(0, 25)) for j in range(3))
            pygame.draw.line(surf, (*bright, random.randint(35, 100)), (sx, sy), (ex, ey), 2)
        random.seed()

        # Inner glow (bright halo around pupil opening)
        glow_r = int(iris_r * 0.28)
        for r in range(glow_r, 0, -1):
            t = r / glow_r
            alpha = max(0, min(80, int(80 * (1 - t) ** 0.6)))
            bright = tuple(min(255, inner[j] + 55) for j in range(3))
            pygame.draw.circle(surf, (*bright, alpha), (center, center), r)

        # Wet gloss reflection across iris
        gloss_surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        gloss_cx = center - int(iris_r * 0.2)
        gloss_cy = center - int(iris_r * 0.3)
        for r in range(int(iris_r * 0.45), 0, -1):
            t = r / (iris_r * 0.45)
            alpha = max(0, min(45, int(45 * (1 - t ** 2))))
            pygame.draw.circle(gloss_surf, (255, 255, 255, alpha), (gloss_cx, gloss_cy), r)
        surf.blit(gloss_surf, (0, 0))

        return surf.convert_alpha()

    @staticmethod
    def _gen_pupil(size):
        """Pupil with soft gradient edge, glow halo, and dual specular highlights."""
        pupil_r = int(size * PUPIL_RADIUS_RATIO)
        # Extra space for glow halo
        margin = int(pupil_r * 0.6)
        surf_size = (pupil_r + margin) * 2
        surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        center = surf_size // 2

        # Glow halo (dark-to-transparent ring around pupil)
        halo_r = int(pupil_r * 1.4)
        for r in range(halo_r, pupil_r, -1):
            t = (r - pupil_r) / (halo_r - pupil_r)
            alpha = max(0, min(100, int(100 * (1 - t) ** 2)))
            pygame.draw.circle(surf, (5, 5, 5, alpha), (center, center), r)

        # Soft gradient edge (not hard circle)
        for r in range(pupil_r, 0, -1):
            t = r / pupil_r
            if t > 0.85:
                # Soft edge fade
                edge_t = (t - 0.85) / 0.15
                alpha = max(0, min(255, int(255 * (1 - edge_t))))
            else:
                alpha = 255
            pygame.draw.circle(surf, (5, 5, 5, alpha), (center, center), r)

        # Primary specular highlight (upper-left, larger, with glow)
        hl_r = int(size * HIGHLIGHT_RADIUS_RATIO)
        hx = center - int(pupil_r * 0.28)
        hy = center - int(pupil_r * 0.28)
        # Glow around highlight
        for r in range(hl_r + 6, hl_r, -1):
            t = (r - hl_r) / 6
            pygame.draw.circle(surf, (255, 255, 255, int(80 * (1 - t))), (hx, hy), r)
        pygame.draw.circle(surf, (255, 255, 255, 220), (hx, hy), hl_r)

        # Secondary specular highlight (lower-right, smaller, dimmer)
        hl2_r = max(2, hl_r // 2)
        hx2 = center + int(pupil_r * 0.2)
        hy2 = center + int(pupil_r * 0.25)
        pygame.draw.circle(surf, (255, 255, 255, 100), (hx2, hy2), hl2_r)

        return surf.convert_alpha()

    @staticmethod
    def _gen_gloss_overlay(size):
        """Full-eye wet gloss — the single biggest realism improvement."""
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        center = size // 2
        eye_r = int(size * SCLERA_RADIUS_RATIO)

        # Large glossy arc — upper-left (like a window reflection)
        gloss_cx = center - int(eye_r * 0.25)
        gloss_cy = center - int(eye_r * 0.30)
        gloss_r = int(eye_r * 0.85)
        for r in range(gloss_r, 0, -1):
            t = r / gloss_r
            # Soft arc falloff — strong at center, fades at edges
            alpha = max(0, min(55, int(55 * (1 - t ** 1.8) * (t ** 0.15))))
            pygame.draw.circle(surf, (255, 255, 255, alpha), (gloss_cx, gloss_cy), r)

        # Secondary gloss — lower-right edge reflection (subtle)
        g2_cx = center + int(eye_r * 0.3)
        g2_cy = center + int(eye_r * 0.35)
        g2_r = int(eye_r * 0.3)
        for r in range(g2_r, 0, -1):
            t = r / g2_r
            alpha = max(0, min(20, int(20 * (1 - t ** 2))))
            pygame.draw.circle(surf, (255, 255, 255, alpha), (g2_cx, g2_cy), r)

        # Thin bright rim along bottom edge (tear film meniscus)
        for angle_deg in range(140, 400):
            angle = math.radians(angle_deg)
            rim_r = eye_r - 3
            px = center + int(math.cos(angle) * rim_r)
            py = center + int(math.sin(angle) * rim_r)
            # Stronger at bottom, fading at sides
            t = (math.sin(angle) + 1) / 2  # 0 at top, 1 at bottom
            alpha = max(0, min(30, int(30 * t ** 2)))
            if 0 <= px < size and 0 <= py < size:
                surf.fill((255, 255, 255, alpha), (px, py, 2, 2))

        return surf.convert_alpha()

    @staticmethod
    def _gen_eyelid(size, top=True):
        """Eyelid with skin gradient, crease line, and eyelashes."""
        surf = pygame.Surface((size, size // 2 + 60), pygame.SRCALPHA)
        w = size
        h = size // 2 + 60

        # Skin-tone gradient instead of flat color
        for y in range(h):
            t = y / h if top else (1 - y / h)
            # Darker at edge, slightly lighter toward opening
            brightness = max(0, min(40, int(5 + t * 35)))
            surf.fill((brightness, int(brightness * 0.7), int(brightness * 0.55), 255),
                       (0, y, w, 1))

        # Cut curved opening
        if top:
            ellipse_rect = pygame.Rect(-w * 0.1, h - int(h * 0.35), int(w * 1.2), int(h * 0.7))
            pygame.draw.ellipse(surf, (0, 0, 0, 0), ellipse_rect)

            # Crease line above the opening
            crease_y = h - int(h * 0.42)
            for x in range(int(w * 0.15), int(w * 0.85)):
                t = (x - w * 0.15) / (w * 0.7)
                cy = crease_y - int(math.sin(t * math.pi) * h * 0.06)
                surf.fill((0, 0, 0, 40), (x, cy, 1, 2))

            # Eyelashes along top lid edge
            random.seed(99)
            lid_center_y = h - int(h * 0.35) + int(h * 0.35)
            for i in range(35):
                t = 0.12 + (i / 35) * 0.76
                lx = int(w * t)
                # Follow ellipse curve for lash base
                ex = (lx - w * 0.5) / (w * 0.6)
                curve_y = lid_center_y - int(math.sqrt(max(0, 1 - ex * ex)) * h * 0.32)
                # Lash angle and length
                lash_angle = math.pi * 1.3 + (t - 0.5) * 0.6 + random.uniform(-0.15, 0.15)
                lash_len = random.randint(12, 30)
                lash_curve = random.uniform(-0.2, 0.2)
                # Draw curved lash with 3 segments
                prev = (lx, curve_y)
                for seg in range(3):
                    frac = (seg + 1) / 3
                    a = lash_angle + lash_curve * frac
                    nx = prev[0] + int(math.cos(a) * lash_len / 3)
                    ny = prev[1] + int(math.sin(a) * lash_len / 3)
                    thickness = 2 if seg == 0 else 1
                    pygame.draw.line(surf, (0, 0, 0, 200), prev, (nx, ny), thickness)
                    prev = (nx, ny)
            random.seed()
        else:
            pygame.draw.ellipse(
                surf, (0, 0, 0, 0),
                pygame.Rect(-w * 0.1, -int(h * 0.35), int(w * 1.2), int(h * 0.7))
            )

        return surf.convert_alpha()


# ---------------------------------------------------------------------------
# Animation state
# ---------------------------------------------------------------------------

class EyeAnimation:
    """Manages smooth interpolation with micro-saccades, pupil dilation,
    curiosity glances, and double-blink behavior."""

    def __init__(self, lerp_speed=DEFAULT_LERP_SPEED):
        self.current_x = 0.0
        self.current_y = 0.0
        self.target_x = 0.0
        self.target_y = 0.0
        self.lerp_speed = lerp_speed

        # Micro-saccades
        self.micro_saccade_x = 0.0
        self.micro_saccade_y = 0.0
        self._saccade_timer = 0.0

        # Pupil dilation
        self.pupil_dilation = PUPIL_DILATION_BASE
        self._dilation_target = PUPIL_DILATION_BASE
        self._surprise_amount = 0.0  # additive surprise spike, decays independently
        self._breathe_time = random.uniform(0, 100)

        # Idle drift
        self._drift_time = random.uniform(0, 100)

        # Idle curiosity glances
        self._curiosity_timer = time.monotonic() + random.uniform(IDLE_CURIOSITY_MIN, IDLE_CURIOSITY_MAX)
        self._curiosity_target = None
        self._curiosity_return_time = 0.0

        # Blink
        self.blink_progress = 0.0
        self._blink_phase = "none"
        self._blink_timer = 0.0
        self._next_blink = time.monotonic() + random.uniform(IDLE_BLINK_MIN, IDLE_BLINK_MAX)
        self._pending_double_blink = False

        # Proximity-based scaling (iris + pupil grow when person is closer)
        # face_w ~0.05 = far away, ~0.5 = very close
        self.proximity_scale = 1.0        # current smooth scale
        self._proximity_target = 1.0

        # State tracking
        self._current_state = "idle"
        self._prev_state = "idle"
        self._state_changed_at = 0.0

    def update(self, state, face_x, face_y, dt, face_w=0.0, audio=None):
        now = time.monotonic()

        # Detect state transitions
        self._prev_state = self._current_state
        if state != self._current_state:
            self._current_state = state
            self._state_changed_at = now
            # Surprise dilation on first detection (additive, decays separately)
            if state == "detected":
                self._surprise_amount = 0.25

        # Set target
        if state == "detected":
            self.target_x = face_x
            self.target_y = face_y
            speed = self.lerp_speed
        else:
            # Idle: look toward sound if audio available, else center
            if audio is not None:
                beat, vol, startle, direction, _ = audio
                if vol > 0.02:
                    # Look toward sound source
                    self.target_x = direction * 0.7
                else:
                    self.target_x = 0.0
            else:
                self.target_x = 0.0
            self.target_y = 0.0
            speed = IDLE_LERP_SPEED
            self._dilation_target = PUPIL_DILATION_BASE

        # Depth-reactive effects — face_w (face width in frame) = distance proxy
        # Bigger face = closer person → bigger pupil, larger iris
        if state == "detected" and face_w > 0.01:
            clamped_w = max(0.05, min(0.6, face_w))
            t = (clamped_w - 0.05) / 0.55  # 0 = far, 1 = very close

            # Proximity scale: iris/pupil SIZE grows as person approaches
            # Far (0.05) → 0.80x, Close (0.6) → 1.35x
            self._proximity_target = 0.80 + t * 0.55

            # Depth dilation: SET directly (not max — fixes bug where pupil never shrinks)
            # Far → 0.60 (constricted), Medium → 1.10, Close → 1.60 (wide dilated)
            depth_dilation = 0.60 + t * 1.00
            # Surprise spike decays independently on top of depth
            self._surprise_amount *= max(0.0, 1.0 - PUPIL_DILATION_DECAY * dt)
            self._dilation_target = depth_dilation + self._surprise_amount
        else:
            self._proximity_target = 1.0
            self._dilation_target = PUPIL_DILATION_BASE
            self._surprise_amount *= max(0.0, 1.0 - PUPIL_DILATION_DECAY * dt)
        # Slow smooth lerp for proximity (natural, not jumpy)
        self.proximity_scale += (self._proximity_target - self.proximity_scale) * min(1.0, 0.8 * dt)

        # Exponential lerp
        factor = min(1.0, speed * dt)
        self.current_x += (self.target_x - self.current_x) * factor
        self.current_y += (self.target_y - self.current_y) * factor

        # Micro-saccades
        self._saccade_timer += dt
        if self._saccade_timer >= SACCADE_INTERVAL:
            self._saccade_timer = 0.0
            if random.random() < SACCADE_LARGE_CHANCE:
                mag = SACCADE_LARGE
            else:
                mag = SACCADE_SMALL
            self.micro_saccade_x = random.uniform(-mag, mag)
            self.micro_saccade_y = random.uniform(-mag, mag)
        else:
            # Decay saccade toward zero between intervals (~125ms fade)
            decay = min(1.0, 8.0 * dt)
            self.micro_saccade_x *= (1.0 - decay)
            self.micro_saccade_y *= (1.0 - decay)

        # Pupil dilation (breathing + beat pulse + surprise)
        self._breathe_time += dt
        breathe = math.sin(self._breathe_time * PUPIL_DILATION_BREATHE_FREQ * math.pi * 2) * PUPIL_DILATION_BREATHE_AMP

        # Audio beat pulse — pupil throbs with bass
        beat_pulse = 0.0
        if audio is not None:
            beat, vol, startle_trigger, direction, _ = audio
            beat_pulse = beat * 0.40  # ±40% dilation on strong beats

            # Startle reaction — loud sudden sound
            if startle_trigger and self._surprise_amount < 0.1:
                self._surprise_amount = 0.5  # big spike
                # Force a blink
                if self._blink_phase == "none":
                    self._blink_phase = "closing"
                    self._blink_timer = 0.0

        self.pupil_dilation += (self._dilation_target + breathe + beat_pulse - self.pupil_dilation) * min(1.0, 2.5 * dt)

        # Blink
        self._update_blink(dt, state)

    def _update_blink(self, dt, state):
        now = time.monotonic()

        if self._blink_phase == "none":
            if now >= self._next_blink:
                self._blink_phase = "closing"
                self._blink_timer = 0.0
                # Decide if this will be a double-blink
                self._pending_double_blink = random.random() < DOUBLE_BLINK_CHANCE
        elif self._blink_phase == "closing":
            self._blink_timer += dt
            self.blink_progress = min(1.0, self._blink_timer / BLINK_CLOSE_DURATION)
            if self.blink_progress >= 1.0:
                self._blink_phase = "pausing"
                self._blink_timer = 0.0
        elif self._blink_phase == "pausing":
            self._blink_timer += dt
            if self._blink_timer >= BLINK_PAUSE_DURATION:
                self._blink_phase = "opening"
                self._blink_timer = 0.0
        elif self._blink_phase == "opening":
            self._blink_timer += dt
            self.blink_progress = max(0.0, 1.0 - self._blink_timer / BLINK_OPEN_DURATION)
            if self.blink_progress <= 0.0:
                if self._pending_double_blink:
                    # Trigger second blink immediately
                    self._pending_double_blink = False
                    self._blink_phase = "closing"
                    self._blink_timer = 0.0
                else:
                    self._blink_phase = "none"
                    if state == "detected":
                        interval = random.uniform(TRACK_BLINK_MIN, TRACK_BLINK_MAX)
                    else:
                        interval = random.uniform(IDLE_BLINK_MIN, IDLE_BLINK_MAX)
                    self._next_blink = now + interval


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _radial_clamp(dx, dy, max_r):
    """Clamp (dx, dy) offset to a circular radius. Prevents square movement."""
    length = math.sqrt(dx * dx + dy * dy)
    if length > max_r and length > 0:
        dx = dx / length * max_r
        dy = dy / length * max_r
    return dx, dy


def render_eye(surface, layers, anim, args, is_left_eye=True):
    """Render a single eye with parallax, micro-saccades, and pupil dilation."""
    surface.fill((0, 0, 0))

    cx = SCREEN_SIZE // 2
    cy = SCREEN_SIZE // 2

    # Raw offsets from tracking
    raw_x = anim.current_x * args.max_offset
    raw_y = anim.current_y * args.max_offset

    # Micro-saccade jitter (applied to all layers uniformly)
    jitter_x = anim.micro_saccade_x * SACCADE_PIXEL_SCALE
    jitter_y = anim.micro_saccade_y * SACCADE_PIXEL_SCALE

    # Cross-eye offset
    eye_shift = CROSS_EYE_OFFSET if is_left_eye else -CROSS_EYE_OFFSET

    # --- Sclera (radial clamped) ---
    s_dx, s_dy = _radial_clamp(
        raw_x * args.sclera_parallax, raw_y * args.sclera_parallax,
        args.max_offset * args.sclera_parallax
    )
    sw, sh = layers.sclera.get_size()
    sx = int(cx - sw // 2 + s_dx + jitter_x)
    sy = int(cy - sh // 2 + s_dy + jitter_y)
    surface.blit(layers.sclera, (sx, sy))

    # --- Iris (radial clamped + proximity scaled) ---
    i_dx, i_dy = _radial_clamp(
        raw_x * args.iris_parallax + eye_shift,
        raw_y * args.iris_parallax,
        args.max_offset * args.iris_parallax
    )
    prox = anim.proximity_scale
    if abs(prox - 1.0) > 0.005:
        iw_base, ih_base = layers.iris.get_size()
        new_iw = max(1, int(iw_base * prox))
        new_ih = max(1, int(ih_base * prox))
        iris_surf = pygame.transform.smoothscale(layers.iris, (new_iw, new_ih))
    else:
        iris_surf = layers.iris
    iw, ih = iris_surf.get_size()
    ix = int(cx - iw // 2 + i_dx + jitter_x)
    iy = int(cy - ih // 2 + i_dy + jitter_y)
    surface.blit(iris_surf, (ix, iy))

    # --- Pupil (radial clamped + dilation + proximity) ---
    p_dx, p_dy = _radial_clamp(
        raw_x * args.pupil_parallax + eye_shift,
        raw_y * args.pupil_parallax,
        args.max_offset * args.pupil_parallax
    )
    combined_dilation = anim.pupil_dilation * prox
    dilated_pupil = layers.get_dilated_pupil(combined_dilation)
    pw, ph = dilated_pupil.get_size()
    px = int(cx - pw // 2 + p_dx + jitter_x)
    py = int(cy - ph // 2 + p_dy + jitter_y)
    surface.blit(dilated_pupil, (px, py))

    # --- Full-eye wet gloss overlay (after all layers, before eyelids) ---
    surface.blit(layers.gloss_overlay, (0, 0))

    # --- Eyelids ---
    if anim.blink_progress > 0.01:
        lid_travel = int(anim.blink_progress * (SCREEN_SIZE // 2 + 30))
        _, lh = layers.lid_top.get_size()
        surface.blit(layers.lid_top, (0, -lh + lid_travel))
        _, lh2 = layers.lid_bottom.get_size()
        surface.blit(layers.lid_bottom, (0, SCREEN_SIZE - lid_travel))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    running = True

    def shutdown(signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    if sys.platform == "linux":
        os.environ.setdefault("SDL_VIDEODRIVER", "wayland")
    pygame.init()
    pygame.mouse.set_visible(False)

    dual_eye = not args.single_eye
    if dual_eye:
        window_size = (SCREEN_SIZE * 2, SCREEN_SIZE)
    else:
        window_size = (SCREEN_SIZE, SCREEN_SIZE)
    flags = 0 if args.windowed else (pygame.FULLSCREEN | pygame.NOFRAME)

    try:
        screen = pygame.display.set_mode(window_size, flags)
    except pygame.error:
        os.environ["SDL_VIDEODRIVER"] = "x11"
        screen = pygame.display.set_mode(window_size, flags)

    pygame.display.set_caption("raspieyes")
    print(f"[renderer] Window: {window_size[0]}x{window_size[1]}, dual={dual_eye}", flush=True)

    print(f"[renderer] Generating eye layers (color: {args.eye_color})...", flush=True)
    layers = EyeLayers(args.eye_color)
    print("[renderer] Layers ready", flush=True)

    tracking = TrackingState(args.presence_timeout)
    audio_st = AudioState()

    use_mouse = getattr(args, "mouse", False)
    if use_mouse:
        print("[renderer] Mouse tracking mode — move mouse over window", flush=True)
    elif not args.no_camera:
        det_thread = threading.Thread(target=detection_loop, args=(tracking, args), daemon=True)
        det_thread.start()
        print("[renderer] Detection thread started", flush=True)
    else:
        print("[renderer] Camera disabled, idle mode only", flush=True)

    # Start audio thread (microphone beat detection, startle, direction)
    aud_thread = threading.Thread(target=audio_thread, args=(audio_st,), daemon=True)
    aud_thread.start()

    anim = EyeAnimation(lerp_speed=args.lerp_speed)
    clock = pygame.time.Clock()

    if dual_eye:
        left_surf = screen.subsurface((0, 0, SCREEN_SIZE, SCREEN_SIZE))
        right_surf = screen.subsurface((SCREEN_SIZE, 0, SCREEN_SIZE, SCREEN_SIZE))

    print(f"[renderer] Render loop at {args.fps} FPS", flush=True)

    while running:
        dt = clock.tick(args.fps) / 1000.0
        dt = min(dt, 0.1)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False

        # Mouse tracking: read mouse position directly
        if use_mouse:
            mx, my = pygame.mouse.get_pos()
            # Normalize relative to window center [-1, 1]
            nx = (mx / window_size[0] - 0.5) * 2.0
            ny = (my / window_size[1] - 0.5) * 2.0
            # Simulate distance based on mouse distance from center
            dist = math.sqrt(nx * nx + ny * ny)
            nw = max(0.05, 0.4 - dist * 0.2)  # closer to center = "closer" person
            tracking.update("detected", nx, ny, nw)

        state, fx, fy, fw, ts = tracking.get()
        audio_data = audio_st.get()
        anim.update(state, fx, fy, dt, face_w=fw, audio=audio_data)

        if dual_eye:
            render_eye(left_surf, layers, anim, args, is_left_eye=True)
            render_eye(right_surf, layers, anim, args, is_left_eye=False)
        else:
            render_eye(screen, layers, anim, args, is_left_eye=True)

        pygame.display.flip()

    pygame.quit()
    print("[renderer] Stopped", flush=True)


if __name__ == "__main__":
    main()
