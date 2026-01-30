import RPi.GPIO as GPIO
import time
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # add parent folder to paths
from Server.Node import Node
from Servo import Servo

    


if __name__ == "__main__":
    node = Node("pins")
    servo = Servo(14)

    def move_cam(position):
        print(position)
        servo.move(int(-position[0]*100))
        print(servo.current_angle)

    node.subscribe("move_cam",move_cam)





