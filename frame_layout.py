"""
Multi-eye frame layout and per-eye gaze convergence.

Describes a physical frame populated with multiple round displays of varying
sizes and positions, plus the camera(s) that observe viewers in front of it.
Converts the camera's normalized face coordinates into a real-world (X, Y, Z)
target position, then computes each eye's own normalized gaze vector so that
every eye on the frame physically converges on the same viewer.

Coordinate system (millimeters, frame-space):
    origin = center of the frame, looking out at the viewer
    +x = right (as you face the frame)
    +y = down
    +z = out of the frame toward the viewer

JSON schema (see frame_layout.json for an example):

    {
      "frame": {"width_mm": 1800, "height_mm": 1200},
      "cameras": [
        {
          "id": "top_center",
          "x_mm": 0, "y_mm": -600, "z_mm": 0,
          "hfov_deg": 102, "vfov_deg": 67
        }
      ],
      "eyes": [
        {
          "id": "hero_left",
          "x_mm": -400, "y_mm": 0,
          "diameter_mm": 127,
          "render_size_px": 1080,
          "display_type": "hdmi",
          "device": "HDMI-A-1",
          "is_left_eye": true
        },
        ...
      ]
    }

Notes:
- `display_type` is "hdmi" or "spi". For "spi" the renderer will push frames
  via spi_display.py (stubbed until real hardware lands).
- `render_size_px` is the native pixel resolution of the round display.
- Gaze math treats `z_mm` of eyes as 0 (all eyes live on the frame plane).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Optional


# Assumed distance at which face-width proxy nw==0.25 (a typical "person 1m
# away" value from the existing detector). Used to convert the nw depth proxy
# into a world Z estimate. Empirical — tune against your camera.
DEPTH_CALIBRATION_MM = 1000.0
DEPTH_CALIBRATION_NW = 0.25

# Clamp viewer Z so a missing/garbage nw doesn't send gaze to infinity.
MIN_VIEWER_Z_MM = 300.0
MAX_VIEWER_Z_MM = 5000.0

# How many degrees of real-world gaze rotation map to a full-scale eye
# deflection (normalized gaze = ±1.0). 30° roughly matches the existing
# max_offset behavior with DEFAULT_MAX_OFFSET=350 on a 1080 eye.
DEFAULT_MAX_GAZE_DEG = 30.0


@dataclass
class Camera:
    id: str
    x_mm: float
    y_mm: float
    z_mm: float = 0.0
    hfov_deg: float = 102.0  # Pi Camera Module 3 Wide default
    vfov_deg: float = 67.0


@dataclass
class Eye:
    id: str
    x_mm: float
    y_mm: float
    diameter_mm: float
    render_size_px: int
    display_type: str  # "hdmi" | "spi"
    device: str        # "HDMI-A-1" or "/dev/spidev0.0" or GPIO pin spec
    is_left_eye: bool = True
    # Optional: which sub-rect of the HDMI window this eye occupies. Only
    # used for display_type == "hdmi". Units: pixels.
    hdmi_rect: Optional[tuple[int, int, int, int]] = None  # (x, y, w, h)


@dataclass
class FrameLayout:
    frame_width_mm: float
    frame_height_mm: float
    cameras: list[Camera] = field(default_factory=list)
    eyes: list[Eye] = field(default_factory=list)

    @classmethod
    def load(cls, path: str) -> "FrameLayout":
        with open(path, "r") as f:
            data = json.load(f)
        frame = data.get("frame", {})
        layout = cls(
            frame_width_mm=float(frame.get("width_mm", 1800)),
            frame_height_mm=float(frame.get("height_mm", 1200)),
        )
        for c in data.get("cameras", []):
            layout.cameras.append(Camera(
                id=c["id"],
                x_mm=float(c["x_mm"]),
                y_mm=float(c["y_mm"]),
                z_mm=float(c.get("z_mm", 0.0)),
                hfov_deg=float(c.get("hfov_deg", 102.0)),
                vfov_deg=float(c.get("vfov_deg", 67.0)),
            ))
        for e in data.get("eyes", []):
            rect = e.get("hdmi_rect")
            layout.eyes.append(Eye(
                id=e["id"],
                x_mm=float(e["x_mm"]),
                y_mm=float(e["y_mm"]),
                diameter_mm=float(e["diameter_mm"]),
                render_size_px=int(e.get("render_size_px", 1080)),
                display_type=e.get("display_type", "hdmi"),
                device=e.get("device", ""),
                is_left_eye=bool(e.get("is_left_eye", True)),
                hdmi_rect=tuple(rect) if rect else None,
            ))
        return layout

    def hdmi_eyes(self) -> list[Eye]:
        return [e for e in self.eyes if e.display_type == "hdmi"]

    def spi_eyes(self) -> list[Eye]:
        return [e for e in self.eyes if e.display_type == "spi"]


def project_face_to_world(
    nx: float,
    ny: float,
    nw: float,
    camera: Camera,
) -> tuple[float, float, float]:
    """Convert the detector's normalized (nx, ny, nw) into a world-space
    (X, Y, Z) point in frame coordinates (millimeters).

    nx, ny are in roughly [-1, 1] — the horizontal/vertical position of the
    face in the camera image. nw is a face-width proxy for depth.
    """
    # Depth: inverse proportional to face width, calibrated so the chosen
    # (DEPTH_CALIBRATION_NW, DEPTH_CALIBRATION_MM) pair matches.
    nw_safe = max(1e-3, nw) if nw and nw > 0 else DEPTH_CALIBRATION_NW
    z_mm = DEPTH_CALIBRATION_MM * (DEPTH_CALIBRATION_NW / nw_safe)
    z_mm = max(MIN_VIEWER_Z_MM, min(MAX_VIEWER_Z_MM, z_mm))

    # Angular offset from camera principal axis. nx=±1 corresponds to the
    # edge of the camera frame, i.e. ±hfov/2.
    half_h = math.radians(camera.hfov_deg * 0.5)
    half_v = math.radians(camera.vfov_deg * 0.5)
    angle_x = nx * half_h
    angle_y = ny * half_v

    # World position relative to camera, then shifted into frame space.
    # Assumes camera looks along +z (out of the frame). A forward distance
    # of z_mm maps the angular offsets to lateral displacement.
    dx = z_mm * math.tan(angle_x)
    dy = z_mm * math.tan(angle_y)

    world_x = camera.x_mm + dx
    world_y = camera.y_mm + dy
    world_z = camera.z_mm + z_mm
    return world_x, world_y, world_z


def eye_gaze_normalized(
    eye: Eye,
    world_xyz: tuple[float, float, float],
    max_gaze_deg: float = DEFAULT_MAX_GAZE_DEG,
) -> tuple[float, float]:
    """Compute an individual eye's gaze direction toward a world point,
    returned as normalized (nx, ny) in [-1, 1] ready to drop into the
    existing renderer in place of the camera's raw face coordinates.

    Each eye sits at (eye.x_mm, eye.y_mm, 0) looking along +z. The vector
    from the eye to the target, projected onto the eye's local yaw/pitch,
    gives the angles this particular eye must rotate to fixate the viewer.
    Because eyes at different positions see different angles to the same
    target, eyes physically converge on the viewer instead of all pointing
    the same way.
    """
    wx, wy, wz = world_xyz
    dx = wx - eye.x_mm
    dy = wy - eye.y_mm
    dz = max(1.0, wz)  # eye at z=0, target must be in front

    yaw_rad = math.atan2(dx, dz)
    pitch_rad = math.atan2(dy, dz)

    max_rad = math.radians(max_gaze_deg)
    nx = max(-1.0, min(1.0, yaw_rad / max_rad))
    ny = max(-1.0, min(1.0, pitch_rad / max_rad))
    return nx, ny
