import py_trees


# ── Conditions ───────────────────────────────────────────────────────────────

class HasTask(py_trees.behaviour.Behaviour):

    def __init__(self):
        super().__init__(name="Has Task?")
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="current_task", access=py_trees.common.Access.READ)

    def update(self):
        if self.bb.current_task is not None:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE


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

    def initialise(self):
        self._cmd_sent = False

    def update(self):
        if not self._cmd_sent:
            self._node.send("navigation/command", {
                "action": "move_to_goal",
                "task":   self.bb.current_task,
            })
            self._cmd_sent = True

        status = self.bb.nav_status   # updated by BehaviourNode via navigation/status topic
        if status == "done":
            self.bb.current_task = None   # clear task when finished
            return py_trees.common.Status.SUCCESS
        if status == "failed":
            self.bb.current_task = None
            return py_trees.common.Status.FAILURE
        return py_trees.common.Status.RUNNING


class ListenForVoiceCommand(py_trees.behaviour.Behaviour):
    """
    Tells the voice node to start listening.
    Stays RUNNING until voice/command topic delivers a task to the blackboard.
    """

    def __init__(self, node):
        super().__init__(name="Listen For Voice Command")
        self._node       = node
        self._cmd_sent   = False
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="current_task", access=py_trees.common.Access.READ)

    def initialise(self):
        self._cmd_sent = False

    def update(self):
        if not self._cmd_sent:
            self._node.send("voice/command", {"action": "listen"})
            self._cmd_sent = True

        # BehaviourNode sets current_task when voice/command topic fires
        if self.bb.current_task is not None:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.RUNNING


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
