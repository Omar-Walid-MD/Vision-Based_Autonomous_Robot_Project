import os
from dotenv import load_dotenv
load_dotenv()

# platform = os.getenv("PLATFORM")
# if platform == "RPI":
#     from .pathfinding import aStarSearch
# else:
from .pythonPathfinding import a_star_search as aStarSearch

