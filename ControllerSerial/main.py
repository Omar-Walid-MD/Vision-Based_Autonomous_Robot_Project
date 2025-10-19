import serial
import os
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # add parent folder to paths
from Server.Node import Node

node = Node("controller-serial")

platform = os.getenv("PLATFORM")
port = os.getenv("SERIAL_PORT")

ser = serial.Serial(port,115200)
    
def send_moves_to_esp(data):
    ser.write(bytes(data,"utf-8"))
    
node.subscribe("controller_moves",send_moves_to_esp)

send_moves_to_esp("ping")

while True:
    try:    
        if ser.in_waiting:
            data = ser.readline().decode(errors="ignore").strip()
            if data:
                print(data)
    except Exception as e:
        print(e)
        break
