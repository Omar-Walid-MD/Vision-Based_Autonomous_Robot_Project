"""
config.py - Configuration dataclasses for the Peripherals Node.
"""

from dataclasses import dataclass


@dataclass
class ServoConfig:
    channel: int
    min_angle: int
    max_angle: int
    default_angle: int


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
    thermometer_address: int = 0x5A  # MLX90614
    heart_sensor_address: int = 0x57  # MAX30102 / MAX30105 common address

    # Servo channels on PCA9685
    arm_base: ServoConfig = ServoConfig(channel=0, min_angle=0, max_angle=180, default_angle=90)
    arm_shoulder: ServoConfig = ServoConfig(channel=1, min_angle=15, max_angle=165, default_angle=90)
    arm_elbow: ServoConfig = ServoConfig(channel=2, min_angle=15, max_angle=165, default_angle=90)
    head_pan: ServoConfig = ServoConfig(channel=3, min_angle=0, max_angle=180, default_angle=90)
    head_tilt: ServoConfig = ServoConfig(channel=4, min_angle=40, max_angle=140, default_angle=90)

    # Node behavior
    publish_interval_sec: float = 1.0
