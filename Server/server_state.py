# server_state.py
nodes = ["navigation","camera0","camera1","voice","peripherals","behaviour"]

robot_components = {
    "navigation": True,
    "camera": True,
    "voice": True,
    "peripherals": True,
    "behavior": True
}

robot_tasks = [
    {"id":100,"type":"delivery","args":{"dest":"room 1"},"status":"pending","received":1777885679495,"started":0,"done":0},
    {"id":101,"type":"fetch","args":{"dest":"room 1"},"status":"running","received":1777885373495,"started":1777885374495,"done":0},
    {"id":102,"type":"checkup","args":{"dest":"room 1"},"status":"completed","received":1777885373495,"started":1777885374495,"done":1777885874495},
    {"id":103,"type":"checkup","args":{"dest":"room 1"},"status":"failed","received":1777885373495,"started":1777885374495,"done":1777885874495}
]

robot_position = [8,15,90] # x, y, rotation degrees

map_data = None

connected_clients = set()