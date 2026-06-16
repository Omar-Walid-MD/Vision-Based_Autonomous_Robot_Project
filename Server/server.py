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

# How often (seconds) the server broadcasts the active-nodes list to behaviour
NODE_STATUS_BROADCAST_INTERVAL = 2.0

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
        # Immediately notify behaviour of the updated node list
        await broadcast_nodes_status()

@sio.event
async def connect_node(sid, node):
    print(f"Module '{node}' connected ({sid})")
    nodes_status[node] = sid
    # Immediately notify behaviour of the updated node list
    await broadcast_nodes_status()

@sio.event
async def node_error(sid, data):
    """
    Nodes emit this event when a fatal/unexpected error occurs.
    data: {"node": "<name>", "error": "<message>"}
    We relay it to the behaviour node via the 'node/error' topic.
    """
    node_name = get_node(sid) or data.get("node", "unknown")
    payload   = {"node": node_name, "error": data.get("error", "unknown error")}
    print(f"[Server] Node error from '{node_name}': {payload['error']}")
    await sio.emit("get_data", ["node/error", payload], to="node/error")
    
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


# REMOTE EVENT HANDLER
# remoteClientHandler = RemoteClientHandler(sio)

# async def status_broadcaster():
#     while True:
#         await remoteClientHandler.broadcast_status()
#         await asyncio.sleep(2)
        
# async def on_startup(app):
#     app["broadcast_task"] = asyncio.create_task(
#         status_broadcaster()
#     )
# app.on_startup.append(on_startup)


# FUNCTIONS

async def broadcast_nodes_status():
    """Emit the current list of connected node names to the 'server/nodes_status' topic."""
    active_nodes = list(nodes_status.keys())
    await sio.emit("get_data", ["server/nodes_status", {"nodes": active_nodes}],
                   to="server/nodes_status")

async def nodes_status_broadcaster():
    """Background task: periodically pushes active-node list to behaviour."""
    while True:
        await broadcast_nodes_status()
        await asyncio.sleep(NODE_STATUS_BROADCAST_INTERVAL)

async def on_startup(app):
    app["nodes_broadcast_task"] = asyncio.create_task(nodes_status_broadcaster())

app.on_startup.append(on_startup)


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
