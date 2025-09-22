import socketio

class Node:
    def __init__(self, node_name, on_get_data=None):
        self.sio = socketio.Client()

        self.node_name = node_name
        self.on_get_data = on_get_data
        
        @self.sio.event
        def connect():
            print(f"Node {node_name} connected")
            self.sio.emit("connect_node", node_name)

        @self.sio.event
        def get_data(data):
            print(data)
            if self.on_get_data is not None:
                self.on_get_data(data)
                
            
        def tryconnect():
            try:
                self.sio.connect('http://localhost:5000')
            except Exception as e:
                print(f"SocketIO error: {e}")
                
        tryconnect()
        
    def send(self,target,data):
        self.sio.emit("send_data",[target,data])

    
