from panda3d.core import NodePath, Vec3
from direct.task import Task
import math

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
    

class Robot(NodePath):
    def __init__(self, parent, robot_size=0.25):

        NodePath.__init__(self,'robot-root')

        parent.loader.loadModel("./models/robot.obj").reparentTo(self)
        self.reparentTo(parent.render)
        print(self.parent)
        
        self.setPos(2,2,0)
        self.setHpr(-90,0,0)
        self.setScale(0.75,0.75,0.75)
        
        self.points = []
        self.point_index = 0
        
        self.move_speed = 2
        self.rotation_speed = 180
        self.robot_size = robot_size
        
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
        rotation_angle = math.degrees(angle_to_target - math.radians(self.robot.getH()))
        while rotation_angle > 180:
            rotation_angle -= 360
        while rotation_angle < -180:
            rotation_angle += 360
            
        angle_rad = math.radians(rotation_angle)
        if abs(rotation_angle) > 0.1:
            rotation_step = self.rotation_speed * globalClock.getDt()
            if angle_rad >= 0:
                rotation_step = min(rotation_step, rotation_angle)
                self.robot.setH(self.robot.getH() + rotation_step)
            else:
                rotation_step = max(-rotation_step, rotation_angle)
                self.robot.setH(self.robot.getH() + rotation_step)
            return
        
        # move to target position
        position = self.getPos()
        
        distance_to_target = distance_between_points(position, target)
        if distance_to_target > 0.05:
            move_step = self.move_speed * globalClock.getDt()
            move_step = min(move_step, distance_to_target)
            direction = (target_pos - current_pos).normalized()
            
            # position = Vec3(self.position[0] + direction.x * move_step,
            #                self.position[1] + direction.y * move_step,
            #                0)
            
            position.setX(position.getX() + direction.x * move_step)
            position.setY(position.getY() + direction.y * move_step)

            self.robot.setPos(position)
            base.cam.setPos(position.getX(),position.getY(),20)

            return
        
        self.point_index += 1