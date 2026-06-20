import serial
import struct
from classes.RobotStatus import RobotStatus, NavStatus
import os
env = os.environ.copy()
platform = os.getenv("PLATFORM")

batLed = None
if(platform == "RPI"):
    from rpi_ws281x import PixelStrip, Color
    batLed = PixelStrip(1,18)
    batLed.begin()
    
BATTERY_COLORS = [
    (90, (0, 255, 0)),      # green
    (70, (128, 255, 0)),
    (50, (255, 255, 0)),
    (30, (255, 128, 0)),
    (10, (255, 0, 0)),
    (0,  (128, 0, 0)),
]

def set_battery_led(percent):

    percent = max(0, min(100, int(percent)))
    for threshold, color in BATTERY_COLORS:
        if percent >= threshold:
            r, g, b = color
            batLed.setPixelColor(
                0,
                Color(r, g, b)
            )
            batLed.show()
            return

"""
pi -> esp:
    - localize: [x,y,r]
    - move points: [[x,y],[x,y],[x,y]...]
    - stop: stop
    
esp -> pi:
    - transform: [x,y,r]
    - battery_level: bat_percent_float
    - nav_status: status = (idle, navigating, success, failed)
    - recharging: boolean
"""

MSG_MOVE_COMPLETED = 0x01
MSG_BATTERY   = 0x02
MSG_NAV       = 0x03
MSG_RECHARGING = 0x04
MSG_OBSTACLE = 0x05

MSG_STOP = "stop"

# class for ESP32 control (incomplete)
class ESPSerial:
    def __init__(self,port,status:RobotStatus=None,robot=None,baud_rate=115200):
        
        self.serial = serial.Serial(port,baud_rate,timeout=1)
        self.status = status
        self.robot = robot
        pass
    
    
    def write(self,data):
        if not data.endswith("\n"):
            data += "\n"
        self.serial.write(data.encode("utf-8"))
        print(f"> Sent: {data.strip()}")

    def read(self):
        return self.serial.readline().decode("utf-8", errors="ignore").strip()
    
    
    def sendStop(self):
        self.write(MSG_STOP)

    def update(self):
        while self.serial.in_waiting > 0:
            header = self.serial.read(1)

            if len(header) == 0:
                return

            msg_type = header[0]
            
            if msg_type == MSG_MOVE_COMPLETED:
                self.robot.next_move()

            # BATTERY
            elif msg_type == MSG_BATTERY:
                data = self.serial.read(1)
                if len(data) < 1:
                    return

                (bat,) = struct.unpack('<B', data)

                self.status.batteryLevel = bat
                print(f"Battery: {bat}%")
                
                if(platform == "RPI"):
                    set_battery_led(bat)

            # NAV STATUS
            elif msg_type == MSG_NAV:
                data = self.serial.read(1)
                if len(data) < 1:
                    return

                navStatus = NavStatus(data[0])
                self.status.navStatus = navStatus
                self.robot.node.send("navigation/status",navStatus)
                print(f"Nav status: {navStatus}")
                
            # RECHARGING STATUS
            elif msg_type == MSG_RECHARGING:
                data = self.serial.read(1)
                if len(data) < 1:
                    return

                recharging = struct.unpack('?', data)
                self.status.recharging = recharging

                self.robot.node.send("recharging/status",recharging)
                print(f"Recharging set to: {recharging}")
                
            elif msg_type == MSG_OBSTACLE:
                data = self.serial.read(2)

                if len(data) < 2:
                    return

                location, distance_cm = struct.unpack('<BB', data)

                distance = distance_cm / 100.0

                self.status.obstacleLocation = location
                self.status.obstacleDistance = distance

                print(
                    f"Obstacle: location={location} "
                    f"distance={distance:.2f}m"
                )

                self.robot.handle_obstacle(location, distance)
                

            else:
                print("Unknown message type:", msg_type)
                


