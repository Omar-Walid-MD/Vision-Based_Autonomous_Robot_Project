"""
error_tree.py
=============
Error & Node-Health subtree.

This tree is placed FIRST in the root Selector, so it is evaluated before
Emergency, Localization, and Mission trees on every tick.

Two checks
----------
1. Required-nodes check
   The server broadcasts the list of currently-connected nodes on the topic
   ``server/nodes_status``.  BehaviourNode writes that to the blackboard key
   ``connected_nodes`` (a set/list of node names).
   If any node in REQUIRED_NODES is absent, this branch returns SUCCESS
   (i.e. it "handles" the situation by halting everything and alerting).

2. Node-error check
   Any node can broadcast an error on topic ``node/error`` with payload:
       {"node": "<name>", "error": "<message>"}
   BehaviourNode writes this to blackboard key ``node_error``
   (None when no error is pending).
   If a node_error is present, this branch returns SUCCESS (halt + alert).

Returning SUCCESS from this tree prevents the root Selector from
falling through to any other tree, effectively pausing the whole mission
until the problem is resolved (operator must restart / reconnect nodes).
"""

import py_trees

# Nodes that MUST be connected before the robot does anything
REQUIRED_NODES = {"navigation", "camera0", "voice", "peripherals"}


# ─────────────────────────────────────────────────────────────────────────────
# Branch 1: Missing required node
# ─────────────────────────────────────────────────────────────────────────────

class RequiredNodesMissing(py_trees.behaviour.Behaviour):
    """
    Reads ``connected_nodes`` from the blackboard.
    Returns SUCCESS (trigger halt) if any node in REQUIRED_NODES is absent.
    Returns FAILURE (all good — let other trees run) if all are present.

    If connected_nodes is None (server hasn't reported yet), we wait
    (return SUCCESS — safe default: don't move until we know).
    """

    def __init__(self):
        super().__init__(name="Required Nodes Missing?")
        self.bb = py_trees.blackboard.Client(name=self.name)
        self.bb.register_key(key="connected_nodes",
                             access=py_trees.common.Access.READ)

    def update(self):
        connected = self.bb.connected_nodes   # set | list | None

        if connected is None:
            # Haven't received first status broadcast yet — be cautious
            return py_trees.common.Status.SUCCESS

        connected_set = set(connected)
        missing = REQUIRED_NODES - connected_set

        if missing:
            return py_trees.common.Status.SUCCESS   # something missing → halt

        return py_trees.common.Status.FAILURE       # all present → pass through


class HaltForMissingNodes(py_trees.behaviour.Behaviour):
    """
    Announces the missing nodes via voice (once) and keeps returning SUCCESS
    so the root Selector stays blocked.
    """

    def __init__(self, node):
        super().__init__(name="Halt: Missing Nodes")
        self._node        = node
        self._announced   = False
        self._last_missing = None
        self.bb = py_trees.blackboard.Client(name=self.name)
        self.bb.register_key(key="connected_nodes",
                             access=py_trees.common.Access.READ)

    def initialise(self):
        self._announced    = False
        self._last_missing = None

    def update(self):
        connected = self.bb.connected_nodes or set()
        missing   = REQUIRED_NODES - set(connected)

        if missing != self._last_missing:
            self._last_missing = missing
            self._announced    = False  # re-announce if the set changed

        if not self._announced:
            names = ", ".join(sorted(missing))
            self._node.send("voice/speak", {
                "text": f"System halted. The following modules are offline: {names}. "
                        "Please check connections."
            })
            print(f"[ErrorTree] HALT — missing nodes: {missing}")
            self._announced = True

        return py_trees.common.Status.SUCCESS   # keep blocking


# ─────────────────────────────────────────────────────────────────────────────
# Branch 2: Node runtime error
# ─────────────────────────────────────────────────────────────────────────────

class NodeErrorPresent(py_trees.behaviour.Behaviour):
    """
    Returns SUCCESS if ``node_error`` on the blackboard is not None.
    """

    def __init__(self):
        super().__init__(name="Node Error Present?")
        self.bb = py_trees.blackboard.Client(name=self.name)
        self.bb.register_key(key="node_error",
                             access=py_trees.common.Access.READ)

    def update(self):
        if self.bb.node_error is not None:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE


class HaltForNodeError(py_trees.behaviour.Behaviour):
    """
    Announces the node error via voice and logs it.
    Keeps returning SUCCESS (halt) until node_error is cleared.
    Clears node_error after announcing so repeated ticks don't re-speak,
    but the outer Sequence will still be SUCCESS until the node reconnects
    (handled by RequiredNodesMissing branch in the next tick).
    """

    def __init__(self, node):
        super().__init__(name="Halt: Node Error")
        self._node      = node
        self._announced = False
        self.bb = py_trees.blackboard.Client(name=self.name)
        self.bb.register_key(key="node_error",
                             access=py_trees.common.Access.READ)
        self.bb.register_key(key="node_error",
                             access=py_trees.common.Access.WRITE)

    def initialise(self):
        self._announced = False

    def update(self):
        err = self.bb.node_error

        if err and not self._announced:
            node_name = err.get("node",  "unknown module")
            message   = err.get("error", "unknown error")
            self._node.send("voice/speak", {
                "text": f"Critical error in {node_name}: {message}. "
                        "System is halting for safety."
            })
            print(f"[ErrorTree] HALT — node error: {err}")
            self._announced    = True
            self.bb.node_error = None   # clear so we don't re-announce

        return py_trees.common.Status.SUCCESS   # keep blocking


# ─────────────────────────────────────────────────────────────────────────────
# Tree builder
# ─────────────────────────────────────────────────────────────────────────────

def create_error_tree(node):
    """
    Error & Node Health  [Selector, memory=False]
    ├── Missing-nodes Branch  [Sequence, memory=True]
    │   ├── Required Nodes Missing?   condition
    │   └── Halt: Missing Nodes       action  — stays SUCCESS until nodes come back
    └── Node-error Branch  [Sequence, memory=True]
        ├── Node Error Present?       condition
        └── Halt: Node Error          action  — announces + clears error

    The outer Selector returns:
      SUCCESS  → one of the error conditions fired  → root Selector stops here,
                 Emergency / Mission trees don't run.
      FAILURE  → all nodes present AND no errors     → root Selector falls
                 through to Emergency / Localization / Mission trees.
    """

    root = py_trees.composites.Selector(
        name="Error & Node Health", memory=False
    )

    # Branch 1 — missing nodes
    missing_seq = py_trees.composites.Sequence(
        name="Missing Nodes Branch", memory=True
    )
    missing_seq.add_children([
        RequiredNodesMissing(),
        HaltForMissingNodes(node),
    ])

    # Branch 2 — runtime node error
    error_seq = py_trees.composites.Sequence(
        name="Node Error Branch", memory=True
    )
    error_seq.add_children([
        NodeErrorPresent(),
        HaltForNodeError(node),
    ])

    root.add_children([missing_seq, error_seq])
    return root
