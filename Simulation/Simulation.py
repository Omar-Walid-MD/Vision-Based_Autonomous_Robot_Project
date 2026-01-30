
from direct.showbase.ShowBase import ShowBase
from panda3d.core import loadPrcFileData
from direct.task import Task
from classes.Tag import Tag
from classes.Robot import Robot
from classes.Environment import Environment
import time
import math
import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # add parent folder to paths
from pathfinding import aStarSearch

this_directory = os.path.dirname(os.path.abspath(__file__))

confVars = """
win-size 1280 720
window-title Robot Simulation And Mapping
show-frame-rate-meter True
model-cache-dir
"""

loadPrcFileData("",confVars)

robot_size = 0.25

class Simulation(ShowBase):
    def __init__(self,show=True):
        super().__init__()
        
        self.show = show

        self.disableMouse()
        
        # load grid map
        with open(os.path.join(this_directory,"./map.json"),"r") as grid:
            data = json.load(grid)
            self.grid = data["grid"]
            self.cellSize = data["cellSize"]
            self.size = data["size"]
        
        # initialize environment and robot models
        self.env = Environment(self)
        self.robot = Robot(self,robot_size)
        
        
        
        # load april tags
        # self.tags = {}
        # with open(os.path.join(this_directory,"./tags.json"),"r") as tags:
        #     tagsList = json.load(tags)["tags"]
        #     for tag in tagsList:
        #         print(tag["id"])
        #         self.tags[tag["id"]] = Tag(self,tag["id"],tag["pos"],tag["angle"])
        
        # set robot starting position
        robot_position = self.robot.getPos()
        base.cam.setPos(robot_position.getX(),robot_position.getY(),20)
        
        # add update task
        self.taskMgr.add(self.update,"update")
        
    
    def update(self, task):
        
        self.robot.update()
        return Task.cont

    def addPointMarkers(self): 
        for i,point in enumerate(points):
            box = self.loader.loadModel("./models/box.obj")
            box.reparentTo(self.render)
            box.setPos(point[0], point[1], 0)
            box.setLightOff()
            if i == 0:
                box.setColor((0,1,0,1))
            elif i == len(points)-1:
                box.setColor((1,0,0,1))
            else:
                box.setColor((0,0,1,1))
                
    def world_to_grid(self,world_coords):
        return [
            math.floor((world_coords[0]-robot_size)/self.cellSize),
            math.floor((-world_coords[1]-robot_size)/self.cellSize),
        ]
                
    def grid_to_world(self,grid_coords):
        return [grid_coords[0]*self.cellSize+robot_size,-grid_coords[1]*self.cellSize-robot_size]

    def world_to_real(self,world_coords):
        return [world_coords[0],-world_coords[1]]

    def real_to_world(self,world_coords):
        return [world_coords[0],-world_coords[1]]
                
                
    # TOPIC FUNCTIONS
    def process_april_tag(self,data):
        print(data)
        if self.tags.get(data["id"],None) is not None:
            self.tags[data["id"]].locate(data["position"],data["rotation"])
        else:
            print("Tag not found in map")

    def process_move_to(self,name):
        global points
        global point_index
        point_index = 0
        
        start = self.world_to_grid(self.position)
        end = location_name[name]
        points = aStarSearch(self.grid,start,end)
        points = [self.grid_to_world(p) for p in points]
        points[0] = [self.position[0],self.position[1]]
        self.addPointMarkers()
        
        
    # def stop_process(self,data):
    #     global points
    #     global point_index
    #     point_index = 0
    #     points = []
        
    # def process_transform(self, data):
    #     self.position = (data["x"], data["y"], 0)
    #     self.robot.setPos(self.position)
    #     self.robot.setH(data["h"])
        

             


