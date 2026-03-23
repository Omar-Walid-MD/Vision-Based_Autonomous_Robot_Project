from Node import Node
import time

# Dummy node script to test stuff 
node = Node("test_1",url="http://localhost:5000")

# Example subscription method

# def get_data(data):
#     print(f"Received data:",data)

# node.subscribe("data",get_data)

while True:
    message = input("Enter message: ")
    node.send("send_data",message)

