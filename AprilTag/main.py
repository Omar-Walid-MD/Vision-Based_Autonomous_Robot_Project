from AprilTagCam import AprilTagCam
import os
import sys
import signal
import atexit
from dotenv import load_dotenv
load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # add parent folder to paths
from Server.Node import Node

if __name__ == "__main__":
    
    node = Node("camera")
    cam = AprilTagCam()
    platform = os.getenv("PLATFORM")

    
    def cleanup():
        print("Running cleanup...")
        cam.close()
    
    def handle_sigterm(signum, frame):
        sys.exit(0)
    
    atexit.register(cleanup)
    
    # Handle Ctrl+C and termination
    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)
    if platform == "WINDOWS":
        signal.signal(signal.SIGBREAK, handle_sigterm)
    else:
        signal.signal(signal.SIGHUP, handle_sigterm)   # Close window

   
    while True:
        result = cam.detect()
        if result:
            print("Found Tag")
            node.send("april_tag_data",result)
        
