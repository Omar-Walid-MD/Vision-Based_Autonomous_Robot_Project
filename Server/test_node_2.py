from Node import Node
import time

node = Node("test_2",url="http://localhost:5000")

def get_data(data):
    print(f"Received data from a:",data)

node.subscribe("send_to_b",get_data)

while True:
    message = input("Enter message: ")
    node.send("send_to_a",message)
    time.sleep(0.1)
