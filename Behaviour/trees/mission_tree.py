import py_trees


# ── Conditions ───────────────────────────────────────────────────────────────

class HasTask(py_trees.behaviour.Behaviour):

    def __init__(self):
        super().__init__(name="Has Task?")
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="task_queue", access=py_trees.common.Access.READ)

    def update(self):
        if len(self.bb.task_queue) > 0:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE


# ── Actions ──────────────────────────────────────────────────────────────────

class MoveToGoal(py_trees.behaviour.Behaviour):
    """
    Pops the first task from task_queue, sends it to navigation,
    and stays RUNNING until navigation/status reports done or failed.
    """

    def __init__(self, node):
        super().__init__(name="Move To Goal")
        self._node       = node
        self._cmd_sent   = False
        self._active_task = None          # task we popped and are currently executing
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="task_queue", access=py_trees.common.Access.READ)
        self.bb.register_key(key="task_queue", access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="nav_status", access=py_trees.common.Access.READ)
        self.bb.register_key(key="nav_status", access=py_trees.common.Access.WRITE)


    def initialise(self):
        # Called once each time this node becomes RUNNING.
        # Pop the first task from the queue.
        self._cmd_sent    = False
        self._active_task = None
        queue = self.bb.task_queue
        if queue:
            self._active_task  = queue[0]
            self.bb.task_queue = queue[1:]   # pop front
            self.bb.nav_status = "idle"      # reset so stale "done" doesn't fire instantly

    def update(self):
        if self._active_task is None:
            # Queue was empty when initialise() ran — shouldn't normally happen
            return py_trees.common.Status.FAILURE

        if not self._cmd_sent:
            self._node.send("navigation/command", {
                "action": "move_to_goal",
                "task":   self._active_task,
            })
            self._cmd_sent = True

        status = self.bb.nav_status
        if status == "done":
            self.bb.nav_status = "idle"      # reset for next task
            print(f"[MoveToGoal] Task done: {self._active_task}  (remaining: {len(self.bb.task_queue)})")
            return py_trees.common.Status.SUCCESS
        if status == "failed":
            self.bb.nav_status = "idle"
            print(f"[MoveToGoal] Task failed: {self._active_task}")
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
        self.bb.register_key(key="task_queue", access=py_trees.common.Access.READ)

    def initialise(self):
        self._cmd_sent = False

    def update(self):
        if not self._cmd_sent:
            self._node.send("voice/command", {"action": "listen"})
            self._cmd_sent = True

        # BehaviourNode appends to task_queue when voice/command topic fires
        if len(self.bb.task_queue) > 0:
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