"""
screen_controller.py - ScreenController for the Peripherals Node.
"""

import logging

from config import PeripheralsConfig
from servo_driver import load_hardware_libraries, CharLCD

import os
env = os.environ.copy()
platform = os.getenv("PLATFORM")



class ScreenController:
    """Controls 2x16 I2C LCD screen."""

    def __init__(self, config: PeripheralsConfig, mock: bool = False):
        self.config = config
        self.mock = platform != "RPI" or mock
        self.current_text = ""
        self.lcd = None

        if not self.mock:
            if CharLCD is None:
                load_hardware_libraries()
            if CharLCD is None:
                raise RuntimeError(
                    "RPLCD library not installed. Install with: pip install RPLCD"
                )
            self.lcd = CharLCD(
                i2c_expander="PCF8574",
                address=self.config.lcd_address,
                port=1,
                cols=self.config.lcd_cols,
                rows=self.config.lcd_rows,
                dotsize=8,
            )

    def write_text(self, text: str) -> str:
        self.current_text = text[: self.config.lcd_cols * self.config.lcd_rows]
        line1 = self.current_text[: self.config.lcd_cols]
        line2 = self.current_text[self.config.lcd_cols : self.config.lcd_cols * 2]

        if self.mock:
            logging.info("[MOCK LCD]\n%-16s\n%-16s", line1, line2)
        else:
            self.lcd.clear()
            self.lcd.write_string(line1)
            if line2:
                self.lcd.crlf()
                self.lcd.write_string(line2)

        return self.current_text

    def clear(self) -> None:
        self.current_text = ""
        if self.mock:
            logging.info("[MOCK LCD] cleared")
        else:
            self.lcd.clear()
