from AprilTagCam import AprilTagCam
import os
import sys
import signal
import atexit
import time
from dotenv import load_dotenv
load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # add parent folder to paths
from Server.Node import Node
from ControllerSerial.CommandChar import CommandChar

node = Node("camera")
cam = AprilTagCam()
platform = os.getenv("PLATFORM")

robot_stopped = False # robot should stop to take accurate reads from april tag
last_tag_date = 0

def cleanup():
    print("Running cleanup...")
    cam.close()
    
def handle_sigterm(signum, frame):
    sys.exit(0)
    
def now():
    return int(time.time_ns()//1000)
    
def read_april_tag():
    global robot_stopped, last_tag_date
    
    # code to read april tags. may need to read multiple times to get average reading and eliminate noise or use other logic
    result = cam.detect()
    print("Found Tag")
    node.send("april_tag_data",result)
    robot_stopped = False
    last_tag_date = now()
    

if __name__ == "__main__":    
    
    atexit.register(cleanup)
    
    # Handle Ctrl+C and termination
    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)
    if platform == "WINDOWS":
        signal.signal(signal.SIGBREAK, handle_sigterm)
    else:
        signal.signal(signal.SIGHUP, handle_sigterm)   # Close window

    node.subscribe("robot_stop_acknowledge",read_april_tag)
   
    while True:
        result = cam.detect()
        if result:
            if not robot_stopped and last_tag_date - now() > 30*1000:
                print("Tag detected for reading. stopping to read accurately...")
                node.send("write_command",CommandChar.STOP)
                robot_stopped = True
                
        
