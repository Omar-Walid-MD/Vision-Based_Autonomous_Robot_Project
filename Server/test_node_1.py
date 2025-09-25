from Node import Node
    
node = Node("simulation",url="http://localhost:5000")

def get_april_tag(data):
    print(f"Received April Tag Data from Camera:",data)

node.subscribe("april_tag_data",get_april_tag)

while True:
    message = input("Enter message: ")
    node.send("simulation_request",message) #example only

    

