import serial
import struct
from classes.RobotStatus import RobotStatus, NavStatus
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

MSG_TRANSFORM = 0x01
MSG_BATTERY   = 0x02
MSG_NAV       = 0x03
MSG_RECHARGING = 0x04

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

            # TRANSFORM
            if msg_type == MSG_TRANSFORM:
                data = self.serial.read(12)
                if len(data) < 12:
                    return

                x, y, r = struct.unpack('<fff', data)
                self.status.transform = [x,y,r]
                print(f"Transform: x={x}, y={y}, r={r}")

            # BATTERY
            elif msg_type == MSG_BATTERY:
                data = self.serial.read(4)
                if len(data) < 4:
                    return

                (bat,) = struct.unpack('<f', data)
                self.status.batteryLevel = bat
                print(f"Battery: {bat}%")

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

            else:
                print("Unknown message type:", msg_type)
                


    