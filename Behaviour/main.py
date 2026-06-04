import time
import threading
import os
import sys
import argparse
import py_trees
<<<<<<< HEAD

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
=======
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # add parent folder to paths
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
from Server.Node import Node

from Behaviour.trees.emergency_tree    import create_emergency_tree
from Behaviour.trees.localization_tree import create_localization_tree
from Behaviour.trees.mission_tree      import create_mission_tree


<<<<<<< HEAD
class BehaviourNode(Node):

    TICK_RATE = 0.1

    def __init__(self, url="http://localhost:5000", debug_tree=False):
=======

class BehaviourNode(Node):
    """
    The single behaviour node.

    Inherits Node — connects to the socket server exactly like every other
    node (camera, navigation, voice, ...).

    - Subscribes to topics from other nodes → updates the blackboard
    - Runs py_trees internally on a background thread
    - Tree leaves call self.send() to command other nodes
    """

    TICK_RATE = 0.1  # seconds

    def __init__(self,url="http://localhost:5000",debug_tree=False):
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
        super().__init__(node_name="behaviour", url=url)
        
        self._debug_tree = debug_tree

<<<<<<< HEAD
        self._setup_blackboard()

        self.subscribe("battery/level",     self._on_battery)
        self.subscribe("obstacle/detected", self._on_obstacle)
        self.subscribe("camera/tag_found",  self._on_tag_found)
        self.subscribe("navigation/status", self._on_nav_status)
        self.subscribe("voice/command",     self._on_voice_command)

=======
        # ── Blackboard ───────────────────────────────────────────────────
        self._setup_blackboard()

        # ── Subscribe to other nodes ─────────────────────────────────────
        # Incoming data updates the blackboard; tree reads it on next tick.
        self.subscribe("battery/level",    self._on_battery)
        self.subscribe("obstacle/detected", self._on_obstacle)
        self.subscribe("camera/tag_found", self._on_tag_found)
        self.subscribe("navigation/status", self._on_nav_status)
        self.subscribe("voice/command",    self._on_voice_command)
        # self.subscribe("server/task",      self._on_task)

        # ── Build & start tree ───────────────────────────────────────────
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
        self._tree = self._build_tree()
        self._tree.setup(timeout=15)

        self._running = True
<<<<<<< HEAD
        self._thread = threading.Thread(target=self._tick_loop, daemon=True)
=======
        self._thread  = threading.Thread(target=self._tick_loop, daemon=True)
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
        self._thread.start()

        print("Behaviour Node ready.")

<<<<<<< HEAD
=======
    # ── Blackboard setup ─────────────────────────────────────────────────────

>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
    def _setup_blackboard(self):
        self._bb = py_trees.blackboard.Client(name="BehaviourNode")

        keys = {
            "state":             "LOCALIZING",
            "localized":         False,
            "battery_level":     100,
            "current_task":      None,
            "obstacle_detected": False,
<<<<<<< HEAD
            "nav_status":        "idle",
            "is_charging":       False,
=======
            "nav_status":        "idle",   # "idle" | "running" | "done" | "failed"
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
        }

        for key, initial in keys.items():
            self._bb.register_key(key=key, access=py_trees.common.Access.WRITE)
            setattr(self._bb, key, initial)

<<<<<<< HEAD
=======
    # ── Tree ─────────────────────────────────────────────────────────────────

>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
    def _build_tree(self):
        emergency    = create_emergency_tree(self)
        localization = create_localization_tree(self)
        mission      = create_mission_tree(self)

        root = py_trees.composites.Selector(name="Robot Root", memory=False)
        root.add_children([emergency, localization, mission])
        return py_trees.trees.BehaviourTree(root)

    def _tick_loop(self):
        while self._running:
            self._tree.tick()
            
            if self._debug_tree:
<<<<<<< HEAD
                print("\033c", end="")
=======
                print("\033c", end="")  # clear console
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
                print(py_trees.display.unicode_tree(
                    root=self._tree.root,
                    show_status=True
                ))
<<<<<<< HEAD
=======
                
                # print("\nBLACKBOARD:")
                # print(f"localized: {self._bb.localized}")
                # print(f"battery: {self._bb.battery_level}")
                # print(f"task: {self._bb.current_task}")
                # print(f"nav_status: {self._bb.nav_status}")
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
            
            time.sleep(self.TICK_RATE)

    def stop(self):
        self._running = False
        self._thread.join()

<<<<<<< HEAD
    # ── Callbacks ────────────────────────────────────────────────────────────

    def _on_battery(self, payload):
        level = int(payload.get("level", self._bb.battery_level))
        self._bb.battery_level = level

        if level >= 95 and self._bb.is_charging:
            self._bb.is_charging = False
            self.send("navigation/command", {"action": "stop_charging"})
        elif level <= 25 and not self._bb.is_charging:
            self._bb.is_charging = True

    def _on_obstacle(self, payload):
        self._bb.obstacle_detected = bool(payload.get("detected", False))

    def _on_tag_found(self, payload):
        tag_id = payload.get("tag_id") or payload.get("id")
        print(f"✅ Tag Found: {tag_id} - Localization Done")
        
        self.send("navigation/command", {
            "action": "correct_pose",
            "tag_id": tag_id,
=======
    # ── Subscription callbacks — write to blackboard ──────────────────────────

    def _on_battery(self, payload):
        # payload: {"level": <int>}
        self._bb.battery_level = int(payload.get("level", self._bb.battery_level))

    def _on_obstacle(self, payload):
        # payload: {"detected": <bool>}
        self._bb.obstacle_detected = bool(payload.get("detected", False))

    # def _on_task(self, payload):
    #     # payload: {"task": <any>}
    #     self._bb.current_task = payload.get("task")

    def _on_tag_found(self, payload):
        # payload: {"tag_id": <str>}
        # Tell navigation to correct its pose internally — raw pose NOT stored on BB
        self.send("navigation/command", {
            "action": "correct_pose",
            "tag_id": payload.get("tag_id"),
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
        })
        self._bb.localized = True

    def _on_nav_status(self, payload):
<<<<<<< HEAD
        self._bb.nav_status = payload.get("status", "idle")

    def _on_voice_command(self, payload):
        self._bb.current_task = payload.get("task")


if __name__ == "__main__":
=======
        # payload: {"status": "running" | "done" | "failed"}
        self._bb.nav_status = payload.get("status", "idle")

    def _on_voice_command(self, payload):
        # payload: {"task": <any>}
        self._bb.current_task = payload.get("task")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
    parser = argparse.ArgumentParser()
    parser.add_argument("--d", action="store_true")
    args = parser.parse_args()

    node = BehaviourNode(debug_tree=args.d)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
<<<<<<< HEAD
        node.stop()
=======
        node.stop()
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
