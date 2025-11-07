from Node import Node
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # add parent folder to paths
from ControllerSerial.CommandChar import CommandChar
node = Node("voice",url="http://192.168.1.4:5000")

# def sfsfs(data):
#     print(f"Received April Tag Data from Camera:",data)

# node.subscribe("april_tag_data",sfsfs)

while True:
    message = input("Enter message: ")
    if message == "a":
        node.send("write_command",[CommandChar.APRIL_TAG_SEARCH])
    elif message == "s":
        node.send("write_command",[CommandChar.STOP])

