import time
import threading
import os
import sys
import argparse
import py_trees

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Server.Node import Node

from Behaviour.trees.emergency_tree    import create_emergency_tree
from Behaviour.trees.localization_tree import create_localization_tree
from Behaviour.trees.mission_tree      import create_mission_tree


class BehaviourNode(Node):

    TICK_RATE = 0.1

    def __init__(self, url="http://localhost:5000", debug_tree=False):
        super().__init__(node_name="behaviour", url=url)
        
        self._debug_tree = debug_tree

        self._setup_blackboard()

        self.subscribe("battery/level",     self._on_battery)
        self.subscribe("obstacle/detected", self._on_obstacle)
        self.subscribe("camera/tag_found",  self._on_tag_found)
        self.subscribe("navigation/status", self._on_nav_status)
        self.subscribe("voice/command",     self._on_voice_command)

        self._tree = self._build_tree()
        self._tree.setup(timeout=15)

        self._running = True
        self._thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._thread.start()

        print("Behaviour Node ready.")

    def _setup_blackboard(self):
        self._bb = py_trees.blackboard.Client(name="BehaviourNode")

        keys = {
            "state":             "LOCALIZING",
            "localized":         False,
            "battery_level":     100,
            "current_task":      None,
            "obstacle_detected": False,
            "nav_status":        "idle",
            "is_charging":       False,
        }

        for key, initial in keys.items():
            self._bb.register_key(key=key, access=py_trees.common.Access.WRITE)
            setattr(self._bb, key, initial)

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
                print("\033c", end="")
                print(py_trees.display.unicode_tree(
                    root=self._tree.root,
                    show_status=True
                ))
            
            time.sleep(self.TICK_RATE)

    def stop(self):
        self._running = False
        self._thread.join()

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
        })
        self._bb.localized = True

    def _on_nav_status(self, payload):
        self._bb.nav_status = payload.get("status", "idle")

    def _on_voice_command(self, payload):
        self._bb.current_task = payload.get("task")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--d", action="store_true")
    args = parser.parse_args()

    node = BehaviourNode(debug_tree=args.d)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        node.stop()