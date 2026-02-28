# AS5600 Encoder Linearization Options

**Status**: Documented for future reference. Not needed yet — unloaded limits accommodate the eccentricity error.

## Problem

Magnet mounted with double-sided tape → off-center → sinusoidal error through rotation:

$$e(\theta) = A \sin(\theta + \phi)$$

Observed: 180° and 0° show ~8° mean error, while 90°/270° show 2-3°. This is classic once-per-revolution eccentricity. Test C (hold stddev) fails at these positions due to the large oscillation amplitude.

## Matrix Results (iteration 16, 2V, unloaded)

| Position | Mean Error | Stddev | Note |
|----------|-----------|--------|------|
| 0°       | 4-9°      | 3-5°   | Eccentricity pole |
| 45°      | 3°        | 1.5°   | Clean |
| 90°      | 3°        | 1.5°   | Clean |
| 135°     | 2.4°      | 1.3°   | Clean |
| 180°     | 7-9°      | 3-6°   | Eccentricity pole |
| 225°     | 3-4°      | 0.5-2° | Clean |
| 270°     | 2.7°      | 1.7°   | Clean |
| 315°     | ~4°       | ~2°    | Clean |

## Option 1: Physical Fix (Best, Zero Code)

Re-center the magnet on the shaft:
- 3D-printed centering jig
- Magnet with shaft-hole (press-fit)
- Centering sleeve/collar

This eliminates the root cause. AS5600 datasheet specifies ±1° INL under ideal placement.

## Option 2: Software Calibration via GenericSensor

SimpleFOC's `GenericSensor` class accepts a callback, allowing a correction wrapper around the raw AS5600 reading.

**Approach**: Fit a single-harmonic sinusoid to the error curve, subtract it.

```cpp
#include <sensors/GenericSensor.h>

MagneticSensorI2C as5600_raw(AS5600_I2C);

// Calibrated eccentricity parameters (two floats)
float ecc_amplitude = 0.07f;  // ~4° in radians — calibrate!
float ecc_phase = 0.0f;       // phase offset — calibrate!

float correctedReadCallback() {
    as5600_raw.update();
    float raw = as5600_raw.getSensorAngle();
    return raw - ecc_amplitude * sin(raw + ecc_phase);
}

GenericSensor corrected_sensor(correctedReadCallback);
// Then: motor.linkSensor(&corrected_sensor);
```

**Calibration procedure**:
1. Drive motor slowly through 360° in open-loop voltage mode
2. Record sensor angle vs. commanded angle at many points (every 1°)
3. Compute error curve
4. Fit sinusoid: find A and φ (two parameters)
5. Hard-code `ecc_amplitude` and `ecc_phase`

Cost: one `sin()` per control loop iteration (negligible on RP2040 @ 133MHz).

## Option 3: AS5600 Register Tuning (Marginal)

Slow filter in CONF register (0x07–0x08) reduces noise but does NOT fix systematic eccentricity:

```cpp
Wire.beginTransmission(0x36);
Wire.write(0x07);
Wire.write(0x00);  // CONF high byte
Wire.write(0x04);  // CONF low byte: slow filter 16x
Wire.endTransmission();
```

## What the AS5600 Does NOT Have

- No linearization LUT
- No eccentricity compensation
- No internal calibration routine
- No harmonic correction

(Unlike the AS5048A which has CORDIC and better linearity specs.)

## Decision

Stay with current setup. The unloaded limits (±10° accuracy, <5° stddev) accommodate the eccentricity. The loaded product limits (±1°) require either option 1 or option 2 when mechanical coupling is added.
