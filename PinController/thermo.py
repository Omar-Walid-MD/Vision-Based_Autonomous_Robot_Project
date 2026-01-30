from smbus2 import SMBus, i2c_msg
import time

MLX90614_ADDR = 0x5A
REG_TA = 0x06
REG_OBJ1 = 0x07

def read_temp(bus, reg):
    # Write register
    write = i2c_msg.write(MLX90614_ADDR, [reg])
    read = i2c_msg.read(MLX90614_ADDR, 3)  # LSB, MSB, PEC
    bus.i2c_rdwr(write, read)

    data = list(read)
    raw = data[0] | (data[1] << 8)
    return (raw * 0.02) - 273.15

with SMBus(1) as bus:
    try:
        while True:
            print(f"Ambient: {read_temp(bus, REG_TA):.2f} C")
            print(f"Object:  {read_temp(bus, REG_OBJ1):.2f} C")
            print("----------------------")
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
