import threading
import os
import subprocess
import json

from dotenv import load_dotenv
load_dotenv()
env = os.environ.copy()


this_directory = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(this_directory,"./start.json"),"r") as start:
    processes = json.load(start)["processes"]
    for process in processes:
        subprocess.Popen(["start","cmd","/k",process],shell=True,env=env)