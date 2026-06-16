"""
checkup_sequence.py - CheckupSequence: orchestrates the full patient checkup.

State machine, advanced one step per main-loop tick via update() — no
threads, following the same pattern as VitalSensorsReader, ArmController,
and HeadController.

Sequence
--------
IDLE
  -> (start requested)
AWAITING_TEMP_CONFIRM      : waiting for voice node confirmation to begin
                              the temperature check
TEMP_POSITIONING           : move arm into position for the thermometer
                              (placeholder for alignment + endpoint calc —
                              currently uses checkup_position())
TEMP_SCANNING               : VitalSensorsReader thermo scan/confirm/sample
TEMP_DELAY                  : 5 second delay after temperature result
AWAITING_HEART_CONFIRM      : waiting for voice node confirmation to begin
                              the heart/SpO2 check
HEART_POSITIONING           : move arm into position for the pulse sensor
HEART_SCANNING              : VitalSensorsReader heart scan/confirm/sample
DONE                        : checkup complete, publish completion event
FAILED                      : checkup failed, publish failure event

Topics (handled by PeripheralsNode, calling into this class)
--------------------------------------------------------------
Incoming:
  peripherals/checkup/start          -> start_checkup()
  voice/checkup/confirm               -> on_voice_confirm(data)
                                          { "confirmed": bool }

Outgoing (via on_event callback):
  peripherals/checkup/status          -> { "phase": <str> }   (progress)
  peripherals/checkup/result          -> { "type": "temperature"|"heart",
                                            ... reading fields ...,
                                            "alert": bool }
  voice/checkup/request_confirm       -> { "step": "temperature"|"heart" }
  peripherals/checkup/complete        -> {}
  peripherals/checkup/failed          -> { "reason": <str> }

Abnormal reading thresholds
----------------------------
Defined as module constants below; tune to your medical requirements.
"""

from __future__ import annotations

import logging
import time
from enum import Enum, auto
from typing import Callable, Dict, Optional

from controllers import ArmController
from vital_sensors import VitalSensorsReader


# ------------------------------------------------------------------
# Abnormal reading thresholds (tune as needed)
# ------------------------------------------------------------------

TEMP_LOW_C    = 35.5
TEMP_HIGH_C   = 37.8
BPM_LOW       = 50
BPM_HIGH      = 120
SPO2_LOW      = 94

# Timing
CONFIRM_TIMEOUT_SEC = 30.0   # how long to wait for voice confirmation
POST_TEMP_DELAY_SEC = 5.0    # delay between temperature and heart checks


class CheckupState(Enum):
    IDLE                    = auto()
    AWAITING_TEMP_CONFIRM   = auto()
    TEMP_POSITIONING        = auto()
    TEMP_SCANNING           = auto()
    TEMP_DELAY              = auto()
    AWAITING_HEART_CONFIRM  = auto()
    HEART_POSITIONING       = auto()
    HEART_SCANNING          = auto()
    DONE                    = auto()
    FAILED                  = auto()


