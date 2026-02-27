# SimpleFOC Studio Tuning Guide

## Overview

This firmware supports real-time PID tuning via **SimpleFOC Commander**, compatible with [SimpleFOC Studio](https://studio.simplefoc.com).

## Quick Start

### Web App (Recommended)

1. Visit https://studio.simplefoc.com
2. Connect to `/dev/ttyACM0` (115200 baud)
3. Motors appear as `M` (motor0) and `N` (motor1)
4. Adjust PID gains in real-time

### Desktop App

Download from https://github.com/JorgeMaker/SimpleFOCStudio/releases

## Commander Protocol

### Angle Loop Commands

```
MP<value>   # Set angle P gain (e.g., MP20.0)
MI<value>   # Set angle I gain (e.g., MI0.0)
MD<value>   # Set angle D gain (e.g., MD0.5)
```

### Velocity Loop Commands

```
MVP<value>  # Set velocity P gain (e.g., MVP0.125)
MVI<value>  # Set velocity I gain (e.g., MVI10.0)
MVD<value>  # Set velocity D gain (e.g., MVD0.0)
```

### Query Commands

```
M           # Print all motor0 parameters
MP?         # Query angle P gain
MV          # Print velocity controller state
```

## Serial Connection

- **Port**: `/dev/ttyACM0` (USB CDC)
- **Baud**: 115200
- **Protocol**: SimpleFOC Commander (text-based)
- **Debug output**: `A=<angle> T=<target>` @ 100Hz

## Tuning Workflow

1. **Start with conservative gains** (current values are tuned)
2. **Monitor response** via SimpleFOC Studio plots
3. **Adjust angle loop first** (outer loop)
   - Start with P only
   - Add D for damping
   - Add I only if steady-state error
4. **Tune velocity loop** (inner loop, usually stable)

## Current Tuned Values

### Motor 0 (Angle Loop)
- **P**: 20.0 (position stiffness)
- **I**: 0.0 (no integral)
- **D**: 0.5 (damping)

### Motor 0 (Velocity Loop)
- **P**: 0.125
- **I**: 10.0
- **D**: 0.0

These gains achieve **87.6/100 EXCELLENT** quality score.

## Integration Details

Implemented in `lib/commander_integration.cpp`:
- Registers motors with SimpleFOC Commander
- Processes text commands from Serial
- Updates gains in real-time (no reboot required)

See: [.agentic/tuning/implementation/SIMPLEFOC_STUDIO_PLAN.md](../.agentic/tuning/implementation/SIMPLEFOC_STUDIO_PLAN.md)
