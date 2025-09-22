from Node import Node
node_name = input("Enter node name: ")


def on_get_data(data):
    print("[RECEIVED]:",data)
    
node = Node(node_name,url="http://192.168.1.4:5000",on_get_data=on_get_data)

while True:
    target = input("Enter target name: ")
    message = input("Enter message: ")
    node.send(target,message)
    print(f"[SENT]: {message} to ({target})")

    

