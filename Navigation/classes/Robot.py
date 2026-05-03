from panda3d.core import NodePath, Vec3
from direct.task import Task
import math
from pathfinding import aStarSearch


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
        self.setHpr(-90,0,0)
        
        self.points = []
        self.point_index = 0
        
        
        self.move_speed = 2
        self.rotation_speed = 180
        self.size = robot_size # meters
        
    
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
            rotation_step = self.rotation_speed * globalClock.getDt()
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
            move_step = self.move_speed * globalClock.getDt()
            move_step = min(move_step, distance_to_target)
            direction = (target_pos - current_pos).normalized()
            
            position.setX(position.getX() + direction.x * move_step)
            position.setY(position.getY() + direction.y * move_step)

            self.setPos(position)
            if self.scene.show:
                base.cam.setPos(position.getX(),position.getY(),20)

            return
        
        self.point_index += 1