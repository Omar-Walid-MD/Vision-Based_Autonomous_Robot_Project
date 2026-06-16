import time
import threading
import os
import sys
import argparse
import py_trees
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Server.Node import Node

from Behaviour.trees.error_tree            import create_error_tree
from Behaviour.trees.emergency_tree        import create_emergency_tree
from Behaviour.trees.localization_tree     import create_localization_tree
from Behaviour.trees.mission_tree          import create_mission_tree
from Behaviour.trees.patient_checkup_tree  import create_patient_checkup_tree


class BehaviourNode(Node):
    """
    The single behaviour node.

    CLI arguments
    -------------
    --d                 Print the tree to stdout on every tick (debug mode).
    --no-error-check    Disable the error & node-health subtree.
                        Use during development/testing when not all nodes
                        need to be running.
    """

    TICK_RATE = 0.1  # seconds

    def __init__(self, url="http://localhost:5000",
                 debug_tree=False, error_check=True):
        super().__init__(node_name="behaviour", url=url)

        self._debug_tree  = debug_tree
        self._error_check = error_check  # False → error tree skipped entirely

        if not self._error_check:
            print("[BehaviourNode] ⚠️  Error-check disabled (--no-error-check). "
                  "Node health is NOT monitored.")

        # ── Blackboard ───────────────────────────────────────────────────
        self._setup_blackboard()

        # ── Subscribe to other nodes ─────────────────────────────────────
        self.subscribe("battery/level",             self._on_battery)
        self.subscribe("obstacle/detected",         self._on_obstacle)
        self.subscribe("camera/tag_found",          self._on_tag_found)
        self.subscribe("navigation/status",         self._on_nav_status)
        self.subscribe("navigation/location_valid", self._on_location_validated)
        self.subscribe("voice/command",             self._on_voice_command)

        # ── Error / health subscriptions (always subscribed; tree ignores if disabled) ──
        self.subscribe("system/nodes_status", self._on_nodes_status)
        self.subscribe("system/node_error",   self._on_node_error)

        # ── Checkup status from peripherals ──────────────────────────────
        self.subscribe("peripherals/checkup_status", self._on_checkup_status)

        # ── Build & start tree ───────────────────────────────────────────
        self._tree = self._build_tree()
        self._tree.setup(timeout=15)

        self._running = True
        self._thread  = threading.Thread(target=self._tick_loop, daemon=True)
        self._thread.start()

        print("Behaviour Node ready.")

    # ── Blackboard ────────────────────────────────────────────────────────────

    def _setup_blackboard(self):
        self._bb = py_trees.blackboard.Client(name="BehaviourNode")

        keys = {
            "state":                  "LOCALIZING",
            "localized":              False,
            "battery_level":          100,
            "current_task":           None,
            "location_valid":         None,
            "obstacle_detected":      False,
            "nav_status":             "idle",

            # error-tree keys
            "connected_nodes":        None,
            "node_error":             None,

            # checkup keys (simplified)
            "checkup_state":          None,
            "checkup_start_location": None,
            "checkup_status":         None,   # None | "running" | "done" | "failed"
        }

        for key, initial in keys.items():
            self._bb.register_key(key=key, access=py_trees.common.Access.WRITE)
            setattr(self._bb, key, initial)

    # ── Tree ─────────────────────────────────────────────────────────────────

    def _build_tree(self):
        emergency    = create_emergency_tree(self)
        localization = create_localization_tree(self)
        mission      = create_mission_tree(self)
        checkup      = create_patient_checkup_tree(self)

        mission_selector = py_trees.composites.Selector(
            name="Mission Selector", memory=False
        )
        mission_selector.add_children([checkup, mission])

        root_children = []

        # Error tree is the highest-priority child — only included when enabled
        if self._error_check:
            error = create_error_tree(self)
            root_children.append(error)

        root_children += [emergency, localization, mission_selector]

        root = py_trees.composites.Selector(name="Robot Root", memory=False)
        root.add_children(root_children)
        return py_trees.trees.BehaviourTree(root)

    def _tick_loop(self):
        while self._running:
            self._tree.tick()

            if self._debug_tree:
                print("\033c", end="")   # clear console
                print(py_trees.display.unicode_tree(
                    root=self._tree.root,
                    show_status=True
                ))

            time.sleep(self.TICK_RATE)

    def stop(self):
        self._running = False
        self._thread.join()

    # ── Subscription callbacks ────────────────────────────────────────────────

    def _on_battery(self, payload):
        self._bb.battery_level = int(payload.get("level", self._bb.battery_level))

    def _on_obstacle(self, payload):
        self._bb.obstacle_detected = bool(payload.get("detected", False))

    def _on_tag_found(self, payload):
        self.send("navigation/command", {
            "action": "correct_pose",
            "tag_id": payload.get("tag_id"),
        })
        self._bb.localized = True

    def _on_nav_status(self, payload):
        self._bb.nav_status = payload.get("status", "idle")

    def _on_location_validated(self, payload):
        self._bb.location_valid = payload.get("valid")

    def _on_voice_command(self, payload):
        self._bb.current_task = payload.get("task")

    # ── Error / health callbacks ──────────────────────────────────────────────

    def _on_nodes_status(self, payload):
        """payload: {"nodes": ["navigation", "camera0", ...]}"""
        self._bb.connected_nodes = payload.get("nodes", [])

    def _on_node_error(self, payload):
        """payload: {"node": "<name>", "error": "<message>"}"""
        if self._bb.node_error is None:
            self._bb.node_error = payload

    # ── Checkup callback ──────────────────────────────────────────────────────

    def _on_checkup_status(self, payload):
        """
        Peripherals emits this when the full per-patient checkup finishes.
        payload: {"status": "done"} or {"status": "failed"}
        Only update if currently running (ignore stale messages).
        """
        if self._bb.checkup_status == "running":
            self._bb.checkup_status = payload.get("status", "failed")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Robot Behaviour Node")
    parser.add_argument(
        "--d",
        action="store_true",
        help="Print behaviour tree to stdout on every tick."
    )
    parser.add_argument(
        "--no-error-check",
        action="store_true",
        dest="no_error_check",
        help="Disable node-health monitoring (useful during testing when "
             "not all nodes are active)."
    )
    args = parser.parse_args()

    node = BehaviourNode(
        debug_tree=args.d,
        error_check=not args.no_error_check,
    )
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        node.stop()
