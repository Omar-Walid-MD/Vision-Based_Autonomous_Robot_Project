"""
patient_checkup_tree.py
=======================
Simplified behaviour tree for the patient-checkup mission.

The behaviour node sends ONE command to peripherals to start the full checkup
for each patient. Peripherals handles all the steps internally (greetings,
measurements, alerts, etc.) and reports back with a status of "done" or
"failed" on the topic  peripherals/checkup_status.

Two states per patient
----------------------
  navigate  → send move_to_goal to navigation, wait for nav_status done/failed
  checkup   → send start_checkup to peripherals, wait for checkup_status done/failed

Blackboard keys used
--------------------
  current_task           (READ / WRITE)  – the task dict from voice command
  nav_status             (READ / WRITE)  – set by navigation/status topic
  checkup_status         (READ / WRITE)  – set by peripherals/checkup_status topic
  checkup_state          (READ / WRITE)  – internal index + phase dict
  checkup_start_location (READ / WRITE)  – saved at mission start, returned to at end
"""

import py_trees


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _bb_client(name, keys_read=(), keys_write=()):
    bb = py_trees.blackboard.Client(name=name)
    for k in keys_read:
        bb.register_key(key=k, access=py_trees.common.Access.READ)
    for k in keys_write:
        bb.register_key(key=k, access=py_trees.common.Access.WRITE)
    return bb


# ─────────────────────────────────────────────────────────────────────────────
# Condition: Is this a checkup task?
# ─────────────────────────────────────────────────────────────────────────────

class IsCheckupTask(py_trees.behaviour.Behaviour):
    """
    SUCCESS  – current_task is {"type": "checkup", "patients": [...]} with ≥1 patient.
    FAILURE  – anything else.
    """

    def __init__(self):
        super().__init__(name="Is Checkup Task?")
        self.bb = _bb_client(self.name, keys_read=["current_task"])

    def update(self):
        task = self.bb.current_task
        if (
            isinstance(task, dict)
            and task.get("type") == "checkup"
            and isinstance(task.get("patients"), list)
            and len(task["patients"]) > 0
        ):
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE


# ─────────────────────────────────────────────────────────────────────────────
# Action: Save starting location
# ─────────────────────────────────────────────────────────────────────────────

class SaveStartLocation(py_trees.behaviour.Behaviour):
    """Tells navigation to record the current pose; runs once per mission."""

    def __init__(self, node):
        super().__init__(name="Save Start Location")
        self._node = node
        self.bb = _bb_client(self.name,
                             keys_read=["checkup_start_location"],
                             keys_write=["checkup_start_location"])

    def update(self):
        if self.bb.checkup_start_location is None:
            self._node.send("navigation/command", {"action": "save_start_location"})
            self.bb.checkup_start_location = "__saved__"
        return py_trees.common.Status.SUCCESS


# ─────────────────────────────────────────────────────────────────────────────
# Action: Initialise checkup state
# ─────────────────────────────────────────────────────────────────────────────

class InitCheckup(py_trees.behaviour.Behaviour):
    """Builds the state dict from the task's patient list. Runs only once."""

    def __init__(self):
        super().__init__(name="Init Checkup")
        self.bb = _bb_client(self.name,
                             keys_read=["current_task", "checkup_state"],
                             keys_write=["checkup_state"])

    def update(self):
        if self.bb.checkup_state is not None:
            return py_trees.common.Status.SUCCESS  # already initialised

        task = self.bb.current_task
        self.bb.checkup_state = {
            "patients": list(task["patients"]),
            "index":    0,
            "phase":    "navigate",   # "navigate" | "checkup"
        }
        return py_trees.common.Status.SUCCESS


# ─────────────────────────────────────────────────────────────────────────────
# Action: Visit each patient  (2-state machine: navigate → checkup)
# ─────────────────────────────────────────────────────────────────────────────

