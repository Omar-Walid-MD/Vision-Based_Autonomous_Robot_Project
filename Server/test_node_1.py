from Node import Node
import time

node = Node("test_1",url="http://localhost:5000")

# def get_data(data):
#     print(f"Received data from b:",data)

# node.subscribe("send_to_a",get_data)

while True:
    message = input("Enter message: ")
    node.send("move_to",message)

