import serial
from enum import Enum

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


class CommandChar(str, Enum):
    APRIL_TAG_SEARCH    = "A",
    MOVE_TO_POINTS      = "M",
    ROTATE              = "R",
    STOP                = "S",
    STOP_ACK            ="s",
    SEPARATOR = ":"