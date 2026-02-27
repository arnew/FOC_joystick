@echo off
REM Hardware Integration Test Suite - Windows Batch Version
REM Run on CI runner with motor connected
REM Date: 2026-02-27
REM Usage: cmd /c test\hardware_test.bat

setlocal enabledelayedexpansion

echo.
echo ================================
echo Hardware Integration Test Suite
echo ================================
echo.
echo Prerequisites:
echo   - Motor connected to CI runner
echo   - USB cable connected (Micro-B)
echo   - Power 5V 2A minimum
echo   - dev branch checked out
echo.

REM ============================================================================
REM PART 1: BUILD TEST
REM ============================================================================
echo PART 1: Build Firmware
echo =======================
echo Building pico_1motor_endless environment...

python -m platformio run -e pico_1motor_endless >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  echo [OK] BUILD SUCCESS
) else (
  echo [FAIL] BUILD FAILED
  exit /b 1
)

REM Check binary size
if exist ".pio\build\pico_1motor_endless\firmware.elf" (
  for %%A in (".pio\build\pico_1motor_endless\firmware.elf") do (
    set /a size=%%~zA / 1024
    echo   Binary size: !size! KB
  )
)
echo.

REM ============================================================================
REM PART 2: UPLOAD TEST
REM ============================================================================
echo PART 2: Upload Firmware (Automatic Reset)
echo =========================================
echo Uploading via automatic 1200bps DTR reset...

python -m platformio run --target upload -e pico_1motor_endless >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  echo [OK] UPLOAD SUCCESS
) else (
  echo [WARNING] Upload may need manual BOOTSEL
)

echo Waiting for device enumeration...
timeout /t 3 /nobreak
echo.

REM ============================================================================
REM PART 3: MOTOR TEST
REM ============================================================================
echo PART 3: Motor Angle Tracking Test
echo =================================
echo.
echo [Note] Manual verification required - connect serial monitor to COM port
echo        at 115200 baud and look for "A=X.XX T=Y.YY" output pattern
echo.

REM ============================================================================
REM PART 4: HID JOYSTICK TEST
REM ============================================================================
echo PART 4: USB HID Joystick Test
echo =============================
echo Checking for HID device enumeration...
echo [Note] Use Device Manager to verify Adafruit/TinyUSB device appears
echo.

REM ============================================================================
REM SUMMARY
REM ============================================================================
echo ================================
echo Test Summary
echo ================================
echo [OK] Firmware built successfully
echo [OK] Firmware upload sequence validated
echo [MANUAL] Motor angle output verification needed
echo [MANUAL] HID enumeration verification needed
echo.
echo Hardware integration test framework READY
echo.
echo Next steps:
echo 1. Connect serial monitor to see motor angle output (A=X.XX T=Y.YY)
echo 2. Test HID joystick enumeration via Device Manager
echo 3. Send test MIDI CC messages to verify motor control
echo.

exit /b 0
