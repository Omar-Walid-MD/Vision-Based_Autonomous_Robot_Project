import serial
import os
import sys
import time
import json
from dotenv import load_dotenv
load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # add parent folder to paths
from Server.Node import Node
from CommandChar import CommandChar


platform = os.getenv("PLATFORM")
port = os.getenv("SERIAL_PORT")

ser = serial.Serial(port,115200,timeout=1)


# SERIAL FUNCTIONS
def write_to_serial(data):
    if not data.endswith("\n"):
        data += "\n"
    ser.write(data.encode("utf-8"))
    print(f"> Sent: {data.strip()}")

def read_from_serial():
    return ser.readline().decode("utf-8", errors="ignore").strip()


# TOPIC FUNCTIONS
def write_command_to_serial(args):
    command = args[0]
    
    if command == CommandChar.APRIL_TAG_SEARCH:
        print("send april tag search")
        write_to_serial(CommandChar.APRIL_TAG_SEARCH)
        
    elif command == CommandChar.STOP:
        write_to_serial(CommandChar.STOP)
        
    elif command == CommandChar.MOVE_TO_POINTS:
        points = json.dumps(args[1])
        print(points)
        write_to_serial(CommandChar.MOVE_TO_POINTS + CommandChar.SEPARATOR + points)

def write_stop_to_serial(args):
    write_to_serial(CommandChar.STOP)
    
def handle_received_command(args):
    
    if args == CommandChar.STOP_ACK:
        print("Received Stop Acknowledge")
        node.send("robot_stop_acknowledge",True)

    
if __name__ == "__main__":
    
    node = Node("controller-serial")

    node.subscribe("write_command",write_command_to_serial)
    node.subscribe("stop",write_stop_to_serial)
    
    try:
        while True:
            if ser.in_waiting > 0:
                data = read_from_serial()
                print(data)
                if data[0] == "$":
                    handle_received_command(data[1:])
                    
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        ser.close()
