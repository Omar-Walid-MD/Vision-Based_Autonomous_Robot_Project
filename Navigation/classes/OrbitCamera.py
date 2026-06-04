from direct.showbase.DirectObject import DirectObject
from panda3d.core import Vec3, MouseButton
import math

class OrbitCamera(DirectObject):

    def __init__(self, base, target):

        self.base = base
        self.target = target

        # FULLY disable panda default camera
        base.disableMouse()

        # orbit state
        self.distance = 20
        self.heading = 0
        self.pitch = 80

        self.offset = Vec3(0, 0, 0)

        # mouse state
        self.rotating = False
        self.last_mouse = None

        # events
        self.accept("wheel_up", self.zoom_in)
        self.accept("wheel_down", self.zoom_out)

        self.accept("0", self.reset_view)

        base.taskMgr.add(self.update, "orbit_camera")


    # -------------------------

    def zoom_in(self):
        self.distance *= 0.9

    def zoom_out(self):
        self.distance *= 1.1

    # -------------------------

    def reset_view(self):
        self.distance = 20
        self.heading = 0
        self.pitch = 90
        self.offset = Vec3(0, 0, 0)

    # -------------------------

    def update(self, task):

        mw = self.base.mouseWatcherNode

        if mw.hasMouse():

            mouse = mw.getMouse()

            if self.last_mouse is not None:

                dx = mouse.x - self.last_mouse[0]
                dy = mouse.y - self.last_mouse[1]

                # LEFT MOUSE = orbit
                if mw.is_button_down(MouseButton.one()):

                    self.heading += dx * 100
                    self.pitch -= dy * 100

                    self.pitch = min(89, max(10, self.pitch))

                # RIGHT MOUSE = pan
                if mw.is_button_down(MouseButton.three()):

                    pan_speed = self.distance * 0.002

                    quat = self.base.cam.getQuat()

                    right = quat.getRight()
                    up = quat.getUp()

                    self.offset -= right * dx * pan_speed * 100
                    self.offset -= up * dy * pan_speed * 100

            self.last_mouse = (mouse.x, mouse.y)
        else:
            self.last_mouse = None

        # orbit math
        target_pos = self.target.getPos() + self.offset

        h = math.radians(self.heading)
        p = math.radians(self.pitch)

        x = self.distance * math.cos(p) * math.sin(h)
        y = self.distance * math.cos(p) * math.cos(h)
        z = self.distance * math.sin(p)

        cam_pos = target_pos + Vec3(x, y, z)
        
        self.base.cam.setPos(cam_pos)
        self.base.cam.lookAt(target_pos,Vec3(0,0,1))
        
        

        return task.cont