
from direct.showbase.ShowBase import ShowBase
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import loadPrcFileData, TextNode
from direct.task import Task
from classes.Robot import Robot
from classes.Environment import Environment
from classes.GridVisualizer import GridVisualizer
from classes.OrbitCamera import OrbitCamera
import time
import math
import json
import sys
import os
from pathfinding import marginizeGrid
from queue import Queue


this_directory = os.path.dirname(os.path.abspath(__file__))

confVars = """
    win-size 1280 720
    window-title Robot Simulation And Mapping
    show-frame-rate-meter True
    model-cache-dir
"""
loadPrcFileData("",confVars)


mapDir = "./map"
robotSize = 0.5

class Simulation(ShowBase):
    def __init__(self,args,node):
        super().__init__(windowType='none' if not args.show else None)
        
        self.show = args.show
        self.sim = args.sim
        self.node = node
        
        self.disableMouse()
        
        # load grid map
        with open(os.path.join(this_directory,mapDir,"./map.json"),"r") as map:
            data = json.load(map)["robot_data"]
            self.cellSize = data["cell_size"]
            self.tags = data["tags"]
            
            self.grid =  marginizeGrid(data["grid"],self.cellSize,robotSize)
            
            # convert zone list into dict
            self.zones = {}
            for zone in data["zones"]:
                self.zones[zone["name"]] = zone
        
        # initialize environment and robot models
        self.env = Environment(self,mapDir)
        self.robot = Robot(self,robotSize)
        
        self.tag_queue = Queue()    
        
        if self.show:
            self.gridVisualizer = GridVisualizer(self)

        # set robot starting position
        robot_position = self.robot.getPos()
        
        if len(self.zones.values()):
            zone_verts = list(self.zones.values())[0]["vertices_grid"]
            x = sum(v[0] for v in zone_verts)/len(zone_verts)
            y = sum(v[1] for v in zone_verts)/len(zone_verts)
            pos = self.grid_to_sim([x,y])
            self.robot.setPos(pos[0],pos[1],robot_position.getZ())
        
        robot_position = self.robot.getPos()
        
        
        if self.show:
            # base.cam.setPos(robot_position.getX(),robot_position.getY(),20)

            self.pos_label = OnscreenText(
                text="",
                pos=(-1.7, 0.9),   # top-left corner
                scale=0.08,
                fg=(1, 1, 1, 1),
                align=TextNode.ALeft,
                mayChange=True
            )
            
            self.taskMgr.add(self.update_ui, "update_ui")

        self.taskMgr.add(self.update,"update")
        
        def handle_tag_found(data):
            if isinstance(data, str):
                data = json.loads(data)

            tags = data.get("tags", [])

            if not tags:
                return

            closest_tag = min(tags, key=lambda tag: tag["distance"])

            self.tag_queue.put(closest_tag)
            
            
        
        def handle_navigation_command(data):
            
            action = data["action"]
            
            if action == "move_to_charger":
                if "charger" in self.zones: # zone name for charging must match this
                    self.robot.navigate_to_location("charger")
                else:
                    print("error: charging location not found")
                    
            elif action == "estop":
                self.robot.stop()
            
            
        self.node.subscribe("camera/tags_found",handle_tag_found)
        self.node.subscribe("navigation/command",handle_navigation_command)
        
        # def handle_navigation_continue(data):
        #     self.robot.next_move()
                    
        # self.node.subscribe("navigation/continue",handle_navigation_continue)

        self.camera_controller = OrbitCamera(base, self.robot)
        
        self.robot.navigate_to_location("charger")
        
    
    def update(self, task):
        
        self.process_tag_updates()
        self.robot.update()
        
        return Task.cont

    def update_ui(self, task):
        world_pos = self.robot.getPos()
        grid_pos = self.sim_to_grid([world_pos[0],world_pos[1]])

        self.pos_label.setText(
            f"World: ({world_pos.x:.2f}, {world_pos.y:.2f}, {world_pos.z:.2f})\n"
            f"Grid: ({grid_pos[0]}, {grid_pos[1]})\n"
            f"Battery level: {int(self.robot.status.batteryLevel)}%"
        )

        return task.cont


    def world_to_grid(self,world_coords):
        return [
            math.floor((world_coords[0] - self.cellSize/2)/self.cellSize),
            math.floor((world_coords[1] - self.cellSize/2)/self.cellSize),
        ]
                
    def grid_to_world(self,grid_coords):
        return [
            grid_coords[0]*self.cellSize + self.cellSize/2,
            grid_coords[1]*self.cellSize + self.cellSize/2
        ]
        # return [grid_coords[0]*self.cellSize+self.cellSize/2+self.robot.size/4,grid_coords[1]*self.cellSize+self.cellSize/2+self.robot.size/4]

    def grid_to_sim(self,grid_coords):
        return self.world_to_sim(self.grid_to_world(grid_coords))

    def sim_to_grid(self,sim_coords):
        return self.world_to_grid(self.sim_to_world(sim_coords))
    
    def world_to_sim(self,world_coords):
        return [world_coords[0],-world_coords[1]]

    def sim_to_world(self,sim_coords):
        return [sim_coords[0],-sim_coords[1]]
    
                
                
    
            
    def process_tag_updates(self):

        while not self.tag_queue.empty():

            data = self.tag_queue.get()

            tag_id = data["id"]

            pos, hpr = self.tags[tag_id]["object"].locate_robot(
                data["pose"]["position"],
                data["pose"]["rotation"],
                (0,0,0), 0,
                (0,0,0), 0
            )

            self.robot.setPos(pos)
            self.robot.setHpr(hpr)

            print("tag found")

        return

        
        

             


