
**Purpose**
This is a usb HID joystick that accepts midi commands to configure a SimpleFOC driven motor controlled AXIS (USB Composite Device).

Preconfigured use cases are:
- Cessna 
    - Throttle (0-100), 
    - Flaps (detents for 0,10,20,30,40), 
    - Gear (strong detent at 0, light/strong switchable detent at 100 ), 
    - Trim (-100 to 100 with clicks)
- Airbus 
    - Throttle (Detents for TO/GA, FLX, CLB, Idle, Rev Idle, Reverse Full; Idle->CLB and RecIdle->RevFull are continuous flat spots in the detent profile for proportional control), 
    - Flaps (0,1,2,3,Full), 
    - Spoilers (detents for 0,1/2,Full, in between small clicks), 
    - Gear (like above), 
    - Trim (like above)
- Glider 
    - Spoiler (like above), 
    - Trim (like above)

The joystick needs to be used with Microsoft Flight Simulator, sending the Axis data as USB joystick, and sending the configured case as identification of the USB device.
A companion script is provided that interfaces with the MSFS Scripting  and provides the current position interface from the User Interface of the respective control.



**Hardware Configurations**:
Three buildable configurations support different hardware setups:
- **pico_1motor_endless** — Single endless motor (current hardware, trim-like)
- **pico_1motor_limited** — Single 0-180° motor (throttle/flaps-like)
- **pico_2motor_limited** — Dual motors (throttle + trim, future-proof)

Build with: `platformio run -e pico_1motor_endless`

