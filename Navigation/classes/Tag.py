from panda3d.core import CardMaker, Vec3, Texture, TransformState, Mat3
import math

TAG_HEIGHT = 1.5

# helper functions

def make_transform(pos, hpr):
    return TransformState.makePosHpr(Vec3(*pos), Vec3(*hpr))


# class for displaying and marking April Tags in the simulation
class Tag:
    def __init__(self,scene,tag):
        
        id = tag["id"]
        pos = tag["pos_meter"]
        angle = tag["angle"]
        
        self.id = id
        
        size = 0.5
        cm = CardMaker("quad")
        cm.setFrame(-size, size, -size, size)   # (left, right, bottom, top)
        self.quad = scene.render.attachNewNode(cm.generate())

        self.angle = angle+90
        self.quad.setPos(pos[0],-pos[1],TAG_HEIGHT) 
        self.quad.setHpr(self.angle, 0, 0)
        self.quad.setY(self.quad,-0.01) # move out of walls

        # --- Load texture ---
        idString = ("00000"+self.id)[-5:]
        tex = scene.loader.loadTexture(f"textures/tags/tag36_11_{(idString)}.png")
        tex.setMinfilter(Texture.FTNearest)
        tex.setMagfilter(Texture.FTNearest)

        tex.setFormat(Texture.F_rgba)   # force linear format (no sRGB)
        self.quad.setTexture(tex)
        self.quad.setLightOff()     # ignore scene lights
        self.quad.setColor(1, 1, 1, 1)  # ensure no tinting (R,G,B,A)
        
        self.pointer = scene.loader.loadModel("models/misc/sphere")
        self.pointer.setScale(0.1)
        self.pointer.reparentTo(self.quad)
        self.pointer.setLightOff()
        self.pointer.setColor((1,0,1,1))
        self.pointer.setTextureOff(1)
    
    def locate_robot(
        self,
        offset, rotation,              # AprilTag output
        cam_pos_head, cam_tilt,        # camera relative to head
        head_pos_robot, head_pan       # head relative to robot
    ):
        # 1. Tag in world
        T_world_tag = self.quad.getTransform()

        # 2. Tag in camera (from detection)
        converted_offset = (
            offset[0],
<<<<<<< HEAD
            -offset[2],
=======
            offset[2],
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
            offset[1]
        )

        converted_rotation = (
<<<<<<< HEAD
            rotation[2],
            rotation[1],
            rotation[0]
=======
            -rotation[2],
            rotation[0],
            -rotation[1]
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
        )

        T_camera_tag = make_transform(
            converted_offset,
            converted_rotation
        )

        # Invert → camera in tag
        T_tag_camera = T_camera_tag.invertCompose(TransformState.makeIdentity())

        # 3. Camera in head (tilt = pitch)
        T_head_camera = make_transform(
            cam_pos_head,
            (0, cam_tilt, 0)   # (H, P, R)
        )

        # 4. Head in robot (pan = yaw)
        T_robot_head = make_transform(
            head_pos_robot,
            (head_pan, 0, 0)
        )

        # 5. Chain transforms
        T_world_robot = (
            T_world_tag
            .compose(T_tag_camera)
            .compose(T_head_camera)
            .compose(T_robot_head)
        )

        pos = T_world_robot.getPos()
        hpr = T_world_robot.getHpr()
        
<<<<<<< HEAD
        hpr[0] -= 90

        return pos, hpr
=======
        hpr[0] += 90

        return pos, hpr
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
