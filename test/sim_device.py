"""Minimal HID/MIDI simulator for headless tests.

This models the same CC-to-angle and angle-to-joystick mapping used by firmware.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass
class AxisProfile:
    min_angle: float
    max_angle: float
    reversed: bool = False
    endless: bool = False
    endless_step_rad: float = 2 * math.pi / 128.0


class SimulatedDevice:
    """Simulate a single axis device with MIDI CC input and joystick output."""

    def __init__(self, profile: AxisProfile):
        self.profile = profile
        self.angle = profile.min_angle
        self._last_cc = None

    def send_cc(self, value: int) -> None:
        """Apply a MIDI CC value (0-127)."""
        value = max(0, min(127, int(value)))

        if self.profile.endless:
            if self._last_cc is None:
                self._last_cc = value
                return
            delta = value - self._last_cc
            self._last_cc = value
            self.angle += delta * self.profile.endless_step_rad
            span = self.profile.max_angle - self.profile.min_angle
            if span > 0:
                while self.angle < self.profile.min_angle:
                    self.angle += span
                while self.angle > self.profile.max_angle:
                    self.angle -= span
        else:
            span = self.profile.max_angle - self.profile.min_angle
            self.angle = self.profile.min_angle + (value / 127.0) * span
            self.angle = min(self.profile.max_angle, max(self.profile.min_angle, self.angle))

    def joystick_value(self) -> int:
        """Return a 10-bit joystick value (0-1023)."""
        span = self.profile.max_angle - self.profile.min_angle
        if span <= 0:
            return 0
        normalized = (self.angle - self.profile.min_angle) / span
        if self.profile.reversed:
            normalized = 1.0 - normalized
        normalized = min(1.0, max(0.0, normalized))
        return int(round(normalized * 1023))
