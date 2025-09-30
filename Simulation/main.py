from direct.showbase.ShowBase import ShowBase
from panda3d.core import loadPrcFileData, DirectionalLight, AmbientLight, Vec3
from direct.task import Task
from Tag import Tag
import math
import json
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Pathfinding import aStarSearch

this_directory = os.path.dirname(os.path.abspath(__file__))

confVars = """
win-size 1280 720
window-title Robot Simulation And Mapping
show-frame-rate-meter True
model-cache-dir
"""

loadPrcFileData("",confVars)

points = []
point_index = 0

move_speed = 2
rotation_speed = 180

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
        
        global points
                
        self.disableMouse()
        
        env = self.loader.loadModel("./models/model.obj")
        env.reparentTo(self.render)
        env.setPos(-0.25,16.25,0)
        env.setHpr(0,90,0)
        
        self.robot = self.loader.loadModel("./models/robot.obj")
        self.robot.reparentTo(self.render)
        self.robot.setPos(2,2,0)
        self.robot.setHpr(-90,0,0)
        self.robot.setScale(0.75,0.75,0.75)
        
        
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
        
        self.grid = []
        with open(os.path.join(this_directory,"./grid.json"),"r") as grid:
            self.grid = json.load(grid)["grid"]
        
        start = [1,1]
        end = [30,30]
        
        start = start[-1::-1]
        end = end[-1::-1]
        points = aStarSearch(self.grid,start,end)
        points = [[p[1]*0.5,16-p[0]*0.5] for p in points]
        self.addPointMarkers()
        
        self.tags = []
        with open(os.path.join(this_directory,"./tags.json"),"r") as tags:
            tagsList = json.load(tags)["tags"]
            self.tags = [Tag(self,tag["id"],tag["pos"],tag["angle"]) for tag in tagsList]
        
        self.taskMgr.add(self.update,"update")
        
        self.position = (points[0][0],points[0][1],0)
        self.robot.setPos(self.position)
        base.cam.setPos(self.position[0],self.position[1],30)

    
    def update(self, task):
        global point_index
        if point_index >= len(points) - 1:
            return Task.done
    
        
        current = points[point_index]
        target = points[point_index + 1]
        current_pos = Vec3(current[0], current[1], 0)
        target_pos = Vec3(target[0], target[1], 0)
        
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
        
        distance_to_target = distance_between_points(current, target)
        if distance_to_target > 0.01:
            move_step = move_speed * globalClock.getDt()
            move_step = min(move_step, distance_to_target)
            direction = (target_pos - current_pos).normalized()
            new_pos = Vec3(current[0] + direction.x * move_step,
                           current[1] + direction.y * move_step,
                           0)
            self.robot.setPos(new_pos)
            base.cam.setPos(new_pos.getX(),new_pos.getY(),20)

            points[point_index] = [new_pos.x, new_pos.y]
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

app = MyApp()
app.run()