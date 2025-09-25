from Node import Node

node = Node("camera",url="http://localhost:5000")

def sim_request(data):
    print(f"Received Data from Simulation:",data)

node.subscribe("simulation_request",sim_request)

while True:
    message = input("Enter message: ")
    node.send("april_tag_data",message)  #example only

    

