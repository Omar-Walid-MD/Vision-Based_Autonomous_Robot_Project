from panda3d.core import CardMaker, Vec3
import math

# class for displaying and marking April Tags in the simulation
class Tag:
    def __init__(self,scene,id,pos,angle):
        
        self.id = id
        
        size = 0.5
        cm = CardMaker("quad")
        cm.setFrame(-size, size, -size, size)   # (left, right, bottom, top)
        self.quad = scene.render.attachNewNode(cm.generate())

        # --- Position and rotation ---
        dir = [math.sin(math.radians(180-angle))*0.499,math.cos(math.radians(180-angle))*0.499]
        pos[0] = (pos[0] - dir[0]) * scene.cellSize
        pos[1] = (-pos[1] - dir[1]) * scene.cellSize
        self.quad.setPos(pos[0],pos[1],1) 
        self.quad.setHpr(angle, 0, 0)

        # --- Load texture ---
        tex = scene.loader.loadTexture(f"textures/Tag {self.id}.png")
        self.quad.setTexture(tex)
        self.quad.setLightOff()     # ignore scene lights
        self.quad.setColor(1, 1, 1, 1)  # ensure no tinting (R,G,B,A)
        
        self.pointer = scene.loader.loadModel("./models/box.obj")
        self.pointer.reparentTo(self.quad)
        self.pointer.setLightOff()
        self.pointer.setColor((1,0,1,1))
        
    def locate(self,offset):
        self.pointer.setPos(offset[0],offset[1],offset[2])
        pass
        