class VisitPatients(py_trees.behaviour.Behaviour):
    """
    Iterates over every patient with exactly two states:

    navigate
        Sends move_to_goal to navigation and waits for nav_status.
        → done    : transition to checkup
        → failed  : skip patient, advance to next

    checkup
        Sends start_checkup (with patient location for facing direction) to
        peripherals and waits for checkup_status.
        → done    : advance to next patient (or SUCCESS if all done)
        → failed  : log, advance to next patient

    Peripherals owns everything inside the checkup: greeting, voice prompts,
    temperature & heart-rate measurement, and alerting staff if needed.
    """

    def __init__(self, node):
        super().__init__(name="Visit Patients")
        self._node = node
        self.bb = _bb_client(
            self.name,
            keys_read=[
                "checkup_state", "nav_status", "checkup_status",
            ],
            keys_write=[
                "checkup_state", "nav_status", "checkup_status", "current_task",
            ],
        )

    def initialise(self):
        # Clear stale statuses on (re-)entry
        self.bb.nav_status     = "idle"
        self.bb.checkup_status = None

    # ── helpers ───────────────────────────────────────────────────────────────

    def _set_phase(self, phase):
        s = self.bb.checkup_state
        s["phase"] = phase
        self.bb.checkup_state = s

    def _advance_or_finish(self):
        """Move index to next patient; return SUCCESS when all are done."""
        s = self.bb.checkup_state
        s["index"] += 1
        if s["index"] < len(s["patients"]):
            s["phase"] = "navigate"
            self.bb.checkup_state  = s
            self.bb.nav_status     = "idle"
            self.bb.checkup_status = None
            return py_trees.common.Status.RUNNING
        else:
            s["phase"] = "done"
            self.bb.checkup_state = s
            return py_trees.common.Status.SUCCESS

    # ── update ────────────────────────────────────────────────────────────────

    def update(self):
        s     = self.bb.checkup_state
        phase = s["phase"]
        pat   = s["patients"][s["index"]]

        # ── STATE 1: navigate ──────────────────────────────────────────────
        if phase == "navigate":
            if self.bb.nav_status == "idle":
                self._node.send("navigation/command", {
                    "action": "move_to_goal",
                    "task":   pat["location"],
                })
                self.bb.nav_status = "running"
                return py_trees.common.Status.RUNNING

            nav = self.bb.nav_status
            if nav == "running":
                return py_trees.common.Status.RUNNING

            if nav == "done":
                self.bb.nav_status = "idle"
                self._set_phase("checkup")
                return py_trees.common.Status.RUNNING

            # nav == "failed" → skip this patient
            print(f"[CheckupTree] Navigation to '{pat['location']}' failed — skipping patient.")
            self.bb.nav_status = "idle"
            return self._advance_or_finish()

        # ── STATE 2: checkup ───────────────────────────────────────────────
        if phase == "checkup":
            if self.bb.checkup_status is None:
                # Kick off the full checkup on the peripherals node
                self._node.send("peripherals/command", {
                    "action":   "start_checkup",
                    "location": pat["location"],
                    "facing":   pat.get("facing", "forward"),
                })
                # Use a sentinel so we don't re-send on the next tick
                self.bb.checkup_status = "running"
                return py_trees.common.Status.RUNNING

            status = self.bb.checkup_status
            if status == "running":
                return py_trees.common.Status.RUNNING

            # "done" or "failed" — either way advance to next patient
            if status == "failed":
                print(f"[CheckupTree] Checkup failed for patient at '{pat['location']}'.")

            self.bb.checkup_status = None
            return self._advance_or_finish()

        # Should never reach here
        return py_trees.common.Status.FAILURE


# ─────────────────────────────────────────────────────────────────────────────
# Action: Return to starting location
# ─────────────────────────────────────────────────────────────────────────────

class ReturnToStart(py_trees.behaviour.Behaviour):
    """Navigates back to the saved start location and clears the task."""

    def __init__(self, node):
        super().__init__(name="Return To Start")
        self._node     = node
        self._cmd_sent = False
        self.bb = _bb_client(
            self.name,
            keys_read=["nav_status", "checkup_start_location"],
            keys_write=["nav_status", "current_task", "checkup_state",
                        "checkup_start_location", "checkup_status"],
        )

    def initialise(self):
        self._cmd_sent     = False
        self.bb.nav_status = "idle"

    def update(self):
        if not self._cmd_sent:
            self._node.send("navigation/command", {"action": "return_to_start"})
            self._cmd_sent = True

        nav = self.bb.nav_status
        if nav == "done":
            self._node.send("voice/speak",
                            {"text": "Checkup mission complete. Returning to base."})
            self._clear()
            return py_trees.common.Status.SUCCESS
        if nav == "failed":
            self._node.send("voice/speak",
                            {"text": "Could not return to starting position."})
            self._clear()
            return py_trees.common.Status.FAILURE

        return py_trees.common.Status.RUNNING

    def _clear(self):
        self.bb.current_task           = None
        self.bb.checkup_state          = None
        self.bb.checkup_start_location = None
        self.bb.checkup_status         = None
        self.bb.nav_status             = "idle"


# ─────────────────────────────────────────────────────────────────────────────
# Tree builder
# ─────────────────────────────────────────────────────────────────────────────

def create_patient_checkup_tree(node):
    """
    Patient Checkup  [Sequence, memory=True]
    ├── Is Checkup Task?       condition  – guard: only runs for checkup tasks
    ├── Save Start Location    action     – record current pose once
    ├── Init Checkup           action     – build patient list + state dict
    ├── Visit Patients         action     – 2-state loop: navigate → checkup
    └── Return To Start        action     – go back, clear task

    Per-patient flow inside VisitPatients:
        navigate  →  checkup  →  next patient  →  …  →  SUCCESS
                  (peripherals drives all checkup steps internally)
    """
    root = py_trees.composites.Sequence(name="Patient Checkup", memory=True)
    root.add_children([
        IsCheckupTask(),
        SaveStartLocation(node),
        InitCheckup(),
        VisitPatients(node),
        ReturnToStart(node),
    ])
    return root
