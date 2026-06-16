"""
vital_sensors.py - VitalSensorsReader for the Peripherals Node.

Each sensor has a single update() method that advances its state machine
by one step and returns immediately. The main loop calls
vitals.update() every tick — no sensor threads, no blocking.

State machine (per sensor):
  IDLE       → not polled; waiting for request_thermo() / request_heart()
  SCANNING   → polling raw values; waiting for contact threshold
  CONFIRMING → threshold crossed; waiting CONTACT_CONFIRM_DURATION of sustained contact
  SAMPLING   → collecting data for SAMPLE_DURATION seconds
  → publishes result via on_result callback → back to IDLE

FIFO note (MAX30102):
  The FIFO is cleared by zeroing the three pointer registers the moment a heart scan starts so
  that samples accumulated while the sensor was idle don't cause stale/zero
  reads. This is the root cause of the "returns 0 when started late" bug.

I2C conflict note:
  MLX90614 uses adafruit busio; MAX30102 uses smbus directly. They share
  the physical I2C bus. Thermo and heart updates must not be called in the
  same tick — the main loop alternates them.
"""

from __future__ import annotations

import logging
import math
import random
import time
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Union

from config import PeripheralsConfig
import servo_driver as _hw


# ------------------------------------------------------------------
# Tuneable constants
# ------------------------------------------------------------------

THERMO_CONTACT_THRESHOLD: float = 30.0   # °C object temp → body present
HEART_CONTACT_THRESHOLD:  int   = 100_000 # IR counts → finger present

CONTACT_CONFIRM_DURATION: float = 0.2    # seconds threshold must be held
SAMPLE_DURATION:          float = 5.0    # seconds of data to collect
SCAN_INTERVAL:            float = 0.05   # seconds between update() ticks

HEART_SAMPLE_RATE: float = 25.0          # effective Hz (100 Hz / 4x avg)


# ------------------------------------------------------------------
# State
# ------------------------------------------------------------------

class SensorState(Enum):
    IDLE       = auto()
    SCANNING   = auto()
    CONFIRMING = auto()
    SAMPLING   = auto()


# ------------------------------------------------------------------
# VitalSensorsReader
# ------------------------------------------------------------------

