#!/usr/bin/env python3
"""
Simple LED connection test for Raspberry Pi
Blinks 3 LEDs in sequence repeatedly

Wiring assumed (BCM numbering):
- LED 1 (shutdown)   ? GPIO 26
- LED 2 (boot/shutdown) ? GPIO 19
- LED 3 (running)    ? GPIO 13

"""

import RPi.GPIO as GPIO
import time

# === Configuration =====================================
LED_PINS = [26, 19, 13]          # BCM numbers: LED1, LED2, LED3
DELAY = 0.4                      # seconds between steps
CYCLE_PAUSE = 1.0                # pause after full sequence

# === Setup =============================================
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

for pin in LED_PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)     # start all LEDs OFF

print("LED sequence test starting...")
print("Press Ctrl+C to stop")

try:
    while True:
        # Light up one LED at a time
        for pin in LED_PINS:
            GPIO.output(pin, GPIO.HIGH)     # LED ON
            time.sleep(DELAY)
            GPIO.output(pin, GPIO.LOW)      # LED OFF
            time.sleep(DELAY / 2)           # short gap between LEDs

        # Optional: quick "all on" flash at end of cycle
        for pin in LED_PINS:
            GPIO.output(pin, GPIO.HIGH)
        time.sleep(0.3)
        for pin in LED_PINS:
            GPIO.output(pin, GPIO.LOW)

        time.sleep(CYCLE_PAUSE)             # pause before next cycle

except KeyboardInterrupt:
    print("\nStopped by user")

finally:
    # Cleanup is important on Raspberry Pi
    for pin in LED_PINS:
        GPIO.output(pin, GPIO.LOW)
    GPIO.cleanup()
    print("GPIO cleaned up all LEDs turned off")
