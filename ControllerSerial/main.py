import serial
import os
import sys
import time
from dotenv import load_dotenv
load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # add parent folder to paths
from Server.Node import Node

node = Node("controller-serial")

platform = os.getenv("PLATFORM")
port = os.getenv("SERIAL_PORT")

ser = serial.Serial(port,115200,timeout=1)

def send_moves_to_esp(data):
    if not data.endswith("\n"):
        data += "\n"
    ser.write(data.encode("utf-8"))
    print(f"> Sent: {data.strip()}")

send_moves_to_esp("ping")

try:
    while True:
        if ser.in_waiting > 0:
            data = ser.readline().decode("utf-8", errors="ignore").strip()
            if data:
                print(data)
        time.sleep(0.05)
        count += 1

except KeyboardInterrupt:
    print("Exiting...")
finally:
    ser.close()