class VitalSensorsReader:
    """
    Non-blocking vital sensor manager.

    Call update_thermo() and update_heart() from the main loop every tick.
    Each call does one unit of work (one raw read or one FIFO drain) and
    returns immediately — no threads, no blocking sleeps inside update().
    """

    def __init__(self, config: PeripheralsConfig, mock: bool = False):
        self.config = config
        self.mock   = mock
        self.thermo       = None
        self.heart_sensor = None

        # Last published values
        self.temperature:      Optional[float] = None
        self.room_temperature: Optional[float] = None
        self.heart_pulse:      Optional[int]   = None
        self.oxy_saturation:   Optional[int]   = None

        # Sensor states
        self._thermo_state: SensorState = SensorState.IDLE
        self._heart_state:  SensorState = SensorState.IDLE

        # Contact confirmation timing
        self._thermo_contact_since: Optional[float] = None
        self._heart_contact_since:  Optional[float] = None

        # Sample accumulation
        self._thermo_body_buf: List[float] = []
        self._thermo_room_buf: List[float] = []
        self._heart_red_buf:   List[int]   = []
        self._heart_ir_buf:    List[int]   = []
        self._sample_start:    float       = 0.0

        # Callback: on_result(topic, data)
        self.on_result: Optional[Callable[[str, Dict], None]] = None

        if not self.mock:
            _hw.load_hardware_libraries()
            i2c = _hw.busio.I2C(_hw.board.SCL, _hw.board.SDA)
            self.thermo = _hw.MLX90614(i2c, address=self.config.thermometer_address)

            if _hw.MAX30102 is not None:
                time.sleep(0.1)
                self.heart_sensor = _hw.MAX30102(
                    channel=1,
                    address=self.config.heart_sensor_address,
                )
            else:
                logging.warning(
                    "MAX30102 could not be imported from max30102/max30102.py. "
                    "Heart/SpO2 readings will be unavailable."
                )

    # ------------------------------------------------------------------
    # Request API  (called by topic event handlers — just sets a flag)
    # ------------------------------------------------------------------

    def request_thermo(self) -> None:
        """Ask for a thermo reading cycle. Ignored if one is already active."""
        if self._thermo_state != SensorState.IDLE:
            logging.debug("Thermo already active, ignoring request.")
            return
        logging.info("Thermo: requested — will start SCANNING on next tick")
        self._thermo_state         = SensorState.SCANNING
        self._thermo_contact_since = None

    def request_heart(self) -> None:
        """Ask for a heart reading cycle. Ignored if one is already active."""
        if self._heart_state != SensorState.IDLE:
            logging.debug("Heart already active, ignoring request.")
            return
        logging.info("Heart: requested — clearing FIFO and starting SCANNING on next tick")
        # Reset and reconfigure the sensor to get it into a clean known state.
        # This is the same sequence __init__ runs: reset() wipes all registers,
        # the 1s sleep lets the hardware stabilise, then setup() reconfigures
        # sample rate / LED current / FIFO settings from scratch.
        # This is more reliable than zeroing FIFO pointers alone because a
        # full reset also clears the overflow counter and interrupt flags.
        if not self.mock and self.heart_sensor is not None:
            try:
                logging.info("Heart: resetting sensor before scan")
                self.heart_sensor.reset()
                time.sleep(1)
                self.heart_sensor.setup()
                logging.debug("Heart: sensor reset and reconfigured")
            except OSError as exc:
                logging.warning("Heart: sensor reset failed: %s", exc)
        self._heart_state         = SensorState.SCANNING
        self._heart_contact_since = None

    # ------------------------------------------------------------------
    # Update methods  (called from the main loop every tick)
    # ------------------------------------------------------------------

    def update_thermo(self) -> None:
        """Advance the thermo state machine by one step. Returns immediately."""
        state = self._thermo_state

        if state == SensorState.IDLE:
            return

        if state == SensorState.SCANNING:
            raw = self._raw_thermo()
            logging.debug("Thermo SCANNING: %.2f°C", raw)
            if raw > THERMO_CONTACT_THRESHOLD:
                self._thermo_contact_since = time.monotonic()
                self._thermo_state = SensorState.CONFIRMING
                logging.debug("Thermo: threshold crossed, entering CONFIRMING")
            return

        if state == SensorState.CONFIRMING:
            raw = self._raw_thermo()
            logging.debug("Thermo CONFIRMING: %.2f°C", raw)
            if raw <= THERMO_CONTACT_THRESHOLD:
                logging.debug("Thermo: contact lost, back to SCANNING")
                self._thermo_contact_since = None
                self._thermo_state = SensorState.SCANNING
                return
            elapsed = time.monotonic() - self._thermo_contact_since
            if elapsed >= CONTACT_CONFIRM_DURATION:
                print("[Thermo] Contact detected.")
                logging.info("Thermo: contact confirmed — entering SAMPLING")
                self._thermo_body_buf = []
                self._thermo_room_buf = []
                self._sample_start    = time.monotonic()
                self._thermo_state    = SensorState.SAMPLING
            return

        if state == SensorState.SAMPLING:
            # Collect one reading per tick until SAMPLE_DURATION expires.
            try:
                self._thermo_body_buf.append(float(self.thermo.object_temperature)
                                             if not self.mock
                                             else random.uniform(36.4, 37.2))
                self._thermo_room_buf.append(float(self.thermo.ambient_temperature)
                                             if not self.mock
                                             else random.uniform(24.0, 27.0))
            except OSError as exc:
                logging.warning("Thermo sample read error: %s", exc)

            if time.monotonic() - self._sample_start >= SAMPLE_DURATION:
                self._finish_thermo()
            return

    def update_heart(self) -> None:
        """Advance the heart state machine by one step. Returns immediately."""
        state = self._heart_state

        if state == SensorState.IDLE:
            return

        if state == SensorState.SCANNING:
            ir = self._raw_ir_nowait()
            logging.debug("Heart SCANNING IR: %d", ir)
            if ir > HEART_CONTACT_THRESHOLD:
                self._heart_contact_since = time.monotonic()
                self._heart_state = SensorState.CONFIRMING
                logging.debug("Heart: threshold crossed, entering CONFIRMING")
            return

        if state == SensorState.CONFIRMING:
            ir = self._raw_ir_nowait()
            logging.debug("Heart CONFIRMING IR: %d", ir)
            if ir <= HEART_CONTACT_THRESHOLD:
                logging.debug("Heart: contact lost, back to SCANNING")
                self._heart_contact_since = None
                self._heart_state = SensorState.SCANNING
                return
            elapsed = time.monotonic() - self._heart_contact_since
            if elapsed >= CONTACT_CONFIRM_DURATION:
                print("[Heart] Contact detected.")
                logging.info("Heart: contact confirmed — entering SAMPLING")
                self._heart_red_buf = []
                self._heart_ir_buf  = []
                self._sample_start  = time.monotonic()
                self._heart_state   = SensorState.SAMPLING
            return

        if state == SensorState.SAMPLING:
            # Drain whatever is in the FIFO right now (non-blocking).
            self._drain_fifo_once()
            if time.monotonic() - self._sample_start >= SAMPLE_DURATION:
                self._finish_heart()
            return

    # ------------------------------------------------------------------
    # Finish helpers
    # ------------------------------------------------------------------

    def _finish_thermo(self) -> None:
        body = (round(sum(self._thermo_body_buf) / len(self._thermo_body_buf), 1)
                if self._thermo_body_buf else None)
        room = (round(sum(self._thermo_room_buf) / len(self._thermo_room_buf), 1)
                if self._thermo_room_buf else None)
        self.temperature      = body
        self.room_temperature = room
        result = {"body_temperature_c": body, "room_temperature_c": room}
        logging.info("Thermo result: body=%.1f°C  room=%.1f°C", body or 0, room or 0)
        if self.on_result:
            self.on_result("peripherals/vitals/thermo", result)
        self._thermo_state = SensorState.IDLE
        logging.info("Thermo: back to IDLE")

    def _finish_heart(self) -> None:
        ir_buf  = self._heart_ir_buf
        red_buf = self._heart_red_buf
        if len(ir_buf) < 10:
            logging.warning("Heart: only %d samples — too few to compute", len(ir_buf))
            bpm  = None
            spo2 = None
        else:
            bpm  = self.estimate_pulse(ir_buf)
            spo2 = self.estimate_spo2(red_buf, ir_buf)
        self.heart_pulse    = bpm
        self.oxy_saturation = spo2
        result = {"heart_pulse_bpm": bpm, "oxy_saturation_percent": spo2}
        logging.info("Heart result: BPM=%s  SpO2=%s%%", bpm, spo2)
        if self.on_result:
            self.on_result("peripherals/vitals/heart", result)
        self._heart_state = SensorState.IDLE
        logging.info("Heart: back to IDLE")

    # ------------------------------------------------------------------
    # Raw read helpers  (no blocking sleeps)
    # ------------------------------------------------------------------

    def _raw_thermo(self) -> float:
        if self.mock:
            return round(random.uniform(28.0, 38.0), 2)
        try:
            return float(self.thermo.object_temperature)
        except OSError as exc:
            logging.warning("Thermo raw read error: %s", exc)
            return 0.0

    def _raw_ir_nowait(self) -> int:
        """
        Return the latest IR value from the FIFO without waiting.
        If the FIFO is empty right now, returns the last known value (or 0).
        The FIFO was cleared on request_heart() so 0 genuinely means no signal.
        """
        if self.mock:
            return random.randint(80_000, 160_000)
        if self.heart_sensor is None:
            return 0
        try:
            n = self.heart_sensor.get_data_present()
            ir = 0
            while n > 0:
                _, ir = self.heart_sensor.read_fifo()
                n -= 1
            return ir
        except OSError as exc:
            logging.warning("Heart raw IR read error: %s", exc)
            return 0

    def _drain_fifo_once(self) -> None:
        """Drain all currently available FIFO samples into the sample buffers."""
        if self.mock:
            self._heart_red_buf.append(random.randint(50_000, 150_000))
            self._heart_ir_buf.append(random.randint(100_000, 200_000))
            return
        if self.heart_sensor is None:
            return
        try:
            n = self.heart_sensor.get_data_present()
            while n > 0:
                red, ir = self.heart_sensor.read_fifo()
                self._heart_red_buf.append(red)
                self._heart_ir_buf.append(ir)
                n -= 1
        except OSError as exc:
            logging.warning("Heart FIFO drain error: %s", exc)

    # ------------------------------------------------------------------
    # Signal processing
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_pulse(ir_samples: List[int]) -> Optional[int]:
        n = len(ir_samples)
        if n < 10:
            logging.warning("BPM: too few samples (%d)", n)
            return None

        mean      = sum(ir_samples) / n
        ir_min    = min(ir_samples)
        ir_max    = max(ir_samples)
        ir_range  = ir_max - ir_min

        # Log signal diagnostics so threshold issues are visible in the log.
        logging.info(
            "BPM signal: samples=%d  mean=%d  min=%d  max=%d  range=%d",
            n, int(mean), ir_min, ir_max, ir_range,
        )

        # If the signal range is tiny, the finger is not making good contact
        # or the LED power is too low — no pulsatile component to detect.
        if ir_range < mean * 0.001:   # less than 0.1% modulation
            logging.warning(
                "BPM: signal range too flat (range=%d, mean=%d) — "
                "check finger placement or increase LED current", ir_range, int(mean)
            )
            return None

        # Adaptive threshold: midpoint between mean and max.
        # More robust than a fixed 2% offset when signal amplitude varies.
        threshold = (mean + ir_max) / 2.0

        peaks, in_peak = 0, False
        for val in ir_samples:
            if val > threshold and not in_peak:
                peaks += 1
                in_peak = True
            elif val <= threshold:
                in_peak = False

        logging.info("BPM: threshold=%.0f  peaks_detected=%d", threshold, peaks)

        if peaks == 0:
            logging.warning("BPM: no peaks found above threshold %.0f", threshold)
            return None

        bpm = int(round((peaks / (n / HEART_SAMPLE_RATE)) * 60))
        logging.info("BPM: raw computed = %d", bpm)

        if bpm < 30 or bpm > 220:
            logging.warning("BPM: %d out of physiological range, discarding", bpm)
            return None
        return bpm

    @staticmethod
    def estimate_spo2(red_samples: List[int], ir_samples: List[int]) -> Optional[int]:
        if len(red_samples) < 10 or len(ir_samples) < 10:
            return None

        def ac_dc(s: List[int]):
            mean = sum(s) / len(s)
            std  = math.sqrt(sum((x - mean) ** 2 for x in s) / len(s))
            return std, mean

        ac_red, dc_red = ac_dc(red_samples)
        ac_ir,  dc_ir  = ac_dc(ir_samples)
        if dc_red == 0 or dc_ir == 0 or ac_ir == 0:
            return None
        R = (ac_red / dc_red) / (ac_ir / dc_ir)
        return max(70, min(100, int(round(110.0 - 25.0 * R))))

    # ------------------------------------------------------------------
    # Debug loop  (--debug-vitals, runs standalone)
    # ------------------------------------------------------------------

    def debug_loop(self) -> None:
        """Tight loop printing raw sensor values for debugging. Ctrl+C to stop."""
        print("=== Vital Sensors Debug ===")
        print("Printing raw values every tick. Ctrl+C to stop.\n")
        i = 0
        while True:
            i += 1
            temp = self._raw_thermo()
            ir   = self._raw_ir_nowait()
            print(
                f"[#{i}]  Thermo: {temp:.2f}°C  |  "
                f"IR: {ir}  ({'CONTACT' if ir > HEART_CONTACT_THRESHOLD else 'no contact'})"
            )
            time.sleep(SCAN_INTERVAL)
