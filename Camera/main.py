# from AprilTagCam import AprilTagCam
# import os
# import sys
# import signal
# import atexit
# import time
# from dotenv import load_dotenv
# load_dotenv()

# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # add parent folder to paths
# from Server.Node import Node

# node = Node("camera")
# cam = AprilTagCam()
# platform = os.getenv("PLATFORM")

# # robot_stopped = False # robot should stop to take accurate reads from april tag
# robot_searching = False
# robot_aligning = False
# last_tag_date = 0

# def cleanup():
#     print("Running cleanup...")
#     cam.close()
    
# def handle_sigterm(signum, frame):
#     sys.exit(0)
    
# def now():
#     return int(time.time_ns()//1_000_000)
    
# # def read_april_tag():
# #     global robot_stopped, last_tag_date
    
# #     # code to read april tags. may need to read multiple times to get average reading and eliminate noise or use other logic
# #     result = cam.detect()
# #     print("Found Tag")
# #     node.send("april_tag_data",result)
# #     robot_stopped = False
# #     last_tag_date = now()

# def start_search(data):
#     global robot_searching
#     robot_searching = True

# def on_robot_stop(data):
#     global robot_aligning
#     print(robot_aligning)
#     if robot_aligning:
#         target_angle = 0
#         margin = 2
        
#         result = cam.detect()
#         while not result:
#             result = cam.detect()
#             time.sleep(0.1)
        
#         angle = result["rotation"][1]
        
#         limit = 20
        
#         print(f"Tag angle: {angle}")
        
#         if abs(angle - target_angle) < margin:
#             print("Tag aligning successful!")
#             robot_aligning = False
#         else:
#             rotate_angle = int(angle-target_angle)
#             if 0 < rotate_angle < limit:
#                 rotate_angle = limit
#             elif -limit < rotate_angle < 0:
#                 rotate_angle = -limit
    
# def stop_robot(data):
#     global robot_searching, robot_aligning
#     robot_searching = False
#     robot_aligning = False

# if __name__ == "__main__":    
    
#     atexit.register(cleanup)
    
#     # Handle Ctrl+C and termination
#     signal.signal(signal.SIGINT, handle_sigterm)
#     signal.signal(signal.SIGTERM, handle_sigterm)
#     if platform == "WINDOWS":
#         signal.signal(signal.SIGBREAK, handle_sigterm)
#     else:
#         signal.signal(signal.SIGHUP, handle_sigterm)   # Close window

#     # node.subscribe("robot_stop_acknowledge",read_april_tag)
#     node.subscribe("robot_stop_acknowledge",on_robot_stop)
#     node.subscribe("start_search",start_search)
#     node.subscribe("stop",stop_robot)

#     while True:
#         if robot_searching:
#             result = cam.detect()
#             if result:
#                 # if not robot_stopped and last_tag_date - now() > 30*1000:
#                 print("Tag detected for reading. stopping.")
#                 # robot_stopped = True
#                 robot_searching = False
#                 robot_aligning = True
                
        