class CheckupSequence:
    """
    Orchestrates the temperature + heart/SpO2 checkup sequence.

    Call update() once per main-loop tick. Call start_checkup() and
    on_voice_confirm() from topic handlers — both only set state, the
    actual work happens in update().
    """

    def __init__(self, arm: Optional[ArmController], vitals: Optional[VitalSensorsReader]):
        self.arm = arm
        self.vitals = vitals

        self._state: CheckupState = CheckupState.IDLE
        self._delay_until: float = 0.0
        self._confirm_deadline: float = 0.0

        # Set by PeripheralsNode: on_event(topic, data)
        self.on_event: Optional[Callable[[str, Dict], None]] = None

        # Latches results from VitalSensorsReader.on_result so this class
        # can detect "a thermo/heart cycle just finished" without polling
        # vitals state directly. PeripheralsNode wires VitalSensorsReader's
        # on_result to call both this and its own publish.
        self._last_thermo_result: Optional[Dict] = None
        self._last_heart_result:  Optional[Dict] = None

    # ------------------------------------------------------------------
    # Public trigger API (called from topic handlers — flags only)
    # ------------------------------------------------------------------

    def start_checkup(self) -> None:
        """Begin the checkup sequence. No-op if one is already running."""
        if self._state != CheckupState.IDLE:
            logging.warning("Checkup already in progress, ignoring start request.")
            return

        if self.arm is None or self.vitals is None:
            logging.warning("Checkup requires both arm and vitals to be enabled.")
            self._fail("arm or vitals subsystem disabled")
            return

        logging.info("Checkup: starting — requesting temperature confirmation")
        self._request_confirm("temperature")
        self._state = CheckupState.AWAITING_TEMP_CONFIRM

    def on_voice_confirm(self, data: Dict) -> None:
        """
        Called when voice/checkup/confirm is received.
        data: { "confirmed": bool }
        """
        confirmed = bool(data.get("confirmed", False))

        if self._state == CheckupState.AWAITING_TEMP_CONFIRM:
            if confirmed:
                logging.info("Checkup: temperature confirmed — positioning arm")
                self._state = CheckupState.TEMP_POSITIONING
            else:
                self._fail("user declined temperature check")

        elif self._state == CheckupState.AWAITING_HEART_CONFIRM:
            if confirmed:
                logging.info("Checkup: heart check confirmed — positioning arm")
                self._state = CheckupState.HEART_POSITIONING
            else:
                self._fail("user declined heart/SpO2 check")

        else:
            logging.debug("Checkup: voice confirm received but not awaited, ignoring.")

    def notify_thermo_result(self, result: Dict) -> None:
        """
        Called by PeripheralsNode whenever VitalSensorsReader publishes a
        thermo result, so this state machine can pick it up if a checkup
        is waiting on it.
        """
        self._last_thermo_result = result

    def notify_heart_result(self, result: Dict) -> None:
        """Same as notify_thermo_result, for heart/SpO2 results."""
        self._last_heart_result = result

    # ------------------------------------------------------------------
    # update() — call from the main loop every tick
    # ------------------------------------------------------------------

    def update(self) -> None:
        state = self._state

        if state in (CheckupState.IDLE, CheckupState.DONE, CheckupState.FAILED):
            return

        # --- Confirmation waits: timeout if voice node never responds ---
        if state in (CheckupState.AWAITING_TEMP_CONFIRM, CheckupState.AWAITING_HEART_CONFIRM):
            if time.monotonic() > self._confirm_deadline:
                step = "temperature" if state == CheckupState.AWAITING_TEMP_CONFIRM else "heart"
                self._fail(f"no confirmation received for {step} check")
            return

        # --- Temperature branch ---
        if state == CheckupState.TEMP_POSITIONING:
            self._position_for_temperature()
            return

        if state == CheckupState.TEMP_SCANNING:
            self._advance_temp_scan()
            return

        if state == CheckupState.TEMP_DELAY:
            if time.monotonic() >= self._delay_until:
                logging.info("Checkup: post-temperature delay complete — requesting heart confirmation")
                self._request_confirm("heart")
                self._state = CheckupState.AWAITING_HEART_CONFIRM
            return

        # --- Heart branch ---
        if state == CheckupState.HEART_POSITIONING:
            self._position_for_heart()
            return

        if state == CheckupState.HEART_SCANNING:
            self._advance_heart_scan()
            return

    # ------------------------------------------------------------------
    # Temperature branch steps
    # ------------------------------------------------------------------

    def _position_for_temperature(self) -> None:
        """
        Move the arm so the thermometer faces the patient's face.

        NOTE: This is a placeholder for the full camera-guided alignment +
        endpoint-calculation sequence (head alignment to the detected face
        position, a fresh endpoint reading, then arm.move_to(x, y)). That
        flow is described in the technical report but not yet implemented
        in code. For now this uses the existing fixed checkup_position().
        """
        if self.arm is None:
            self._fail("arm unavailable during temperature positioning")
            return

        self.arm.checkup_position(mode="smooth", blocking=True)
        logging.info("Checkup: arm positioned for temperature — starting thermo scan")

        if self.vitals is None:
            self._fail("vitals unavailable during temperature positioning")
            return

        self._last_thermo_result = None
        self.vitals.request_thermo()
        self._state = CheckupState.TEMP_SCANNING

    def _advance_temp_scan(self) -> None:
        """
        Wait for VitalSensorsReader to finish its thermo scan/confirm/sample
        cycle (signalled via notify_thermo_result). Once a result arrives,
        check for abnormal values, publish the result, and move on to the
        post-temperature delay.
        """
        result = self._last_thermo_result
        if result is None:
            return  # still scanning — VitalSensorsReader.update_thermo() is progressing

        body_temp = result.get("body_temperature_c")
        alert = body_temp is None or body_temp < TEMP_LOW_C or body_temp > TEMP_HIGH_C

        self._emit("peripherals/checkup/result", {
            "type": "temperature",
            "body_temperature_c": body_temp,
            "room_temperature_c": result.get("room_temperature_c"),
            "alert": alert,
        })

        if alert:
            logging.warning("Checkup: abnormal temperature reading (%s°C)", body_temp)
        else:
            logging.info("Checkup: temperature reading %.1f°C", body_temp)

        self._delay_until = time.monotonic() + POST_TEMP_DELAY_SEC
        self._state = CheckupState.TEMP_DELAY

    # ------------------------------------------------------------------
    # Heart branch steps
    # ------------------------------------------------------------------

    def _position_for_heart(self) -> None:
        """
        Move the arm so the pulse sensor faces the patient's hand.

        NOTE: Same placeholder note as _position_for_temperature — full
        camera-guided alignment + endpoint calculation for the hand target
        is not yet implemented; this uses checkup_position() for now.
        """
        if self.arm is None:
            self._fail("arm unavailable during heart positioning")
            return

        self.arm.checkup_position(mode="smooth", blocking=True)
        logging.info("Checkup: arm positioned for heart/SpO2 — starting heart scan")

        if self.vitals is None:
            self._fail("vitals unavailable during heart positioning")
            return

        self._last_heart_result = None
        self.vitals.request_heart()
        self._state = CheckupState.HEART_SCANNING

    def _advance_heart_scan(self) -> None:
        """
        Wait for VitalSensorsReader to finish its heart scan/confirm/sample
        cycle. Once a result arrives, check for abnormal values, publish the
        result, retract the arm, and finish the checkup.
        """
        result = self._last_heart_result
        if result is None:
            return

        bpm  = result.get("heart_pulse_bpm")
        spo2 = result.get("oxy_saturation_percent")

        alert = (
            bpm is None or spo2 is None
            or bpm < BPM_LOW or bpm > BPM_HIGH
            or spo2 < SPO2_LOW
        )

        self._emit("peripherals/checkup/result", {
            "type": "heart",
            "heart_pulse_bpm": bpm,
            "oxy_saturation_percent": spo2,
            "alert": alert,
        })

        if alert:
            logging.warning("Checkup: abnormal heart reading (BPM=%s, SpO2=%s%%)", bpm, spo2)
        else:
            logging.info("Checkup: heart reading BPM=%s, SpO2=%s%%", bpm, spo2)

        self._finish()

    # ------------------------------------------------------------------
    # Completion helpers
    # ------------------------------------------------------------------

    def _request_confirm(self, step: str) -> None:
        self._emit("voice/checkup/request_confirm", {"step": step})
        self._confirm_deadline = time.monotonic() + CONFIRM_TIMEOUT_SEC
        self._emit("peripherals/checkup/status", {"phase": f"awaiting_{step}_confirm"})

    def _finish(self) -> None:
        """Retract the arm and mark the checkup complete."""
        if self.arm is not None:
            self.arm.rest_position(mode="smooth")
        logging.info("Checkup: complete")
        self._emit("peripherals/checkup/status", {"phase": "done"})
        self._emit("peripherals/checkup/complete", {})
        self._state = CheckupState.DONE
        self._reset_for_next()

    def _fail(self, reason: str) -> None:
        """Retract the arm (best-effort) and mark the checkup failed."""
        logging.error("Checkup: failed — %s", reason)
        if self.arm is not None:
            try:
                self.arm.rest_position(mode="smooth")
            except Exception:
                logging.exception("Checkup: error retracting arm during failure handling")
        self._emit("peripherals/checkup/status", {"phase": "failed"})
        self._emit("peripherals/checkup/failed", {"reason": reason})
        self._state = CheckupState.FAILED
        self._reset_for_next()

    def _reset_for_next(self) -> None:
        """
        Return to IDLE so a new checkup can be requested.
        Called immediately after DONE/FAILED — those states exist mainly so
        the final status events are emitted with a clear phase, but there is
        no need to linger in them since update() no-ops for both anyway.
        """
        self._last_thermo_result = None
        self._last_heart_result = None
        self._state = CheckupState.IDLE

    def _emit(self, topic: str, data: Dict) -> None:
        if self.on_event:
            self.on_event(topic, data)