import socketio

class Node:
    def __init__(self, node_name, url="http://localhost:5000"):
        self.sio = socketio.Client()

        self.node_name = node_name
        self.topics = {}
        self.connected = False
        
        @self.sio.event
        def connect():
            print(f"Node {node_name} connected")
            self.sio.emit("connect_node", node_name)
            self.connected = True

        @self.sio.event
        def get_data(data):
            topic, payload = data
            topicFunction = self.topics.get(topic,None)
            if topicFunction is not None:
                topicFunction(payload)
                
            
        def tryconnect():
            try:
                self.sio.connect(url)
            except Exception as e:
                print(f"SocketIO error: {e}")
                
        tryconnect()
        
    def send(self,topic,data):
        if self.connected:
            self.sio.emit("send_data",[topic,data])
        else:
            print("Node not connected!")
    
    def subscribe(self,topic,function):
        if self.connected:
            self.sio.emit("join_topic", topic)
            self.topics[topic] = function
        else:
            print("Node not connected!")
        
    def emit(self,event):
        if self.connected:
            self.sio.emit(event)
        else:
            print("Node not connected!")

        

    
