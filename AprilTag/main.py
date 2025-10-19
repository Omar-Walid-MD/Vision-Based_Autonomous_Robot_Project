from AprilTagCam import AprilTagCam
import os
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # add parent folder to paths
from Server.Node import Node

if __name__ == "__main__":
    node = Node("camera")
    cam = AprilTagCam()
    while True:
        result = cam.detect()
        if result:
            # print(result["rotation"])
            node.send("april_tag_data",result)
        