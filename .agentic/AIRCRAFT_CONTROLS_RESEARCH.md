# Aircraft Controls Research — Real-World Reference Data

Research compiled for verifying/correcting haptic feedback profiles in config.h.

**Sources**: Cessna 172S POH (Pilot's Operating Handbook), Airbus A320 FCOM (Flight Crew Operating Manual), glider manufacturer manuals (Schleicher ASK-21, Schempp-Hirth Discus), Thrustmaster TCA product specifications, published pilot experience.

---

## 1. Cessna 172 (Skyhawk / 172SP)

### Trim Wheel
- **Type**: Cable-actuated elevator trim wheel, located between pilot seats on center console.
- **Physical travel**: Approximately 18–20 full rotations from full nose-down to full nose-up. The wheel is about 10 cm (4 in) diameter.
- **Detent behavior**: **NONE**. The real trim wheel is completely smooth and held in position by cable friction alone. There are no clicks, notches, or detents.
- **Markings**: A pointer on the instrument panel indicates nose-up / nose-down on a scale; the wheel itself has a knurled surface for grip.
- **Force feel**: Light but noticeable friction. Smooth rotation, easy to turn with fingertips.
- **Firmware impact**: 18 uniform clicks is a REASONABLE haptic approximation (feel-of-quality choice), but note the real aircraft is smooth. The number 18 happens to be close to the number of full turns on the real wheel — possibly a coincidence, or a useful mapping where 1 click ≈ 1 revolution of the real wheel.

### Throttle
- **Type**: Push-pull plunger (linear, NOT rotary). Black knob, in-line with mixture and carb heat.
- **Physical travel**: Approximately 8–10 cm (3–4 in) linear push/pull.
- **Detent behavior**: **NONE**. Smooth travel, friction lock to hold position.
- **Force feel**: Spring-loaded friction lock. Moderate force to move, stays in place when released.
- **Mapping note**: Throttle is IN = full power, OUT = idle. For a rotary motor, 180° smooth is a reasonable representation.

### Mixture
- **Type**: Push-pull plunger (linear). Red knob, adjacent to throttle.
- **Physical travel**: Similar to throttle, ~8–10 cm.
- **Detent behavior**: The **idle cutoff** position (full out) has a slight detent/indent to prevent accidental lean-to-cutoff.
- **Force feel**: Similar friction-lock as throttle.
- **Note**: Not currently in firmware profiles. If added: smooth with one soft detent at 0% (idle cutoff).

### Flaps
- **Type**: Electric flaps controlled by a switch/lever (172SP). Older models (pre-1981) had a Johnson bar with notched positions.
- **Positions**:
  - **172SP (1998–present)**: **4 positions**: 0°, 10°, 20°, 30° (max 30°)
  - **172P and earlier (pre-1981)**: **5 positions**: 0°, 10°, 20°, 30°, 40° (max 40°)
- **Control type**: The 172SP uses a rocker switch or spring-loaded flap lever — the motor drives flaps to discrete positions. Earlier models used a manual lever with notches.
- **Firmware impact**: The firmware assumes 5 positions (0°–40°). This matches **pre-1981 models** only. The most common current model (172SP) has only **4 positions (0°–30°)**. Consider making this configurable or defaulting to 4 positions.

### Landing Gear
- **CRITICAL**: The standard Cessna 172 has **FIXED (non-retractable) landing gear**. There is no gear lever.
- The **Cessna 172RG** (Retractable Gear) variant does have a gear handle: a simple two-position switch (UP/DOWN) with a mechanical over-center lock.
- **Firmware impact**: The "Cessna Gear" profile should either be renamed to "Cessna 172RG Gear" or noted as applying only to the RG variant.

---

## 2. Airbus A320

### Trim Wheel (Pitch Trim / THS — Trimmable Horizontal Stabilizer)
- **Type**: Two manual trim wheels on each side of the center pedestal (captain side and first officer side). They rotate together and with the autopilot/autotrim commands.
- **Physical travel**: The wheels rotate over approximately 12 full turns from full nose-down (-13.5° THS) to full nose-up (+4° THS). The total THS range is ~17.5°.
- **Detent behavior**: **NONE**. Continuous smooth rotation. The wheels spin freely with the autotrim in normal law.
- **Force feel**: In normal law, the wheels are motor-driven and rotate on their own (pilot feels them spinning under autotrim). In direct law (backup), the pilot turns them with moderate effort.
- **Firmware impact**: 18 uniform clicks is a REASONABLE haptic approximation. As with Cessna, the real aircraft has no clicks.

### Thrust Levers
- **Type**: Two side-by-side thrust levers on the center pedestal. Linear track with defined detent gates.
- **Physical travel**: Approximately 50–55° of angular travel from IDLE to TOGA. Reverse thrust adds approximately 20° behind IDLE (accessed by lifting reverse lever mechanism).
- **Detent positions** (measured from IDLE = 0°):
  | Position | Angle from IDLE | % of IDLE→TOGA range | Strength |
  |----------|-----------------|----------------------|----------|
  | REV FULL | ≈ −20° | (below IDLE) | Hard stop |
  | REV IDLE | ≈ −6° | (below IDLE) | Moderate detent |
  | **IDLE** | 0° | 0% | Hard gate |
  | **CL (Climb)** | ≈ 20° | ≈ 36% | Hard gate |
  | **FLX/MCT** | ≈ 35° | ≈ 64% | Moderate gate |
  | **TOGA** | ≈ 50–55° | 100% | Hard stop |
- **Between IDLE and CL**: Free proportional movement (autothrust range). The levers normally rest at CL during climb and cruise. Autothrust manages engine power; pilots set the lever at CL and leave it.
- **Gate behavior**: Each detent is a "gate" — a physical indent you push through. The gate_mode=true approach in the firmware correctly models this.
- **Firmware comparison**: Current firmware has gates at 0%, 14%, 28%, 64%, 82%, 100%. Recommended adjustment (see below).

### Flap Lever
- **Type**: Lever on the center pedestal with discrete detent positions.
- **Positions (physical lever markings)**: **0, 1, 2, 3, FULL** — that is **5 positions**.
  - Note: "Config 1+F" is NOT a separate lever position. It's the same lever position "1" but the aircraft automatically selects flaps when speed is below a threshold. The lever physically only has 5 stops.
- **Travel**: Approximately 80–90° angular arc from 0 to FULL.
- **Detent behavior**: Hard detents at each position. Lever clicks firmly into each notch.
- **Firmware impact**: 5 positions evenly spaced at 100° range is REASONABLE. The real spacing is roughly even. Consider slightly increasing range to ~90° for more realistic feel.

### Speed Brake (Spoiler) Lever
- **Type**: Lever on center pedestal, slides forward/aft.
- **Positions**: 
  - **RETRACTED**: Fully aft, firm detent.
  - **ARMED**: A special lifted position (pull up and aft) — not on the same linear track. Used to arm ground spoilers for landing.
  - **Proportional deployment**: From retracted, push forward for proportional spoiler deployment (no intermediate detents).
  - **FULL**: Fully forward, physical stop.
- **Physical travel**: Approximately 15 cm (6 in) linear, or roughly 70–80° if on a rotary.
- **Detent behavior**: The real A320 speed brake lever has **NO intermediate detents** between RETRACTED and FULL. It is proportional/smooth with stops only at both extremes.
- **Firmware impact**: The current 5-point major/minor pattern (0/¼/½/¾/Full) adds clicks that don't exist in the real aircraft. Recommend:
  - Remove minor clicks at 25% and 75%
  - Keep hard stops at 0% and 100%
  - Optionally add a waypoint at 50% with very low strength (0.1) as a tactile midpoint reference

### Landing Gear Lever
- **Type**: Simple two-position lever (UP/DOWN) on center instrument panel.
- **Behavior**: The lever has a positive lock in the DOWN position. Lift-and-push to move to UP.
- **Not currently in firmware as a separate A320 profile** (the AIRCRAFT_PROFILES.md mentions it but config.h doesn't list it).

---

## 3. Glider (Generic — ASK-21 / Discus / LS4 class)

### Trim
- **Type**: Spring trim, typically a small lever or wheel depending on glider type.
  - **ASK-21**: Trim lever on the left side, spring-loaded to center.
  - **Discus / LS4**: Small trim lever, often with 10–15 cm travel.
- **Physical travel**: Typically 10–15 cm linear or approximately 90–120° of rotation if on a rotary mechanism.
- **Detent behavior**: **NONE**. Smooth, spring-loaded to a neutral position. The trim adjusts the spring tension on the stick.
- **Force feel**: Light spring resistance with a definite center feel.
- **Firmware impact**: 18 clicks over 180° is MORE clicks and MORE range than typical real glider trim. A glider trim is much simpler — consider 120° range with maybe 8–10 clicks, or just smooth with soft centering. However, 18 clicks at 180° is fine for a universal approximation.

### Airbrake / Spoiler
- **Type**: Large lever on the left side of the cockpit (most gliders). Pull aft to deploy, push forward to close.
- **Physical travel**: Approximately 15–20 cm (6–8 in) linear.
- **Detent behavior**: 
  - **Locked closed**: Most gliders have a positive lock in the fully closed position — push forward and the lever clicks into a locked position. This prevents accidental deployment.
  - **Proportional**: Between closed-lock and fully open, the travel is **smooth with no intermediate detents**.
  - **Full open**: Physical stop, no special detent.
- **Force feel**: Moderate to heavy force (aerodynamic load pushes the spoilers open, so you're fighting the airstream when closing). Spring return or over-center mechanism helps.
- **Firmware impact**: The 5-point major/minor pattern adds clicks that don't exist on real glider airbrakes. Recommend:
  - Hard detent at 0% (locked closed)
  - Smooth/free movement from 0%–100%
  - Hard stop at 100% (fully deployed)

---

## 4. Thrustmaster TCA Quadrant (Airbus Edition)

This is the most popular desktop A320 throttle quadrant for flight simmers and a key reference for users of this device.

### Physical Specifications
- **Lever travel**: Approximately 65–70mm linear track, or about 55–60° angular equivalent.
- **Detent gates** (from observation and community measurements):
  | Position | Approx % of forward travel | Approx angle |
  |----------|---------------------------|--------------|
  | REV FULL | -30% (below IDLE) | -18° |
  | REV IDLE | -10% (below IDLE) | -6° |
  | IDLE | 0% | 0° |
  | CL | ~36% | ~20° |
  | FLX/MCT | ~64% | ~35° |
  | TOGA | 100% | ~55° |
- **Gate feel**: Plastic detent mechanism. Each gate is a notch you push through with moderate force. IDLE has the strongest detent. TOGA is a hard stop.
- **Reverse**: Accessed by lifting a separate lever mechanism that unlocks the reverse range.

### Comparison with firmware
The firmware's A320_THROTTLE_DETENTS percentages:
- REV FULL at 0%, REV IDLE at 14%, IDLE at 28%, CLB at 64%, FLX at 82%, TOGA at 100%

This puts IDLE at 28% of total travel. In reality (both real A320 and TCA), the reverse range is mechanically separate (lift mechanism), and IDLE is at the bottom of the forward range (0%). The firmware maps the reverse range into the same 0–100% span, which is a design choice. 

If we map forward-only range (IDLE to TOGA) to 0–100%:
| Position | TCA measured | Firmware (forward mapped) |
|----------|-------------|--------------------------|
| IDLE | 0% | 0% (was 28% of full) |
| CL | ~36% | ~50% (was 64% of full) |
| FLX/MCT | ~64% | ~75% (was 82% of full) |
| TOGA | 100% | 100% |

The firmware's forward-range spacing is more compressed toward TOGA than the TCA. See recommendations below.

---

## 5. RECOMMENDED CHANGES

### RC-1: Cessna Flaps — Reduce to 4 positions (172SP default)
**What**: Change CESSNA_FLAPS_DETENTS from 5 positions (0°/10°/20°/30°/40°) to 4 positions (0°/10°/20°/30°).
**Why**: The most common Cessna 172 in service (172SP, 1998–present) has 30° max flaps. The 40° setting applies only to pre-1981 models.
**Numbers**:
```cpp
static const DetentPoint CESSNA_FLAPS_DETENTS[] = {
    {   0.0f, 1.0f },   // 0° retracted
    {  33.3f, 1.0f },   // 10°
    {  66.7f, 1.0f },   // 20°
    { 100.0f, 1.0f },   // 30° full
};
```
Map size: 4. Range can stay at 120°.

**Alternative**: Keep 5 positions but label as "Cessna 172 (pre-1981)" and add a 4-position variant for "Cessna 172SP".

### RC-2: Cessna Gear — Rename or annotate
**What**: Rename "Cessna Gear" to "Cessna 172RG Gear" since the standard 172 has fixed gear.
**Why**: Avoids confusion. The 172RG is the retractable-gear variant.

### RC-3: A320 Throttle Detent Spacing — Adjust forward-range percentages
**What**: Adjust A320_THROTTLE_DETENTS to better match real A320/TCA gate spacing.
**Why**: Current spacing puts CLB at 64% (forward of midpoint); TCA data shows CLB at ~36% of forward range.
**Numbers** (if reverse is kept in same 0–100% span):
```cpp
static const DetentPoint A320_THROTTLE_DETENTS[] = {
    {   0.0f, 1.0f },   // REV FULL
    {  12.0f, 0.8f },   // REV IDLE
    {  25.0f, 1.0f },   // IDLE
    {  52.0f, 1.0f },   // CLB   (was 64 → 52: ~36% of 25→100 range)
    {  73.0f, 0.8f },   // FLX   (was 82 → 73: ~64% of 25→100 range)
    { 100.0f, 1.0f },   // TOGA
};
```

**Alternative**: Split reverse into a separate mode and map only forward thrust (IDLE→TOGA) to 0–100%, which is how the TCA works mechanically.

### RC-4: A320 Spoiler — Remove artificial intermediate clicks
**What**: Simplify A320_SPOILER_DETENTS to 2–3 points maximum.
**Why**: Real A320 speed brake is proportional with no intermediate detents.
**Numbers**:
```cpp
static const DetentPoint A320_SPOILER_DETENTS[] = {
    {   0.0f, 1.0f },   // Retracted (hard stop)
    {  50.0f, 0.1f },   // Midpoint reference (very soft)
    { 100.0f, 1.0f },   // Full (hard stop)
};
```
Map size: 3.

### RC-5: Glider Spoiler — Remove artificial intermediate clicks  
**What**: Simplify GLIDER_SPOILER_DETENTS similar to RC-4.
**Why**: Real glider airbrakes are smooth/proportional with lock at closed position.
**Numbers**:
```cpp
static const DetentPoint GLIDER_SPOILER_DETENTS[] = {
    {   0.0f, 1.0f },   // Locked closed (hard detent)
    { 100.0f, 0.8f },   // Full open (stop, slightly less hard than lock)
};
```
Map size: 2.

### RC-6 (OPTIONAL): Trim profiles — Consider smooth mode
**What**: Change all trim profiles (Cessna/A320/Glider) from 18 uniform clicks to smooth (detent_count=0).
**Why**: No real-world trim wheel has clicks. The 18-click approximation is a UX design choice for tactile feedback, not realism.
**Trade-off**: Clicks give better position awareness through a rotary knob. Keep if user-feel testing prefers clicks. Reduce to ~10 clicks if 18 feels too "notchy". This is a user preference item, not a correctness issue.

### RC-7 (LOW PRIORITY): Glider Trim — Reduce range
**What**: Consider reducing Glider Trim range from 180° to 120° and click count from 18 to ~10.
**Why**: Real glider trim has much less travel than airplane trim. A shorter range would feel more realistic.

### RC-8 (INFO): A320 Flap Lever
**Status**: Current firmware is **CORRECT**. The A320 flap lever has 5 physical positions (0, 1, 2, 3, FULL). The "Config 1+F" is a flight control law mode, not a lever position. No change needed.

### RC-9 (INFO): Cessna Throttle  
**Status**: Current firmware is **CORRECT** for a rotary approximation. Real Cessna throttle is smooth push-pull. Smooth 180° range is the right representation.

---

## Summary Table

| Profile | Current State | Verdict | Action |
|---------|--------------|---------|--------|
| Cessna Trim | 18 clicks, 180° | OK (UX choice) | Optional: go smooth (RC-6) |
| Cessna Throttle | Smooth, 180° | CORRECT | None |
| Cessna Flaps | 5 pos, 120° | WRONG for 172SP | Change to 4 positions (RC-1) |
| Cessna Gear | 2 pos, 90° | MISLEADING | Rename to 172RG (RC-2) |
| A320 Trim | 18 clicks, 180° | OK (UX choice) | Optional: go smooth (RC-6) |
| A320 Throttle | 6 gates, 120° | SPACING OFF | Adjust percentages (RC-3) |
| A320 Flaps | 5 pos, 100° | CORRECT | None |
| A320 Spoilers | 5 detents, 90° | WRONG | Simplify to 2–3 (RC-4) |
| Glider Trim | 18 clicks, 180° | OVER-SPEC | Optionally reduce (RC-7) |
| Glider Spoiler | 5 detents, 90° | WRONG | Simplify to 2 (RC-5) |

**Priority**: RC-1, RC-3, RC-4, RC-5 are correctness fixes. RC-2 is labeling. RC-6, RC-7 are taste.
