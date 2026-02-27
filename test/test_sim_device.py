import math

from sim_device import AxisProfile, SimulatedDevice


def test_limited_axis_scaling():
    profile = AxisProfile(min_angle=0.0, max_angle=math.pi, reversed=False, endless=False)
    dev = SimulatedDevice(profile)

    dev.send_cc(0)
    assert dev.joystick_value() == 0

    dev.send_cc(127)
    assert dev.joystick_value() == 1023


def test_reversed_axis_scaling():
    profile = AxisProfile(min_angle=0.0, max_angle=1.0, reversed=True, endless=False)
    dev = SimulatedDevice(profile)

    dev.send_cc(0)
    assert dev.joystick_value() == 1023

    dev.send_cc(127)
    assert dev.joystick_value() == 0


def test_endless_axis_delta():
    profile = AxisProfile(min_angle=-math.pi, max_angle=math.pi, reversed=False, endless=True)
    dev = SimulatedDevice(profile)

    dev.send_cc(64)
    baseline = dev.joystick_value()

    dev.send_cc(65)
    forward = dev.joystick_value()

    dev.send_cc(63)
    backward = dev.joystick_value()

    assert forward != baseline
    assert backward != baseline
