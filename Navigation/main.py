from Simulation import Simulation
from direct.task import Task
import argparse
import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Server.Node import Node


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-ns", "--no-show",
        action="store_false",
        dest="show",
        help="Disable rendering window",
    )
    parser.add_argument(
        "-nm", "--no-sim",
        action="store_false",
        dest="sim",
        help="Disable simulation mode",
    )
    parser.set_defaults(show=True, sim=True)
    return parser.parse_args()


if __name__ == "__main__":
    args   = parse_args()
    node   = Node("navigation")

    # ── Simulation must exist before subscriptions so handlers can reach it ──
    simulation = Simulation(args, node)

    # Tracks whether a navigation move is currently in progress so the
    # per-frame monitor knows when to watch for completion.
    _nav_active = False

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _start_navigation(zone_name):
        """
        Kick off pathfinding to *zone_name*.  Returns True when a path was
        found and navigation has started; False when the zone is unreachable
        (path blocked) or unknown.
        """
        robot = simulation.robot
        robot.navigate_to_location(zone_name)

        if len(robot.points) == 0:
            # aStarSearch returned nothing — destination unreachable
            return False
        return True

    # ── navigation/command handler ────────────────────────────────────────────
    #
    # Actions dispatched by the Behaviour node:
    #
    #   validate_location  → publish navigation/location_valid {"valid": bool}
    #   move_to_goal       → navigate to named zone, publish running/failed
    #   move_to_charger    → navigate to "charger" zone, publish running/failed
    #   correct_pose       → robot pose is updated by camera/tag_found
    #                        (subscribed inside Simulation); nothing to do here
    #   estop              → halt immediately, publish idle

    def handle_command(data):
        nonlocal _nav_active
        action = data.get("action")
        robot  = simulation.robot

        # ── Validate whether a location name is known ─────────────────────
        if action == "validate_location":
            task  = data.get("task")
            valid = isinstance(task, str) and task in simulation.zones
            node.send("navigation/location_valid", {"valid": valid})

        # ── Navigate to a named goal (from voice command) ─────────────────
        elif action == "move_to_goal":
            task = data.get("task")

            if not task or task not in simulation.zones:
                node.send("navigation/status", {"status": "failed"})
                return

            if _start_navigation(task):
                _nav_active = True
                node.send("navigation/status", {"status": "running"})
            else:
                node.send("navigation/status", {"status": "failed"})

        # ── Navigate to the charging station ─────────────────────────────
        elif action == "move_to_charger":
            if "charger" not in simulation.zones:
                print("Navigation: 'charger' zone not found in map.")
                node.send("navigation/status", {"status": "failed"})
                return

            if _start_navigation("charger"):
                _nav_active = True
                node.send("navigation/status", {"status": "running"})
            else:
                node.send("navigation/status", {"status": "failed"})

        # ── Pose correction via April tag — handled by Simulation ─────────
        elif action == "correct_pose":
            pass   # camera/tag_found subscription inside Simulation does this

        # ── Emergency stop ────────────────────────────────────────────────
        elif action == "estop":
            robot.stop()
            _nav_active = False
            node.send("navigation/status", {"status": "idle"})

    node.subscribe("navigation/command", handle_command)

    # ── Per-frame navigation status monitor ───────────────────────────────────
    #
    # Runs every Panda3D frame.  When a nav move is active it checks whether
    # the robot has finished traversing its waypoint list and, if so, publishes
    # the terminal status and clears the active flag.

    def monitor_nav(task):
        nonlocal _nav_active
        if not _nav_active:
            return Task.cont

        robot = simulation.robot

        # Point list exhausted → robot has arrived
        if robot.point_index >= len(robot.points) - 1:
            _nav_active = False
            node.send("navigation/status", {"status": "done"})

        return Task.cont

    simulation.taskMgr.add(monitor_nav, "monitor_nav")

    simulation.run()
