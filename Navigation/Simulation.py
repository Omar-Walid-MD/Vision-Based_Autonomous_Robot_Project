from direct.showbase.ShowBase import ShowBase
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import loadPrcFileData, TextNode
from direct.task import Task
from classes.Robot import Robot
from classes.Environment import Environment
from classes.GridVisualizer import GridVisualizer
from classes.OrbitCamera import OrbitCamera
import time
import math
import json
import sys
import os
from pathfinding import marginizeGrid
from queue import Queue

from PIL import Image, ImageDraw


this_directory = os.path.dirname(os.path.abspath(__file__))

confVars = """
    win-size 1280 720
    window-title Robot Simulation And Mapping
    show-frame-rate-meter True
    model-cache-dir
"""
loadPrcFileData("", confVars)

mapDir = "./map/test/test"
robotSize = 0

class Simulation(ShowBase):
    def __init__(self, args, node):
        super().__init__(windowType='none' if not args.show else None)

        self.show = args.show
        self.sim = args.sim
        self.node = node
        
        self.disableMouse()
        
        # load grid map
        with open(os.path.join(this_directory, mapDir, "./map.json"), "r") as map:
            data = json.load(map)["robot_data"]
            self.cellSize = data["cell_size"]
            self.tags = data["tags"]

            self.grid = marginizeGrid(data["grid"], self.cellSize, robotSize)

            # convert zone list into dict
            self.zones = {}
            for zone in data["zones"]:
                self.zones[zone["name"]] = zone

        # initialize environment and robot models
        self.env = Environment(self,mapDir)
        self.robot = Robot(self,robotSize)
        
        self.tag_queue = Queue()    
        
        if self.show:
            self.gridVisualizer = GridVisualizer(self)

        # set robot starting position
        robot_position = self.robot.getPos()

        if len(self.zones.values()):
            zone_verts = list(self.zones.values())[0]["vertices_grid"]
            x = sum(v[0] for v in zone_verts) / len(zone_verts)
            y = sum(v[1] for v in zone_verts) / len(zone_verts)
            pos = self.grid_to_sim([x, y])
            self.robot.setPos(pos[0], pos[1], robot_position.getZ())

        robot_position = self.robot.getPos()

        if self.show:
            # base.cam.setPos(robot_position.getX(),robot_position.getY(),20)

            self.pos_label = OnscreenText(
                text="",
                pos=(-1.7, 0.9),  # top-left corner
                scale=0.08,
                fg=(1, 1, 1, 1),
                align=TextNode.ALeft,
                mayChange=True
            )

            self.taskMgr.add(self.update_ui, "update_ui")

        self.taskMgr.add(self.update, "update")

        # ------------------ Topic callbacks ------------------

        def handle_tag_found(data):
            if isinstance(data, str):
                data = json.loads(data)

            tags = data.get("tags", [])

            if not tags:
                return

            closest_tag = min(tags, key=lambda tag: tag["distance"])

            self.tag_queue.put(closest_tag)
            
            
        
        def handle_navigation_command(data):
            
            print(f"[SIM DEBUG] Received: {data}")
            action = data["action"]

            if action == "move_to_charger":
                if "charger" in self.zones:
                    self.robot.navigate_to_location("charger")
                else:
                    print("error: charging location not found")

            elif action == "estop":
                self.robot.stop()

            # ✅ NEW: handle move_to_goal from behaviour tree
            elif action == "move_to_goal":
                task = data.get("task")
                if task and isinstance(task, dict):
                    location = task.get("location")
                    if location:
                        self.robot.navigate_to_location(location)
                    else:
                        print("error: 'location' missing in move_to_goal task")
                else:
                    print("error: invalid task format for move_to_goal")

        self.node.subscribe("camera/tag_found", handle_tag_found)
        self.node.subscribe("navigation/command", handle_navigation_command)

    # ------------------ Core update ------------------

    def update(self, task):
        
        self.process_tag_updates()
        self.robot.update()
        
        return Task.cont

    def update_ui(self, task):
        world_pos = self.robot.getPos()
        grid_pos = self.sim_to_grid([world_pos[0], world_pos[1]])

        self.pos_label.setText(
            f"World: ({world_pos.x:.2f}, {world_pos.y:.2f}, {world_pos.z:.2f})\n"
            f"Grid: ({grid_pos[0]}, {grid_pos[1]})\n"
            f"Battery level: {int(self.robot.status.batteryLevel)}%"
        )
        
        self.pos_label.hide()

        return task.cont

    # ------------------ Coordinate conversions ------------------

    def world_to_grid(self, world_coords):
        return [
            math.floor((world_coords[0] - self.cellSize / 2) / self.cellSize),
            math.floor((world_coords[1] - self.cellSize / 2) / self.cellSize),
        ]

    def grid_to_world(self, grid_coords):
        return [
            grid_coords[0] * self.cellSize + self.cellSize / 2,
            grid_coords[1] * self.cellSize + self.cellSize / 2
        ]

    def grid_to_sim(self, grid_coords):
        return self.world_to_sim(self.grid_to_world(grid_coords))

    def sim_to_grid(self, sim_coords):
        return self.world_to_grid(self.sim_to_world(sim_coords))

    def world_to_sim(self, world_coords):
        return [world_coords[0], -world_coords[1]]

    def sim_to_world(self,sim_coords):
        return [sim_coords[0],-sim_coords[1]]

            
    def process_tag_updates(self):

        while not self.tag_queue.empty():

            data = self.tag_queue.get()

            tag_id = data["id"]

            pos, hpr = self.tags[tag_id]["object"].locate_robot(
                data["pose"]["position"],
                data["pose"]["rotation"],
                (0,0,0), 0,
                (0,0,0), 0
            )

            self.robot.setPos(pos)
            self.robot.setHpr(hpr)

            print("tag found")

        return
    


    def export_path_image(self, grid, start, end, waypoints, filename="path.png", cell_size=20):
        height = len(grid)
        width = len(grid[0])

        img = Image.new(
            "RGB",
            (width * cell_size, height * cell_size),
            (255, 255, 255)
        )

        draw = ImageDraw.Draw(img)

        # Draw grid
        for y in range(height):
            for x in range(width):

                color = (255, 255, 255)  # free

                if grid[y][x] == 0:
                    color = (0, 0, 0)    # obstacle

                x0 = x * cell_size
                y0 = y * cell_size
                x1 = x0 + cell_size
                y1 = y0 + cell_size

                draw.rectangle([x0, y0, x1, y1], fill=color)

        # Draw waypoints
        for x, y in waypoints:

            x0 = x * cell_size
            y0 = y * cell_size
            x1 = x0 + cell_size
            y1 = y0 + cell_size

            draw.rectangle(
                [x0, y0, x1, y1],
                fill=(0, 0, 255)
            )

        # Draw start
        sx, sy = start
        draw.rectangle(
            [
                sx * cell_size,
                sy * cell_size,
                (sx + 1) * cell_size,
                (sy + 1) * cell_size
            ],
            fill=(0, 255, 0)
        )

        # Draw end
        ex, ey = end
        draw.rectangle(
            [
                ex * cell_size,
                ey * cell_size,
                (ex + 1) * cell_size,
                (ey + 1) * cell_size
            ],
            fill=(255, 0, 0)
        )

        # Optional grid lines
        for x in range(width + 1):
            draw.line(
                [(x * cell_size, 0), (x * cell_size, height * cell_size)],
                fill=(200, 200, 200)
            )

        for y in range(height + 1):
            draw.line(
                [(0, y * cell_size), (width * cell_size, y * cell_size)],
                fill=(200, 200, 200)
            )
            
        if len(waypoints) >= 2:

            for i in range(len(waypoints) - 1):

                x1, y1 = waypoints[i]
                x2, y2 = waypoints[i + 1]

                draw.line(
                    [
                        (
                            x1 * cell_size + cell_size / 2,
                            y1 * cell_size + cell_size / 2
                        ),
                        (
                            x2 * cell_size + cell_size / 2,
                            y2 * cell_size + cell_size / 2
                        )
                    ],
                    fill=(100, 100, 100),  #gray
                    width=4
                )

        img.save(filename)

        
        

             


