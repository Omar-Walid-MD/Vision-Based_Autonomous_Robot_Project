
from direct.showbase.ShowBase import ShowBase
from panda3d.core import loadPrcFileData, DirectionalLight, AmbientLight, Vec3
from direct.task import Task
from Tag import Tag
from classes.Robot import Robot
from classes.Environment import Environment
import time
import math
import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # add parent folder to paths
from pathfinding import aStarSearch
from Server.Node import Node

this_directory = os.path.dirname(os.path.abspath(__file__))

confVars = """
win-size 1280 720
window-title Robot Simulation And Mapping
show-frame-rate-meter True
model-cache-dir
"""
location_name = {
    "a":[1,1],
    "b":[10,10],
    "c": [20,20],
    "d":[30,30]
}
loadPrcFileData("",confVars)

points = []
point_index = 0

move_speed = 2
rotation_speed = 180
robot_size = 0.25

def normalize_vector(vector):
    sum_of_squares = sum(x**2 for x in vector)
    magnitude = math.sqrt(sum_of_squares)
    if magnitude == 0:
        return vector
    normalized_vector = [x / magnitude for x in vector]
    return normalized_vector

def angle_between_points(current, target):
    dx = target[0] - current[0]
    dy = target[1] - current[1]
    return math.atan2(dy, dx)

def distance_between_points(current, target):
    dx = target[0] - current[0]
    dy = target[1] - current[1]
    return math.sqrt(dx**2 + dy**2)
    

class MyApp(ShowBase):
    def __init__(self):
        super().__init__()
                        
        self.disableMouse()
        
        # load grid map
        with open(os.path.join(this_directory,"./grid.json"),"r") as grid:
            data = json.load(grid)
            self.grid = data["grid"]
            self.cellSize = data["cellSize"]
            self.size = data["size"]
        
        # initialize environment and robot models
        self.env = Environment(self)
        self.robot = Robot(self)
        
        # set up camera and lighting
        base.cam.setHpr(0, -90, 0)
        
        dlight = DirectionalLight("light")
        self.render.setLight(self.render.attachNewNode(dlight))
        dlight.setPoint((2,28,100))
        dlight.setDirection((0,0.5,-1))
        dlight.setColor((0.25,0.25,0.5,1))
        
        alight = AmbientLight("ambient")
        alight.setColor((0.3, 0.3, 0.3, 1))
        alnp = self.render.attachNewNode(alight)
        self.render.setLight(alnp)
        
        # load april tags
        self.tags = {}
        with open(os.path.join(this_directory,"./tags.json"),"r") as tags:
            tagsList = json.load(tags)["tags"]
            for tag in tagsList:
                print(tag["id"])
                self.tags[tag["id"]] = Tag(self,tag["id"],tag["pos"],tag["angle"])
        
        # set robot starting position
        self.position = (2,-2,0)
        self.robot.setPos(self.position)
        base.cam.setPos(self.position[0],self.position[1],20)
        
        # add update task
        self.taskMgr.add(self.update,"update")
        
    
    def update(self, task):
        global point_index
        
        # if no points, continue to next iteration
        if point_index >= len(points) - 1:
            return Task.cont

        # get current and target points
        current = points[point_index]
        target = points[point_index + 1]
        current_pos = Vec3(current[0], current[1], 0)
        target_pos = Vec3(target[0], target[1], 0)
        
        # rotate to face target angle
        angle_to_target = angle_between_points(current, target)
        rotation_angle = math.degrees(angle_to_target - math.radians(self.robot.getH()))
        while rotation_angle > 180:
            rotation_angle -= 360
        while rotation_angle < -180:
            rotation_angle += 360
            
        angle_rad = math.radians(rotation_angle)
        if abs(rotation_angle) > 0.1:
            rotation_step = rotation_speed * globalClock.getDt()
            if angle_rad >= 0:
                rotation_step = min(rotation_step, rotation_angle)
                self.robot.setH(self.robot.getH() + rotation_step)
            else:
                rotation_step = max(-rotation_step, rotation_angle)
                self.robot.setH(self.robot.getH() + rotation_step)
            return Task.cont
        
        # move to target position
        distance_to_target = distance_between_points(self.position, target)
        if distance_to_target > 0.05:
            move_step = move_speed * globalClock.getDt()
            move_step = min(move_step, distance_to_target)
            direction = (target_pos - current_pos).normalized()
            self.position = Vec3(self.position[0] + direction.x * move_step,
                           self.position[1] + direction.y * move_step,
                           0)
            self.robot.setPos(self.position)
            base.cam.setPos(self.position.getX(),self.position.getY(),20)

            return Task.cont
        
        point_index += 1
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
        
        start=self.world_to_grid(self.position)
        end=location_name[name]
        points = aStarSearch(self.grid,start,end)
        points = [self.grid_to_world(p) for p in points]
        points[0] = self.position
        self.addPointMarkers()
        
    def stop_process(self,data):
        global points
        global point_index
        point_index = 0
        points = []
        
    def process_transform(self, data):
        self.position = (data["x"], data["y"], 0)
        self.robot.setPos(self.position)
        self.robot.setH(data["h"])
        
        
             
node = Node("simulation")
app = MyApp()

# NODE SUBSCRIPTION
node.subscribe("april_tag_data",app.process_april_tag)
node.subscribe("move_to",app.process_move_to)
node.subscribe("stop",app.stop_process)
node.subscribe("transform",app.process_transform)
# START APP
app.run()
