from adafruit_servokit import ServoKit


class Servo:
    def __init__(self,channel):
        self.kit = ServoKit(channels=16)
        self.channel = channel
        self.current_angle = 90
        self.move_to_angle(90)
        pass

    def move_to_angle(self,angle):
        self.current_angle = angle
        self.kit.servo[self.channel].angle = self.current_angle

    def move(self,angle):
        self.current_angle = max(min(180,self.current_angle+angle),0)
        self.kit.servo[self.channel].angle = self.current_angle


    
