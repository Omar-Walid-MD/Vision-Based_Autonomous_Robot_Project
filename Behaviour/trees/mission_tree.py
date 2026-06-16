import py_trees


# ── Conditions ───────────────────────────────────────────────────────────────

class HasTask(py_trees.behaviour.Behaviour):
    """Returns SUCCESS when a task is waiting on the blackboard."""

    def __init__(self):
        super().__init__(name="Has Task?")
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="current_task", access=py_trees.common.Access.READ)

    def update(self):
        if self.bb.current_task is not None:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE


# ── Actions ──────────────────────────────────────────────────────────────────

class ValidateLocation(py_trees.behaviour.Behaviour):
    """
    Asks the navigation node whether current_task names a reachable location.

    Flow
    ----
    initialise():   reset location_valid → None, send 'validate_location'
    update():
        - None     → RUNNING (waiting for navigation/location_valid response)
        - True     → SUCCESS (proceed to MoveToGoal)
        - False    → announce invalid, clear task, FAILURE (drop back to idle)

    The navigation node must publish on topic 'navigation/location_valid'
    with payload {"valid": true/false}.  BehaviourNode writes that to
    blackboard key 'location_valid' via _on_location_validated().
    """

    def __init__(self, node):
        super().__init__(name="Validate Location")
        self._node        = node
        self._req_sent    = False
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="current_task",    access=py_trees.common.Access.READ)
        self.bb.register_key(key="current_task",    access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="location_valid",  access=py_trees.common.Access.READ)
        self.bb.register_key(key="location_valid",  access=py_trees.common.Access.WRITE)

    def initialise(self):
        self._req_sent        = False
        self.bb.location_valid = None   # clear any previous result

    def update(self):
        if not self._req_sent:
            self._node.send("navigation/command", {
                "action": "validate_location",
                "task":   self.bb.current_task,
            })
            self._req_sent = True

        result = self.bb.location_valid

        if result is None:
            return py_trees.common.Status.RUNNING   # waiting for response

        if result is True:
            return py_trees.common.Status.SUCCESS   # proceed to MoveToGoal

        # Invalid location — inform user and clear the task
        self._node.send("voice/speak", {
            "text": f"Unknown location: {self.bb.current_task}. Please repeat."
        })
        self.bb.current_task   = None
        self.bb.location_valid = None
        return py_trees.common.Status.FAILURE


class MoveToGoal(py_trees.behaviour.Behaviour):
    """
    Sends current_task to navigation and waits for completion.

    Resets nav_status to 'idle' on initialise() so a stale 'done' from a
    previous run (e.g. the charger approach) doesn't cause an instant finish.
    """

    def __init__(self, node):
        super().__init__(name="Move To Goal")
        self._node     = node
        self._cmd_sent = False
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="current_task",   access=py_trees.common.Access.READ)
        self.bb.register_key(key="current_task",   access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="nav_status",     access=py_trees.common.Access.READ)
        self.bb.register_key(key="nav_status",     access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="location_valid", access=py_trees.common.Access.WRITE)

    def initialise(self):
        self._cmd_sent     = False
        self.bb.nav_status = "idle"   # clear stale result

    def update(self):
        if not self._cmd_sent:
            self._node.send("navigation/command", {
                "action": "move_to_goal",
                "task":   self.bb.current_task,
            })
            self._cmd_sent = True

        status = self.bb.nav_status
        if status == "done":
            self._node.send("voice/speak", {
                "text": f"Arrived at {self.bb.current_task}."
            })
            self._clear()
            return py_trees.common.Status.SUCCESS
        if status == "failed":
            self._node.send("voice/speak", {"text": "Navigation failed."})
            self._clear()
            return py_trees.common.Status.FAILURE

        return py_trees.common.Status.RUNNING

    def _clear(self):
        self.bb.current_task   = None
        self.bb.location_valid = None


class ListenForVoiceCommand(py_trees.behaviour.Behaviour):
    """
    Tells the voice node to start listening and waits for a task to arrive.

    Stays RUNNING until voice/command topic delivers a task to the blackboard.
    The voice node writes to 'current_task' via BehaviourNode._on_voice_command.
    """

    def __init__(self, node):
        super().__init__(name="Listen For Voice Command")
        self._node     = node
        self._cmd_sent = False
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="current_task", access=py_trees.common.Access.READ)

    def initialise(self):
        self._cmd_sent = False

    def update(self):
        if not self._cmd_sent:
            self._node.send("voice/command", {"action": "listen"})
            self._cmd_sent = True

        if self.bb.current_task is not None:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.RUNNING


# ── Tree builder ─────────────────────────────────────────────────────────────

def create_mission_tree(node):
    """
    Normal-operation tree: listen for commands and navigate to goals.

    Structure
    ---------
    Mission  [Selector]
    ├── Navigation Task  [Sequence, memory=True]
    │   ├── Has Task?             condition: current_task is not None
    │   ├── Validate Location     action: ask nav if location exists  ← step 3
    │   └── Move To Goal          action: navigate, RUNNING until done
    └── Idle Listening  [Sequence]
        └── Listen For Voice Command   ← step 2 (RUNNING until command heard)

    Flow for step 3
    ---------------
    Voice command sets current_task → HasTask SUCCESS
    ValidateLocation sends validate request, waits for navigation/location_valid
        valid   → SUCCESS → MoveToGoal runs
        invalid → FAILURE → sequence FAILURE → Idle branch retries
    """

    root = py_trees.composites.Selector(name="Mission", memory=False)

    # ── Branch 1: execute a validated navigation task ────────────────────────
    # memory=True: once HasTask and ValidateLocation succeed, don't re-evaluate
    # them while MoveToGoal is RUNNING.
    nav_seq = py_trees.composites.Sequence(
        name="Navigation Task", memory=True
    )
    nav_seq.add_children([
        HasTask(),
        ValidateLocation(node),
        MoveToGoal(node),
    ])

    # ── Branch 2: idle — wait for the next voice command ────────────────────
    idle_seq = py_trees.composites.Sequence(
        name="Idle Listening", memory=False
    )
    idle_seq.add_children([ListenForVoiceCommand(node)])

    root.add_children([nav_seq, idle_seq])
    return root
