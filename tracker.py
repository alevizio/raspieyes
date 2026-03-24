#!/usr/bin/env python3
"""
raspieyes — persistent centroid tracker with Kalman prediction

Maintains object identity across frames by matching centroids via
Euclidean distance. Each tracked object has a Kalman filter for
smooth position prediction through detection gaps.

Used by eye_renderer.py's detection loop.
"""

import math
import time

import cv2
import numpy as np


class KalmanPoint:
    """2D Kalman filter tracking position + velocity."""

    def __init__(self, x, y, process_noise=0.05, measurement_noise=0.5):
        # State: [x, y, vx, vy], Measurement: [x, y]
        self.kf = cv2.KalmanFilter(4, 2)

        # Transition matrix (constant velocity model)
        self.kf.transitionMatrix = np.array([
            [1, 0, 1, 0],
            [0, 1, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ], dtype=np.float32)

        # Measurement matrix (we observe x, y)
        self.kf.measurementMatrix = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ], dtype=np.float32)

        # Process noise (how much we expect motion to change)
        self.kf.processNoiseCov = np.eye(4, dtype=np.float32) * process_noise

        # Measurement noise (how noisy the detections are)
        self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * measurement_noise

        # Initial state
        self.kf.statePre = np.array([x, y, 0, 0], dtype=np.float32)
        self.kf.statePost = np.array([x, y, 0, 0], dtype=np.float32)
        self.kf.errorCovPost = np.eye(4, dtype=np.float32)

    def predict(self):
        """Predict next position. Returns (x, y)."""
        state = self.kf.predict()
        return float(state[0]), float(state[1])

    def correct(self, x, y):
        """Update with actual measurement. Returns corrected (x, y)."""
        measurement = np.array([x, y], dtype=np.float32)
        state = self.kf.correct(measurement)
        return float(state[0]), float(state[1])

    def get_position(self):
        """Get current estimated position."""
        return float(self.kf.statePost[0]), float(self.kf.statePost[1])


class TrackedObject:
    """A single tracked object with position history and Kalman filter."""

    def __init__(self, obj_id, cx, cy, w, process_noise=0.05, measurement_noise=0.5):
        self.obj_id = obj_id
        self.cx = cx  # raw centroid x (pixels)
        self.cy = cy  # raw centroid y (pixels)
        self.w = w    # bounding box width (pixels)
        self.kalman = KalmanPoint(cx, cy, process_noise, measurement_noise)
        self.smooth_x = cx  # kalman-smoothed position
        self.smooth_y = cy
        self.disappeared = 0  # frames since last detection
        self.created_at = time.monotonic()
        self.last_seen_at = time.monotonic()

    def update(self, cx, cy, w):
        """Update with new detection."""
        self.cx = cx
        self.cy = cy
        self.w = w
        self.disappeared = 0
        self.last_seen_at = time.monotonic()
        # Kalman correct
        self.kalman.predict()
        sx, sy = self.kalman.correct(cx, cy)
        self.smooth_x = sx
        self.smooth_y = sy

    def predict(self):
        """Predict position when no detection available."""
        self.disappeared += 1
        sx, sy = self.kalman.predict()
        self.smooth_x = sx
        self.smooth_y = sy

    @property
    def age(self):
        return time.monotonic() - self.created_at

    @property
    def time_since_seen(self):
        return time.monotonic() - self.last_seen_at


