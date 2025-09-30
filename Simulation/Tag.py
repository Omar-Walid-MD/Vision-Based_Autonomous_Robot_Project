from panda3d.core import CardMaker
import math

# class for displaying and marking April Tags in the simulation
class Tag:
    def __init__(self,scene,id,pos,angle):
        
        self.id = id
        
        size = 0.5
        cm = CardMaker("quad")
        cm.setFrame(-size, size, -size, size)   # (left, right, bottom, top)
        quad = scene.render.attachNewNode(cm.generate())

        # --- Position and rotation ---
        dir = [math.sin(math.radians(180-angle))*0.49,math.cos(math.radians(180-angle))*0.49]
        quad.setPos(pos[0]-(dir[0]),pos[1]-(dir[1]),1)   # move 5 units forward
        quad.setHpr(angle, 0, 0)    # yaw 45 degrees

        # --- Load texture ---
        tex = scene.loader.loadTexture(f"textures/Tag {self.id}.png")
        quad.setTexture(tex)
        quad.setLightOff()     # ignore scene lights
        quad.setColor(1, 1, 1, 1)  # ensure no tinting (R,G,B,A)
        