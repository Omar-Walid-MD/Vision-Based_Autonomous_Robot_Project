import threading
import os
import subprocess
import json
import time
import sys



from dotenv import load_dotenv
load_dotenv()
env = os.environ.copy()

platform = os.getenv("PLATFORM")

this_directory = os.path.dirname(os.path.abspath(__file__))


print("Project started")
time.sleep(2)



def start_process(process):
<<<<<<< HEAD
    subprocess.Popen(["start","cmd","/k",f"{process}"],shell=True,env=env)
=======
    subprocess.Popen(["start","cmd","/k",f"python {process}"],shell=True,env=env)
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
    

if platform == "WINDOWS":
    with open(os.path.join(this_directory,"./start.json"),"r") as start:
        processes = json.load(start)["processes"]
        i = 0
        for process in processes:
            if process["start"]:
<<<<<<< HEAD
                start_process(process["command"])
=======
                start_process(process["path"])
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
                
            if i == 0:
                time.sleep(5)
            i += 1
            
                
    input()

else:
    print("Use Tmux instead!")
