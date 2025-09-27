from Node import Node
    
node = Node("simulation",url="http://localhost:5000")

def sfsfs(data):
    print(f"Received April Tag Data from Camera:",data)

node.subscribe("april_tag_data",sfsfs)

while True:
    message = input("Enter message: ")
    node.send("simulation_request",message) #example only
