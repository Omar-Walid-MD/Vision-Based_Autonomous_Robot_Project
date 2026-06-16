import socketio
import os
import sys
import traceback


class Node:
    def __init__(self, node_name, url="http://localhost:5000", skip_connection=False):
        self.sio = socketio.Client()
    
        self.node_name = node_name
        self.topics = {}
        self.connected = False
        
        # connect to server and register node name
        
        @self.sio.event
        def connect():
            print(f"Node {node_name} connected")
            self.sio.emit("connect_node", node_name)
            self.connected = True

        # receive and handle data using topic subscription callback
        @self.sio.event
        def get_data(data):
            topic, payload = data

            topicFunction = self.topics.get(topic, None)
            if topicFunction is not None:
                topicFunction(payload)
        
        # shutdown attached node process      
        @self.sio.event
        def shutdown():
            print("shutting down node")
            os._exit(0)
                
            
        def tryconnect():
            try:
                self.sio.connect(url)
            except Exception as e:
                print(f"SocketIO error: {e}")
        
        if not skip_connection:       
            tryconnect()

        # Install a global exception hook so any unhandled exception in this
        # process is reported to the server before the process exits.
        _node_ref = self

        def _global_exception_handler(exc_type, exc_value, exc_tb):
            """Report fatal errors to the behaviour tree via the server."""
            error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            print(f"[Node:{node_name}] FATAL ERROR:\n{error_msg}")
            try:
                if _node_ref.connected:
                    _node_ref.sio.emit("node_error", {
                        "node":  node_name,
                        "error": str(exc_value) or repr(exc_value),
                    })
                    # Give the emit a moment to flush before the process dies
                    import time
                    time.sleep(0.5)
            except Exception:
                pass  # Don't recurse into another error
            # Call the default handler (prints traceback)
            sys.__excepthook__(exc_type, exc_value, exc_tb)

        sys.excepthook = _global_exception_handler
    
    # send data on topic
    def send(self, topic, data=None):
        if self.connected:
            print(f"Sending data ({data}) to topic: ({topic})")
            self.sio.emit("send_data", [topic, data])
        else:
            print("Node not connected!")
    
    # subscribe to topic
    def subscribe(self, topic, function):
        if self.connected:
            self.sio.emit("join_topic", topic)
            self.topics[topic] = function
        else:
            print("Node not connected!")
    
    # emit socket event    
    def emit(self, event):
        if self.connected:
            self.sio.emit(event)
        else:
            print("Node not connected!")

    # report a handled error to the server (behaviour tree will halt)
    def report_error(self, message: str):
        """
        Call this from any node to report a non-fatal but significant error
        that should halt the behaviour tree (e.g. sensor failure, hardware
        fault) without crashing the process.
        """
        print(f"[Node:{self.node_name}] Reporting error: {message}")
        if self.connected:
            self.sio.emit("node_error", {
                "node":  self.node_name,
                "error": message,
            })