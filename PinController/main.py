import RPi.GPIO as GPIO
import time

# GPIO pins
TRIG = 23
ECHO = 24

GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)

def get_distance():
    # Send 10us pulse to TRIG
    # ~ s = time.time()
    GPIO.output(TRIG, True)
    time.sleep(0.00001)   # 10 microseconds
    GPIO.output(TRIG, False)

    # Wait for ECHO to go HIGH
    while GPIO.input(ECHO) == 0:
        pulse_start = time.time()

    # Wait for ECHO to go LOW
    while GPIO.input(ECHO) == 1:
        pulse_end = time.time()

    pulse_duration = pulse_end - pulse_start

    # Distance in cm
    distance = pulse_duration * 17150   # speed of sound/2
    # ~ print((time.time()-s)*1000,"ms")
    return round(distance, 2)

try:
    while True:
        dist = get_distance()
        print("Distance:", dist, "cm")
        time.sleep(0.25)

except KeyboardInterrupt:
    print("Cleaning up...")
    GPIO.cleanup()
