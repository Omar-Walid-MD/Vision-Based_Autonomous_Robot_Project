import py_trees


<<<<<<< HEAD
=======
# ── Conditions ───────────────────────────────────────────────────────────────

>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
class IsLocalized(py_trees.behaviour.Behaviour):

    def __init__(self):
        super().__init__(name="Is Localized?")
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="localized", access=py_trees.common.Access.READ)

    def update(self):
        if self.bb.localized:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE


<<<<<<< HEAD
class LookForTarget(py_trees.behaviour.Behaviour):

    def __init__(self, node):
        super().__init__(name="Look For Target")
        self._node = node
        self._scan_sent = False
=======
# ── Actions ──────────────────────────────────────────────────────────────────

class LookForTarget(py_trees.behaviour.Behaviour):
    """
    Sends a scan request to the camera node.
    Waits for the blackboard flag `localized` to be set True
    (written by BehaviourNode when it receives the camera/tag_found topic).
    """

    def __init__(self, node):
        super().__init__(name="Look For Target")
        self._node         = node
        self._scan_sent    = False
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="localized", access=py_trees.common.Access.READ)

    def initialise(self):
        self._scan_sent = False

    def update(self):
        if not self._scan_sent:
<<<<<<< HEAD
            self._node.send("camera/scan")
            self._scan_sent = True

=======
            self._node.send("peripherals/look_for_tag")
            self._scan_sent = True

        # BehaviourNode will set localized=True when camera/tag_found arrives
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
        if self.bb.localized:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.RUNNING


class AnnounceReady(py_trees.behaviour.Behaviour):

    def __init__(self, node):
        super().__init__(name="Announce Ready")
        self._node = node

    def update(self):
        self._node.send("voice/speak", {"text": "Robot is ready."})
        return py_trees.common.Status.SUCCESS


<<<<<<< HEAD
=======
# ── Tree builder ─────────────────────────────────────────────────────────────

>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
def create_localization_tree(node):
    root = py_trees.composites.Selector(name="Localization", memory=False)

    localize_seq = py_trees.composites.Sequence(name="Localise Sequence", memory=False)
    localize_seq.add_children([LookForTarget(node), AnnounceReady(node)])

<<<<<<< HEAD
    root.add_children([IsLocalized(), localize_seq])
    return root
=======
    # IsLocalized succeeds immediately if already done → skips the sequence
    root.add_children([IsLocalized(), localize_seq])
    return root
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
