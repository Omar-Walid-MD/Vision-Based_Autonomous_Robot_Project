import pygame #pip install pygame
import serial #pip install pyserial
import time

pygame.init()
width = 500
height = 500
screen = pygame.display.set_mode(vsync=1,size=(width,height))
pygame.display.set_caption("Robot Remote Control")
clock = pygame.time.Clock()
labelFont = "calibri"

controls = {
    "KEYDOWN": {
        "w": "F",
        "a": "L",
        "s": "B",
        "d": "R",
        "m": "M",
        "n": "N"
    },
    "KEYUP": {
        "w": "0",
        "a": "0",
        "s": "0",
        "d": "0"
    }
}


running = True
connected = False

#Press C to re-connect if Bluetooth disconnected
def connect_blutooth():   
    global connected, bt
    try:
        #change COM to the Serial which your PC's Blutooth connects to
        bt = serial.Serial('COM7', 9600)
        time.sleep(2)
        connected = True
        print("Connected")
    except Exception as e:
        print(e)


def send_to_bluetooth(data):
    if connected:
        try:
            print(data)
            bt.write(str(data).encode())
        except Exception as e:
            print(e)


connect_blutooth()

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False
        
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
                break
            
            #Press C to re-connect if Bluetooth disconnected
            elif event.key == pygame.K_c:
                connect_blutooth()
                
            else:
                for key in controls["KEYDOWN"]:
                    if event.key == pygame.key.key_code(key):
                        send_to_bluetooth(controls["KEYDOWN"][key])
                    
        elif event.type == pygame.KEYUP:
            for key in controls["KEYUP"]:
                if event.key == pygame.key.key_code(key):
                    send_to_bluetooth(controls["KEYUP"][key])
       

    screen.fill("white")    
    
    clock.tick(30)
    pygame.display.update()
    