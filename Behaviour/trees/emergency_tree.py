import py_trees

BATTERY_LOW_THRESHOLD  = 20   # % — trigger charging
BATTERY_FULL_THRESHOLD = 95   # % — stop charging


# ── Conditions ───────────────────────────────────────────────────────────────

class IsBatteryLow(py_trees.behaviour.Behaviour):
    """Returns SUCCESS when battery_level <= LOW_THRESHOLD."""

    def __init__(self):
        super().__init__(name="Is Battery Low?")
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="battery_level", access=py_trees.common.Access.READ)

    def update(self):
        if self.bb.battery_level <= BATTERY_LOW_THRESHOLD:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE


class IsObstacleDetected(py_trees.behaviour.Behaviour):
    """Returns SUCCESS when an obstacle has been reported."""

    def __init__(self):
        super().__init__(name="Is Obstacle Detected?")
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="obstacle_detected", access=py_trees.common.Access.READ)

    def update(self):
        if self.bb.obstacle_detected:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE


# ── Actions ──────────────────────────────────────────────────────────────────

class MoveToCharger(py_trees.behaviour.Behaviour):
    """
    Sends a single move_to_charger command to navigation then waits.

    - Resets nav_status to 'idle' on initialise() so stale state from a
      previous mission doesn't cause an immediate false finish.
    - Returns RUNNING while navigation is in progress.
    - Returns SUCCESS when nav_status == 'done'  (arrived at charger).
    - Returns FAILURE when nav_status == 'failed' (path blocked).
    """

    def __init__(self, node):
        super().__init__(name="Move To Charger")
        self._node     = node
        self._cmd_sent = False
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="nav_status", access=py_trees.common.Access.READ)
        self.bb.register_key(key="nav_status", access=py_trees.common.Access.WRITE)

    def initialise(self):
        self._cmd_sent    = False
        self.bb.nav_status = "idle"   # clear any stale result

    def update(self):
        if not self._cmd_sent:
            self._node.send("navigation/command", {"action": "move_to_charger"})
            self._cmd_sent = True

        status = self.bb.nav_status
        if status == "done":
            return py_trees.common.Status.SUCCESS
        if status == "failed":
            self._node.send("voice/speak", {"text": "Cannot reach charger."})
            return py_trees.common.Status.FAILURE
        return py_trees.common.Status.RUNNING


class WaitForFullCharge(py_trees.behaviour.Behaviour):
    """
    Sits at the charger until the battery reaches BATTERY_FULL_THRESHOLD.

    - Sends 'start_charging' once when it first runs.
    - Returns RUNNING while battery_level < BATTERY_FULL_THRESHOLD.
    - When full: sends 'stop_charging', announces via voice, returns SUCCESS.
      The parent sequence then exits, IsBatteryLow evaluates to FAILURE on
      the next tick (battery is now full), so the Emergency tree fails and
      the Mission tree resumes (step 5).
    """

    def __init__(self, node):
        super().__init__(name="Wait For Full Charge")
        self._node          = node
        self._charge_started = False
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="battery_level", access=py_trees.common.Access.READ)

    def initialise(self):
        self._charge_started = False

    def update(self):
        if not self._charge_started:
            self._node.send("peripherals/command", {"action": "start_charging"})
            self._node.send("voice/speak",          {"text": "Battery low. Charging."})
            self._charge_started = True

        if self.bb.battery_level >= BATTERY_FULL_THRESHOLD:
            self._node.send("peripherals/command", {"action": "stop_charging"})
            self._node.send("voice/speak",          {"text": "Charging complete. Resuming mission."})
            return py_trees.common.Status.SUCCESS

        return py_trees.common.Status.RUNNING


class EStop(py_trees.behaviour.Behaviour):

    def __init__(self, node):
        super().__init__(name="E-Stop")
        self._node = node

    def update(self):
        self._node.send("navigation/command", {"action": "estop"})
        return py_trees.common.Status.SUCCESS


class VoiceAlert(py_trees.behaviour.Behaviour):

    def __init__(self, node, message="Warning."):
        super().__init__(name="Voice Alert")
        self._node    = node
        self._message = message

    def update(self):
        self._node.send("voice/speak", {"text": self._message})
        return py_trees.common.Status.SUCCESS


# ── Tree builder ─────────────────────────────────────────────────────────────

def create_emergency_tree(node):
    """
    Priority-ordered safety checks evaluated before every other tree.

    Structure
    ---------
    Emergency & Safety  [Selector]
    ├── Low Battery Branch  [Sequence, memory=True]          ← step 4 & 5
    │   ├── Is Battery Low?       condition: battery <= 20 %
    │   ├── Move To Charger       action: navigate, RUNNING → SUCCESS on arrival
    │   └── Wait For Full Charge  action: charge until 95 %, then stop
    └── Obstacle Branch  [Sequence, memory=False]
        ├── Is Obstacle Detected?
        ├── E-Stop
        └── Voice Alert  "Warning: obstacle detected."

    Flow for battery management (steps 4 & 5)
    ------------------------------------------
    While battery <= 20 %:
        IsBatteryLow → SUCCESS → sequence runs
        MoveToCharger stays RUNNING → Emergency stays RUNNING → Mission paused  (step 4)
        Once arrived → MoveToCharger SUCCESS, WaitForFullCharge runs
        WaitForFullCharge stays RUNNING until battery >= 95 %
        When full → stop_charging sent, WaitForFullCharge SUCCESS → sequence SUCCESS
    Next tick: battery >= 95 % → IsBatteryLow FAILURE → sequence FAILURE
               → Emergency FAILURE → Mission tree resumes  (step 5)
    """

    root = py_trees.composites.Selector(name="Emergency & Safety", memory=False)

    # ── Low Battery Branch ───────────────────────────────────────────────────
    # memory=True: once MoveToCharger has succeeded, skip it on subsequent
    # ticks — don't re-send the command while WaitForFullCharge is RUNNING.
    battery_seq = py_trees.composites.Sequence(
        name="Low Battery Branch", memory=True
    )
    battery_seq.add_children([
        IsBatteryLow(),
        MoveToCharger(node),
        WaitForFullCharge(node),
    ])

    # ── Obstacle Branch ──────────────────────────────────────────────────────
    obstacle_seq = py_trees.composites.Sequence(
        name="Obstacle Branch", memory=False
    )
    obstacle_seq.add_children([
        IsObstacleDetected(),
        EStop(node),
        VoiceAlert(node, message="Warning: obstacle detected. Stopping."),
    ])

    root.add_children([battery_seq, obstacle_seq])
    return root
