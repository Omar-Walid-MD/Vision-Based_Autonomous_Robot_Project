import os
from dotenv import load_dotenv
load_dotenv()

platform = os.getenv("PLATFORM")
if platform == "RPI":
    from .pathfinding import aStarSearch, marginizeGrid
else:
    from .pythonPathfinding import a_star_search as aStarSearch
    from .pythonPathfinding import marginize_grid as marginizeGrid

