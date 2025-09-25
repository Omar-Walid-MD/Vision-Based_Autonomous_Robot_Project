import asyncio
import socketio
from aiohttp import web
import threading
import os
import subprocess
from colorama import Fore, Back, Style
import json


# ENABLE CORS
@web.middleware
async def cors_middleware(request, handler):
    # Handle preflight OPTIONS request
    if request.method == "OPTIONS":
        resp = web.Response(status=200)
    else:
        resp = await handler(request)

    # Add CORS headers
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp

# SERVER SETUP
sio = socketio.AsyncServer(cors_allowed_origins="*")
app = web.Application(middlewares=[cors_middleware])
sio.attach(app)


def handle_get(request):
    return web.Response(text="Welcome to the server!!")
    
app.router.add_get("/",handle_get)

# STATES
# with open ("./nodes.json","r") as file:
#     nodes = json.load(file)["nodes"]

nodes = ["simulation","camera","distance","wheels","remote_client"]
nodes_status = {}
logs = []

# SERVER EVENTS
@sio.event
async def connect(sid, environ):
    # print(f"Client connected: {sid}")
    pass

@sio.event
async def disconnect(sid):
    node = get_node(sid)
    del nodes_status[node]  
    print_log(f"Module '{node}' disconnected ({sid})")

@sio.event
async def connect_node(sid, node):
    print_log(f"Module '{node}' connected ({sid})")
    nodes_status[node] = sid
    
@sio.event
async def join_topic(sid, topic):
    await sio.enter_room(sid=sid,room=topic)
    print_log(f"({sid}) Subscribed to topic: {topic}")
    

@sio.event
async def send_data(sid, data):
    topic, payload = data
    print_log(f"sending to room {topic}")
    await sio.emit("get_data",[topic,payload],to=topic)

    
    
    # target_sid = nodes_status.get(data[0],None)
    # if target_sid is not None:
    #     sender_node = get_node(sid)
    #     print_log(sender_node+" "+target_sid)


# FUNCTIONS

def get_node(sid):
    for k,v in nodes_status.items():
        if v == sid:
            return k
    return None 

def start_nodes():
    # print_log("Starting Nodes...")
    # for node in nodes:
    #     subprocess.Popen(["start","cmd","/k",f"python ./{node}.py"],shell=True)
    print_status()
        
        
def print_status():
    clear_terminal()
    for node in nodes:
        sid = nodes_status.get(node,None)
        print(f"{Fore.GREEN if sid else Fore.RED}{node} {': '+sid if sid else ''}{Style.RESET_ALL}")
    if len(logs) > 0:
        print("=====================")
        for log in logs:
            print(log)
            
            
    timer = threading.Timer(1,print_status)
    timer.daemon = True
    timer.start()

def print_log(log):
    global logs
    logs.append(log)
    if len(logs) > 5:
        logs = logs[1:]

def clear_terminal():
    if os.name == 'nt':  # For Windows
        _ = os.system('cls')
    else:  # For macOS and Linux
        _ = os.system('clear')
        
        
# NAME
if __name__ == '__main__':
    threading.Timer(1,start_nodes).start()
    web.run_app(app, port=5000)
