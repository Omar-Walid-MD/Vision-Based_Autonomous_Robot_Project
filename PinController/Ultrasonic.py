import RPi.GPIO as GPIO
import time

# GPIO pins
# TRIG = 23
# ECHO = 24

class Ultrasonic:
    def __init__(self,echo,trig):
        self.echo = echo
        self.trig = trig

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.trig, GPIO.OUT)
        GPIO.setup(self.echo, GPIO.IN)
        pass

    def get_distance(self):
        # Send 10us pulse to TRIG
        # ~ s = time.time()
        GPIO.output(self.trig, True)
        time.sleep(0.00001)   # 10 microseconds
        GPIO.output(self.trig, False)

        # Wait for ECHO to go HIGH
        while GPIO.input(self.echo) == 0:
            pulse_start = time.time()

        # Wait for ECHO to go LOW
        while GPIO.input(self.echo) == 1:
            pulse_end = time.time()

        pulse_duration = pulse_end - pulse_start

        # Distance in cm
        distance = pulse_duration * 17150   # speed of sound/2
        # ~ print((time.time()-s)*1000,"ms")
        return round(distance, 2)