from panda3d.core import NodePath, Vec3
from direct.task import Task
import math
import os
from pathfinding import aStarSearch
from classes.RobotStatus import RobotStatus
from classes.ESPSerial import ESPSerial

env = os.environ.copy()
SERIAL_PORT = os.getenv("SERIAL_PORT")

SIM_MOVE_SPEED = 2
SIM_ROTATE_SPEED = 180

BATTERY_SEND_INTERVAL = 10
BATTERY_SEND_REMAINING = 0

# Helper functions
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

    
# class simulating Robot in the environment
class Robot(NodePath):
    def __init__(self, scene, robot_size=0.25):

        NodePath.__init__(self,'robot-root')
        self.scene = scene

        scene.loader.loadModel("./models/robot.obj").reparentTo(self)
        self.reparentTo(scene.render)
        
        self.setPos(2,2,0)
        self.setHpr(0,0,0)
        
        self.points = []
        self.point_index = 0
        
        self.size = robot_size # meters
        
        self.status = RobotStatus()
        
        self.sim = scene.sim
        self.node = scene.node
        
        self.serial = None
        if not self.sim:
            self.serial = ESPSerial(SERIAL_PORT,status=self.status,robot=self)
            
        
    
    # navigate to given location name
    def navigate_to_location(self,zone_name):
        zone = self.scene.zones.get(zone_name)
        if not zone:
            print(f"Zone ({zone_name}) not found")
            return
        
        # get center point of zone
        zone_verts = zone["vertices_grid"]
        x = int(sum(v[0] for v in zone_verts)/len(zone_verts))
        y = int(sum(v[1] for v in zone_verts)/len(zone_verts))
                
        self.navigate_to_point([x,y])
        
    def navigate_to_point(self,point):
        
        self.points = self.calculate_points(point)
        self.point_index = 0
        
    def calculate_points(self,target):
        pos = self.getPos()
        pos = [pos[0],pos[1]] # vector to list
        start = self.scene.sim_to_grid([pos[0],pos[1]]) # convert simulation space to grid
        points = aStarSearch(self.scene.grid,start,target)

        if not len(points):
            return []
        
        # show grid if render enabled
        if self.scene.show:
            self.scene.gridVisualizer.pathOverlay.show_path(points)
        
        points = [self.scene.grid_to_sim(p) for p in points] # convert back to simulation space
        points[0] = pos # replace first estimated point with actual position
        return points

        
    def update(self):
        if self.sim:
            self.simulate_navigation()
            self.simulate_battery()
        else:
            self.serial.update()    
        
        self.send_battery_level()
        
        
    def send_battery_level(self):
        global BATTERY_SEND_REMAINING
        if BATTERY_SEND_REMAINING <= 0:
            self.node.send("battery/level",self.status.batteryLevel)
            BATTERY_SEND_REMAINING = BATTERY_SEND_INTERVAL
            print("sent battery level")
        else:
            BATTERY_SEND_REMAINING -= globalClock.getDt()
        
        
    def simulate_navigation(self):
        # if no points, continue to next iteration
        if self.point_index >= len(self.points) - 1:
            return

        # get current and target points
        current = self.points[self.point_index]
        target = self.points[self.point_index + 1]
        current_pos = Vec3(current[0], current[1], 0)
        target_pos = Vec3(target[0], target[1], 0)
        
        # rotate to face target angle
        angle_to_target = angle_between_points(current, target)
        rotation_angle = math.degrees(angle_to_target - math.radians(self.getH()))
        while rotation_angle > 180:
            rotation_angle -= 360
        while rotation_angle < -180:
            rotation_angle += 360
            
        angle_rad = math.radians(rotation_angle)

        if abs(rotation_angle) > 0.1:
            rotation_step = SIM_ROTATE_SPEED * globalClock.getDt()
            if angle_rad >= 0:
                rotation_step = min(rotation_step, rotation_angle)
                self.setH(self.getH() + rotation_step)
            else:
                rotation_step = max(-rotation_step, rotation_angle)
                self.setH(self.getH() + rotation_step)
            return
        
        # move to target position
        position = self.getPos()
        
        distance_to_target = distance_between_points(position, target)
        if distance_to_target > 0.05:
            move_step = SIM_MOVE_SPEED * globalClock.getDt()
            move_step = min(move_step, distance_to_target)
            direction = (target_pos - current_pos).normalized()
            
            position.setX(position.getX() + direction.x * move_step)
            position.setY(position.getY() + direction.y * move_step)

            self.setPos(position)
            if self.scene.show:
                base.cam.setPos(position.getX(),position.getY(),20)

            return
        
        self.point_index += 1
        
    def simulate_battery(self):
        # 1. Get coordinates directly using NodePath built-ins (No getPos required!)
        actual_x = self.getX()
        actual_y = self.getY()

        # 2. Check if the actual location matches the station
        # (Using a wider tolerance of 0.3 to guarantee it registers the zone cleanly)
        at_charging_x = math.isclose(actual_x, 18.40, abs_tol=0.3)
        at_charging_y = math.isclose(actual_y, -20.60, abs_tol=0.3)

        if (self.status.batteryLevel < 10) and at_charging_x and at_charging_y:
            self.status.recharging = True
        elif self.status.recharging == True and self.status.batteryLevel == 100:
            self.status.recharging = False

        if self.status.recharging:
            bat = self.status.batteryLevel
            self.status.batteryLevel = min(100, bat + globalClock.getDt())
        else:
            bat = self.status.batteryLevel
            self.status.batteryLevel = max(0, bat - globalClock.getDt())
        
        
    def stop(self):
        if self.sim:
            self.point_index = 0
            self.points = []
        else:
            self.serial.sendStop() 