class CentroidTracker:
    """Persistent multi-object tracker with centroid matching and Kalman filtering.

    Maintains object identity across frames. Returns the primary target
    (closest to frame center) for eye parallax tracking.
    """

    def __init__(self, max_disappeared=75, max_distance=180,
                 process_noise=0.05, measurement_noise=0.5,
                 presence_timeout=15.0):
        """
        Args:
            max_disappeared: frames before deregistering a lost track
            max_distance: max pixel distance for centroid matching
            process_noise: Kalman process noise (lower = smoother)
            measurement_noise: Kalman measurement noise (lower = trust detections more)
            presence_timeout: seconds to hold last position after all tracks lost
        """
        self._next_id = 0
        self._objects = {}  # id → TrackedObject
        self._max_disappeared = max_disappeared
        self._max_distance = max_distance
        self._process_noise = process_noise
        self._measurement_noise = measurement_noise
        self._presence_timeout = presence_timeout

        # Last known primary target (for presence memory)
        self._last_target_nx = 0.0
        self._last_target_ny = 0.0
        self._last_target_nw = 0.0
        self._last_target_time = 0.0
        self._had_target = False

    def _register(self, cx, cy, w):
        obj = TrackedObject(
            self._next_id, cx, cy, w,
            self._process_noise, self._measurement_noise,
        )
        self._objects[self._next_id] = obj
        self._next_id += 1
        return obj

    def _deregister(self, obj_id):
        del self._objects[obj_id]

    def update(self, detections, frame_width, frame_height):
        """Process new detections and return primary target.

        Args:
            detections: list of (cx, cy, w) in pixel coordinates
            frame_width: frame width for normalization
            frame_height: frame height for normalization

        Returns:
            (nx, ny, nw) normalized position of primary target, or None
        """
        # --- No detections: predict all, deregister old ---
        if len(detections) == 0:
            for obj_id in list(self._objects.keys()):
                obj = self._objects[obj_id]
                obj.predict()
                if obj.disappeared > self._max_disappeared:
                    self._deregister(obj_id)
            return self._get_primary_target(frame_width, frame_height)

        # --- No existing objects: register all detections ---
        if len(self._objects) == 0:
            for (cx, cy, w) in detections:
                self._register(cx, cy, w)
            return self._get_primary_target(frame_width, frame_height)

        # --- Match detections to existing objects ---
        obj_ids = list(self._objects.keys())
        obj_centroids = [(self._objects[oid].smooth_x, self._objects[oid].smooth_y) for oid in obj_ids]

        # Build distance matrix
        n_objects = len(obj_ids)
        n_detections = len(detections)
        distances = np.zeros((n_objects, n_detections), dtype=np.float32)

        for i, (ox, oy) in enumerate(obj_centroids):
            for j, (dx, dy, _) in enumerate(detections):
                distances[i, j] = math.sqrt((ox - dx) ** 2 + (oy - dy) ** 2)

        # Greedy matching: for each object, find nearest unmatched detection
        matched_objects = set()
        matched_detections = set()

        # Sort by distance (smallest first)
        flat_indices = np.argsort(distances, axis=None)
        for flat_idx in flat_indices:
            i = int(flat_idx // n_detections)
            j = int(flat_idx % n_detections)

            if i in matched_objects or j in matched_detections:
                continue
            if distances[i, j] > self._max_distance:
                continue

            # Match!
            obj_id = obj_ids[i]
            cx, cy, w = detections[j]
            self._objects[obj_id].update(cx, cy, w)
            matched_objects.add(i)
            matched_detections.add(j)

        # Unmatched objects: predict (they may reappear)
        for i in range(n_objects):
            if i not in matched_objects:
                obj_id = obj_ids[i]
                obj = self._objects[obj_id]
                obj.predict()
                if obj.disappeared > self._max_disappeared:
                    self._deregister(obj_id)

        # Unmatched detections: register as new objects
        for j in range(n_detections):
            if j not in matched_detections:
                cx, cy, w = detections[j]
                self._register(cx, cy, w)

        return self._get_primary_target(frame_width, frame_height)

    def _get_primary_target(self, frame_width, frame_height):
        """Select the primary tracking target and return normalized position.

        Priority: closest to frame center, with tie-breaking by age (older = preferred).
        """
        if not self._objects:
            return None

        center_x = frame_width / 2
        center_y = frame_height / 2

        # Score: closer to center + older tracks preferred
        best_obj = None
        best_score = float("inf")

        for obj in self._objects.values():
            if obj.disappeared > 10:  # skip objects missing for many frames
                continue
            dist_to_center = math.sqrt(
                (obj.smooth_x - center_x) ** 2 + (obj.smooth_y - center_y) ** 2
            )
            # Bonus for older tracks (divide distance by sqrt of age)
            age_factor = max(1.0, obj.age) ** 0.3
            score = dist_to_center / age_factor
            if score < best_score:
                best_score = score
                best_obj = obj

        if best_obj is None:
            return None

        # Normalize to [-1, 1]
        nx = (best_obj.smooth_x / frame_width - 0.5) * 2.0
        ny = (best_obj.smooth_y / frame_height - 0.5) * 2.0
        nw = best_obj.w / frame_width

        # Save as last known target
        self._last_target_nx = nx
        self._last_target_ny = ny
        self._last_target_nw = nw
        self._last_target_time = time.monotonic()
        self._had_target = True

        return (nx, ny, nw)

    def has_recent_target(self):
        """True if we had a target within the presence timeout window."""
        if not self._had_target:
            return False
        return (time.monotonic() - self._last_target_time) < self._presence_timeout

    @property
    def last_target(self):
        """Last known target position (nx, ny, nw)."""
        return (self._last_target_nx, self._last_target_ny, self._last_target_nw)

    @property
    def active_count(self):
        """Number of actively tracked objects."""
        return sum(1 for obj in self._objects.values() if obj.disappeared <= 10)
