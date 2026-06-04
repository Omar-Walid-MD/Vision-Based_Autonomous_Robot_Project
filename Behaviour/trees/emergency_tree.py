import py_trees


# ── Conditions (blackboard only) ────────────────────────────────────────────

class IsBatteryLow(py_trees.behaviour.Behaviour):
    THRESHOLD = 20

    def __init__(self):
        super().__init__(name="Is Battery Low?")
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="battery_level", access=py_trees.common.Access.READ)

    def update(self):
        if self.bb.battery_level <= self.THRESHOLD:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE


class IsObstacleDetected(py_trees.behaviour.Behaviour):

    def __init__(self):
        super().__init__(name="Is Obstacle Detected?")
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="obstacle_detected", access=py_trees.common.Access.READ)

    def update(self):
        if self.bb.obstacle_detected:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE


# ── Actions (send via BehaviourNode) ────────────────────────────────────────

class MoveToCharger(py_trees.behaviour.Behaviour):

    def __init__(self, node):
        super().__init__(name="Move To Charger")
        self._node = node

    def update(self):
        self._node.send("navigation/command", {"action": "move_to_charger"})
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
    root = py_trees.composites.Selector(name="Emergency & Safety", memory=False)

    battery_seq = py_trees.composites.Sequence(name="Low Battery Branch", memory=False)
    battery_seq.add_children([IsBatteryLow(), MoveToCharger(node)])

    obstacle_seq = py_trees.composites.Sequence(name="Obstacle Branch", memory=False)
    obstacle_seq.add_children([
        IsObstacleDetected(),
        EStop(node),
        VoiceAlert(node, message="Warning: obstacle detected. Stopping."),
    ])

    root.add_children([battery_seq, obstacle_seq])
    return root
