from Node import Node
node_name = input("Enter node name: ")

node = Node(node_name)

def on_get_data(data):
    print("[RECEIVED]:",data)
    
while True:
    target = input("Enter target name: ")
    message = input("Enter message")
    node.send(target,message)
    print(f"[SENT]: {message} to ({target})")

    

