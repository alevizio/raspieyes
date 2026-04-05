"""
SPI round display driver stub (GC9A01 240x240).

This is scaffolding for the multi-eye frame experiment. No real SPI traffic
happens here yet — actual wiring requires physical GC9A01 displays, which
aren't present in the current build. The driver interface and init sequence
are in place so that swapping in a working backend later is a drop-in change.

Typical wiring per display (shared SPI bus, per-display CS/DC/RST):
    VCC  -> 3.3V
    GND  -> GND
    SCL  -> SPI SCLK (GPIO11 / pin 23 on Pi 5)
    SDA  -> SPI MOSI (GPIO10 / pin 19)
    CS   -> dedicated chip-select GPIO (one per display)
    DC   -> data/command GPIO (can be shared across displays on same bus)
    RST  -> reset GPIO (can be shared or tied high)
    BL   -> 3.3V (or PWM GPIO for dimming)

Dependencies (install when hardware is ready):
    pip install spidev gpiozero numpy
"""

from __future__ import annotations

import time
from typing import Optional

try:
    import pygame
except ImportError:  # pragma: no cover
    pygame = None  # allows import on non-graphical dev machines


# GC9A01 init sequence — minimal subset, RGB565 mode, 240x240.
# Taken from the GC9A01 datasheet + adafruit/lcdwiki reference drivers.
_INIT_CMDS = [
    (0xEF, b""),
    (0xEB, b"\x14"),
    (0xFE, b""),
    (0xEF, b""),
    (0xEB, b"\x14"),
    (0x84, b"\x40"),
    (0x85, b"\xFF"),
    (0x86, b"\xFF"),
    (0x87, b"\xFF"),
    (0x88, b"\x0A"),
    (0x89, b"\x21"),
    (0x8A, b"\x00"),
    (0x8B, b"\x80"),
    (0x8C, b"\x01"),
    (0x8D, b"\x01"),
    (0x8E, b"\xFF"),
    (0x8F, b"\xFF"),
    (0xB6, b"\x00\x20"),
    (0x3A, b"\x05"),             # COLMOD: 16-bit RGB565
    (0x36, b"\x08"),             # MADCTL: BGR
    (0x90, b"\x08\x08\x08\x08"),
    (0xBD, b"\x06"),
    (0xBC, b"\x00"),
    (0xFF, b"\x60\x01\x04"),
    (0xC3, b"\x13"),
    (0xC4, b"\x13"),
    (0xC9, b"\x22"),
    (0xBE, b"\x11"),
    (0xE1, b"\x10\x0E"),
    (0xDF, b"\x21\x0c\x02"),
    (0x11, b""),                  # Sleep out
    # After SLPOUT, host should wait ≥120ms before sending DISPON.
    (0x29, b""),                  # Display on
]


class SpiEyeDisplay:
    """Driver handle for a single GC9A01 panel.

    Current implementation is a no-op stub that logs the first few push
    calls so you can verify the plumbing from the renderer. Replace the
    body of `_send_command`, `_send_data`, and `push_surface` with real
    spidev calls when hardware is wired up.
    """

    def __init__(self, device: str, size_px: int = 240):
        self.device = device
        self.size_px = size_px
        self._spi = None
        self._cs_pin: Optional[int] = None
        self._dc_pin: Optional[int] = None
        self._rst_pin: Optional[int] = None
        self._frame_count = 0
        self._last_log_time = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Parse self.device (e.g. "spi0.0:gpio25"), open spidev, configure
        GPIO, run the init sequence. No-op in the stub."""
        # TODO(hardware): implement when GC9A01 panels arrive. Example:
        #     import spidev, gpiozero
        #     bus, dev = self._parse_spi_dev()
        #     self._spi = spidev.SpiDev()
        #     self._spi.open(bus, dev)
        #     self._spi.max_speed_hz = 40_000_000
        #     self._spi.mode = 0
        #     self._cs_pin = gpiozero.DigitalOutputDevice(...)
        #     ...
        #     self._run_init_sequence()
        print(f"[spi_display] (stub) open {self.device} size={self.size_px}", flush=True)

    def close(self) -> None:
        if self._spi is not None:
            self._spi.close()
            self._spi = None

    # ------------------------------------------------------------------
    # Frame push
    # ------------------------------------------------------------------

    def push_surface(self, surface) -> None:
        """Send a pygame Surface to the panel. Surface must be square;
        will be smoothscaled to self.size_px if needed."""
        self._frame_count += 1

        # Rate-limit the stub log so we don't flood stdout at 60fps.
        now = time.monotonic()
        if now - self._last_log_time > 5.0:
            self._last_log_time = now
            print(
                f"[spi_display] (stub) {self.device}: "
                f"{self._frame_count} frames buffered",
                flush=True,
            )

        # TODO(hardware): convert surface → RGB565 bytes, set CASET/RASET
        # to (0, 0, size-1, size-1), send RAMWR, then stream the pixel
        # buffer over SPI in ~4KB chunks.
        #
        #     if pygame is not None and surface.get_width() != self.size_px:
        #         surface = pygame.transform.smoothscale(
        #             surface, (self.size_px, self.size_px))
        #     rgb = pygame.surfarray.pixels3d(surface)  # (w, h, 3) uint8
        #     r = (rgb[..., 0] >> 3).astype("uint16") << 11
        #     g = (rgb[..., 1] >> 2).astype("uint16") << 5
        #     b = (rgb[..., 2] >> 3).astype("uint16")
        #     rgb565 = (r | g | b).byteswap().tobytes()
        #     self._send_command(0x2A, [0, 0, 0, self.size_px - 1])  # CASET
        #     self._send_command(0x2B, [0, 0, 0, self.size_px - 1])  # RASET
        #     self._send_command(0x2C)                                # RAMWR
        #     self._send_data_chunks(rgb565)

    # ------------------------------------------------------------------
    # Low-level (stubbed)
    # ------------------------------------------------------------------

    def _run_init_sequence(self) -> None:
        for cmd, data in _INIT_CMDS:
            self._send_command(cmd, list(data))
            if cmd == 0x11:  # SLPOUT
                time.sleep(0.12)

    def _send_command(self, cmd: int, data: Optional[list[int]] = None) -> None:
        # TODO(hardware): drive DC low, CS low, xfer [cmd], then DC high
        # for any data bytes.
        pass

    def _send_data(self, data: bytes) -> None:
        # TODO(hardware): stream bytes over SPI with DC high.
        pass
