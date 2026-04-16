from RPLCD.i2c import CharLCD
import time

lcd = CharLCD('PCF8574', 0x27)  # change if needed

messages = [
    "Line 1: TEST",
    "Line 2: 1234567890",
    "I2C OK",
    "ESP/Pi READY",
    "FAST UPDATE",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "0123456789",
    "STABILITY CHECK"
]

lcd.clear()

i = 0

while True:
    lcd.clear()

    msg = messages[i % len(messages)]
    lcd.write_string(msg)

    # second line variation
    lcd.cursor_pos = (1, 0)
    lcd.write_string(f"IDX: {i}")

    i += 1
    time.sleep(0.5)  # fast refresh (tune this down to stress test more)
