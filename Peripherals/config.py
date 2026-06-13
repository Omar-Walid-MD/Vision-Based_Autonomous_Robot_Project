"""
config.py - Configuration dataclasses for the Peripherals Node.
"""

from dataclasses import dataclass, field


@dataclass
class ServoConfig:
    channel: int
    min_angle: float
    max_angle: float
    default_angle: float
    min_pulse_us: float   # Pulse width in microseconds at 0°
    max_pulse_us: float   # Pulse width in microseconds at 180°
    step_size: float      # Degrees per step during smooth movement
    step_delay: float     # Seconds between steps during smooth movement


@dataclass
class PeripheralsConfig:
    # PCA9685 default I2C address is 0x40
    servo_driver_address: int = 0x40
    servo_frequency: int = 50

    # LCD backpack is commonly 0x27 or 0x3F
    lcd_address: int = 0x27
    lcd_cols: int = 16
    lcd_rows: int = 2

    # Medical sensors common addresses
    thermometer_address: int = 0x5A   # MLX90614
    heart_sensor_address: int = 0x57  # MAX30102 / MAX30105 common address

    # Servo channels on PCA9685
    # Pulse ranges and movement settings match the hardware used per joint.
    arm_base: ServoConfig = field(default_factory=lambda: ServoConfig(
        channel=0, min_angle=0, max_angle=160, default_angle=90,
        min_pulse_us=600, max_pulse_us=3000,   # MG995
        step_size=1, step_delay=0.05,
    ))
    arm_shoulder: ServoConfig = field(default_factory=lambda: ServoConfig(
        channel=1, min_angle=15, max_angle=150, default_angle=90,
        min_pulse_us=500, max_pulse_us=2500,   # MG996R
        step_size=2, step_delay=0.05,
    ))
    arm_elbow: ServoConfig = field(default_factory=lambda: ServoConfig(
        channel=2, min_angle=15, max_angle=165, default_angle=90,
        min_pulse_us=500, max_pulse_us=2500,   # SG90
        step_size=1, step_delay=0.005,
    ))
    head_pan: ServoConfig = field(default_factory=lambda: ServoConfig(
        channel=3, min_angle=0, max_angle=180, default_angle=90,
        min_pulse_us=500, max_pulse_us=2500,
        step_size=1, step_delay=0.01,
    ))
    head_tilt: ServoConfig = field(default_factory=lambda: ServoConfig(
        channel=4, min_angle=40, max_angle=140, default_angle=90,
        min_pulse_us=500, max_pulse_us=2500,
        step_size=1, step_delay=0.01,
    ))

    # Node behavior
    publish_interval_sec: float = 1.0