import serial
from enum import Enum

"""
pi -> esp:
    - localize: [x,y,r]
    - move points: [[x,y],[x,y],[x,y]...]
    - stop: stop
    
esp -> pi:
    - update: [x,y,r,bat]
    - obstacle: [left,middle,right]
    - nav_status: status = (navigating, success, failed)
"""

# class for ESP32 control (incomplete)
class ESPSerial:
    def __init__(self,port,baud_rate=115200):
        
        self.serial = serial.Serial(port,115200,timeout=1)
        pass
    
    def write(self,data):
        if not data.endswith("\n"):
            data += "\n"
        self.serial.write(data.encode("utf-8"))
        print(f"> Sent: {data.strip()}")

    def read():
        return serial.readline().decode("utf-8", errors="ignore").strip()

