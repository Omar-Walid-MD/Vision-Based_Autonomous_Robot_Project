import asyncio
import socketio
from aiohttp import web
import threading
import os
from colorama import Fore, Back, Style
import json
import signal
import sys
import time
from server_state import connected_clients, map_data, nodes, robot_components
from RemoteClientHandler import RemoteClientHandler
from dotenv import load_dotenv
load_dotenv()
env = os.environ.copy()
platform = os.getenv("PLATFORM")



# SERVER SETUP
sio = socketio.AsyncServer(cors_allowed_origins="*")
app = web.Application()
sio.attach(app)

remoteClientHandler = RemoteClientHandler(sio)

def handle_exit(signum, frame):
    """Handle termination signals."""
    print("\nReceived exit signal, shutting down...")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, handle_exit)   # Ctrl+C
signal.signal(signal.SIGTERM, handle_exit)  # kill command

if platform == "WINDOWS":
    signal.signal(signal.SIGBREAK, handle_exit)
else:
    signal.signal(signal.SIGHUP, handle_exit)   # Close window

nodes_status = {}

MAP_PATH = os.getenv("MAP_PATH")

with open(MAP_PATH, "r") as f:
    map_data = json.load(f)

# SERVER EVENTS
@sio.event
async def connect(sid, environ):
    # print(f"Client connected: {sid}")
    pass

@sio.event
async def disconnect(sid):
    print("a node disconnected")
    node = get_node(sid)
    if node is not None:
        del nodes_status[node]  
        print(f"Module '{node}' disconnected ({sid})")

@sio.event
async def connect_node(sid, node):
    print(f"Module '{node}' connected ({sid})")
    nodes_status[node] = sid
    
@sio.event
async def join_topic(sid, topic):
    await sio.enter_room(sid=sid,room=topic)
    print(f"({sid}) Subscribed to topic: {topic}")

@sio.event
async def send_data(sid, data):
    topic, payload = data
    print(f"Sending data ({payload}) to room: ({topic})")
    await sio.emit("get_data",[topic,payload],to=topic)

@sio.event
async def start_shutdown(sid):
    await sio.emit("shutdown")
    print("shutting down")
    if platform == "RPI":
        await asyncio.sleep(2)
        os.system("sudo shutdown -h now")
        
@sio.event
async def register_client(sid):
    await remoteClientHandler.client_connected(sid)





# FUNCTIONS

def get_node(sid):
    for k,v in nodes_status.items():
        if v == sid:
            return k
    return None 

def start():
    print_status()
        
        
def print_status():
    # clear_terminal()
    for node in nodes:
        sid = nodes_status.get(node,None)
        print(f"{Fore.GREEN if sid else Fore.RED}{node} {': '+sid if sid else ''}{Style.RESET_ALL}")
    
            
            
    timer = threading.Timer(1,print_status)
    timer.daemon = True
    timer.start()


def clear_terminal():
    if os.name == 'nt':  # For Windows
        _ = os.system('cls')
    else:  # For macOS and Linux
        _ = os.system('clear')
        
        
# NAME
if __name__ == '__main__':
    threading.Timer(1,start).start()
    web.run_app(app, port=5000)
