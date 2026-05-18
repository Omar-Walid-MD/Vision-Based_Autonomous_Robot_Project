from enum import Enum

class RobotStatus:
    def __init__(self):
        
        self.batteryLevel = 100
        self.navStatus = NavStatus.IDLE
        self.transform = [0,0,0]
        
        
        
class NavStatus(Enum):
    IDLE = 0 # not moving yet
    NAVIGATING = 1 # currently navigating
    SUCCESS = 2 # target reached
    FAILED = 3
    