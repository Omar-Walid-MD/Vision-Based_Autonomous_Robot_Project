import smbus
import time

MLX90614_ADDR   = 0x5A

REG_TA    = 0x06
REG_OBJ1  = 0x07 

bus = smbus.SMBus(1)

def read_temp(register):
    raw = bus.read_word_data(MLX90614_ADDR, register)
    temp = (raw * 0.02) - 273.15
    return temp

try:
    while True:
        ambient = read_temp(REG_TA)
        obj = read_temp(REG_OBJ1)
        print(f"Ambient Temp: {ambient:.2f} C")
        print(f"Object Temp: {obj:.2f} C")
        print("----------------------")
        time.sleep(1)
        
except KeyboardInterrupt:
    print("Stopped by User")