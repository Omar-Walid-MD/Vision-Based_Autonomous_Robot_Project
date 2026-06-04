import py_trees


<<<<<<< HEAD
=======
# ── Conditions ───────────────────────────────────────────────────────────────

>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
class HasTask(py_trees.behaviour.Behaviour):

    def __init__(self):
        super().__init__(name="Has Task?")
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="current_task", access=py_trees.common.Access.READ)

    def update(self):
        if self.bb.current_task is not None:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE


<<<<<<< HEAD
class IsNotCharging(py_trees.behaviour.Behaviour):

    def __init__(self):
        super().__init__(name="Is Not Charging?")
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="is_charging", access=py_trees.common.Access.READ)

    def update(self):
        if not self.bb.is_charging:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE


class MoveToGoal(py_trees.behaviour.Behaviour):

    def __init__(self, node):
        super().__init__(name="Move To Goal")
        self._node = node
        self._cmd_sent = False
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="current_task", access=py_trees.common.Access.READ)
        self.bb.register_key(key="nav_status", access=py_trees.common.Access.READ)
        self.bb.register_key(key="current_task", access=py_trees.common.Access.WRITE)
=======
# ── Actions ──────────────────────────────────────────────────────────────────

class MoveToGoal(py_trees.behaviour.Behaviour):
    """
    Sends the current task to the navigation node.
    Stays RUNNING until navigation/status topic reports done or failed.
    """

    def __init__(self, node):
        super().__init__(name="Move To Goal")
        self._node       = node
        self._cmd_sent   = False
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="current_task",   access=py_trees.common.Access.READ)
        self.bb.register_key(key="nav_status",     access=py_trees.common.Access.READ)
        self.bb.register_key(key="current_task",   access=py_trees.common.Access.WRITE)
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a

    def initialise(self):
        self._cmd_sent = False

    def update(self):
        if not self._cmd_sent:
            self._node.send("navigation/command", {
                "action": "move_to_goal",
<<<<<<< HEAD
                "task": self.bb.current_task,
            })
            self._cmd_sent = True

        status = self.bb.nav_status
        if status == "done":
            self.bb.current_task = None
=======
                "task":   self.bb.current_task,
            })
            self._cmd_sent = True

        status = self.bb.nav_status   # updated by BehaviourNode via navigation/status topic
        if status == "done":
            self.bb.current_task = None   # clear task when finished
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
            return py_trees.common.Status.SUCCESS
        if status == "failed":
            self.bb.current_task = None
            return py_trees.common.Status.FAILURE
        return py_trees.common.Status.RUNNING


class ListenForVoiceCommand(py_trees.behaviour.Behaviour):
<<<<<<< HEAD

    def __init__(self, node):
        super().__init__(name="Listen For Voice Command")
        self._node = node
        self._cmd_sent = False
=======
    """
    Tells the voice node to start listening.
    Stays RUNNING until voice/command topic delivers a task to the blackboard.
    """

    def __init__(self, node):
        super().__init__(name="Listen For Voice Command")
        self._node       = node
        self._cmd_sent   = False
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="current_task", access=py_trees.common.Access.READ)

    def initialise(self):
        self._cmd_sent = False

    def update(self):
        if not self._cmd_sent:
            self._node.send("voice/command", {"action": "listen"})
            self._cmd_sent = True

<<<<<<< HEAD
=======
        # BehaviourNode sets current_task when voice/command topic fires
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
        if self.bb.current_task is not None:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.RUNNING


<<<<<<< HEAD
def create_mission_tree(node):
    root = py_trees.composites.Selector(name="Mission Selector", memory=False)

    nav_seq = py_trees.composites.Sequence(name="Navigation Task", memory=True)
    nav_seq.add_children([HasTask(), MoveToGoal(node)])

    idle_seq = py_trees.composites.Sequence(name="Idle Listening", memory=False)
    idle_seq.add_children([IsNotCharging(), ListenForVoiceCommand(node)])

    root.add_children([nav_seq, idle_seq])
    return root
=======
# ── Tree builder ─────────────────────────────────────────────────────────────

def create_mission_tree(node):
    root = py_trees.composites.Selector(name="Mission Selector", memory=False)

    # Branch 1: if a task exists, navigate to it
    nav_seq = py_trees.composites.Sequence(name="Navigation Task", memory=True)
    nav_seq.add_children([HasTask(), MoveToGoal(node)])

    # Branch 2: idle — listen for a voice command
    idle_seq = py_trees.composites.Sequence(name="Idle Listening", memory=False)
    idle_seq.add_children([ListenForVoiceCommand(node)])

    root.add_children([nav_seq, idle_seq])
    return root
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
