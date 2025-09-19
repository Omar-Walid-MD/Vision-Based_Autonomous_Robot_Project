from controller import Robot
import math

def angle_between_points(current, target):
    dx = target[0] - current[0]
    dy = target[1] - current[1]
    return math.atan2(dy, dx)

def distance_between_points(current, target):
    dx = target[0] - current[0]
    dy = target[1] - current[1]
    return math.sqrt(dx**2 + dy**2)

robot = Robot()
points = [
    [0.0, 0.0],  
    [1.0, 0.0],  
    [1.0, 1.0], 
    [0.0, 1.0], 
    [0.0, 0.0]
]
timestep = 16
wheel_radius = 0.0205
axle_length = 0.1

left_motor = robot.getDevice("motor1")
right_motor = robot.getDevice("motor2")
left_sensor = robot.getDevice("ps_1")
right_sensor = robot.getDevice("ps_2")

left_motor.setPosition(float('inf'))
right_motor.setPosition(float('inf'))
left_sensor.enable(timestep)
right_sensor.enable(timestep)
robot.step(timestep)

speed = 13
robot_angle = 0

for current_index in range(len(points) - 1):
    target_index = current_index + 1
    current = points[current_index]
    target = points[target_index]
    angle_to_target = angle_between_points(current, target)
    rotation_angle = math.degrees(angle_to_target - robot_angle)
    angle_rad = math.radians(rotation_angle)
    distance_per_wheel = (axle_length * abs(angle_rad)) / 2
    wheel_turn = distance_per_wheel / wheel_radius
    initial_left = left_sensor.getValue()
    initial_right = right_sensor.getValue()
    if angle_rad >= 0:
        left_motor.setVelocity(speed)
        right_motor.setVelocity(-speed)
    else:
        left_motor.setVelocity(-speed)
        right_motor.setVelocity(speed)
    while robot.step(timestep) != -1:
        current_pos = left_sensor.getValue()
        if abs(current_pos - initial_left) >= abs(wheel_turn):
            left_motor.setVelocity(0)
            right_motor.setVelocity(0)
            robot_angle = angle_to_target
            break
    distance_to_target = distance_between_points(current, target)
    wheel_rotation_needed = distance_to_target / wheel_radius
    initial_left = left_sensor.getValue()
    initial_right = right_sensor.getValue()
    left_motor.setVelocity(speed)
    right_motor.setVelocity(speed)
    while robot.step(timestep) != -1:
        current_pos = left_sensor.getValue()
        if abs(current_pos - initial_left) >= wheel_rotation_needed:
            left_motor.setVelocity(0)
            right_motor.setVelocity(0)
            break