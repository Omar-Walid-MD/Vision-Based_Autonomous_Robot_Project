from panda3d.core import NodePath, DirectionalLight, AmbientLight, CardMaker, Vec3, Texture
from panda3d.core import (
    Geom, GeomNode, GeomTriangles,
    GeomVertexFormat, GeomVertexData,
    GeomVertexWriter, NodePath, TextNode
)

import random
import math
import os
import json

this_directory = os.path.dirname(os.path.abspath(__file__))


class Environment(NodePath):
    def __init__(self, scene, mapDir):

        NodePath.__init__(self,'env-root')

        scene.loader.loadModel(mapDir+"/map.obj").reparentTo(self)
        self.reparentTo(scene.render)
        
        self.setPos(0,0,0)
        self.setHpr(0,90,0)
        
        if scene.show:
            # set up camera and lighting
            base.cam.setHpr(0, -90, 0)
            
            dlight = DirectionalLight("light")
            scene.render.setLight(scene.render.attachNewNode(dlight))
            dlight.setPoint((2,28,100))
            dlight.setDirection((0,0.5,-1))
            dlight.setColor((0.25,0.25,0.5,1))
            
            alight = AmbientLight("ambient")
            alight.setColor((0.3, 0.3, 0.3, 1))
            alnp = scene.render.attachNewNode(alight)
            scene.render.setLight(alnp)
            
            # load zones
            zones = scene.zones.values() # convert dict to list for iteration
            for zone in zones:
                Zone(scene, zone)
                
            # load april tags
            for tag in scene.tags:
                tag["object"] = Tag(scene,tag)


TAG_HEIGHT = 1.5

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
    
    # calculate robot position from detection offset   
    def locate(self,offset,rotation):
        angle = rotation[1]
        rad_angle = math.radians(angle)
        
        pos = [0,0]
        pos[0] = offset[0]*math.cos(rad_angle) - offset[2]*math.sin(rad_angle)
        pos[1] = offset[0]*math.sin(rad_angle) + offset[2]*math.cos(rad_angle)

        self.pointer.setPos(pos[0],-pos[1],offset[1])
        self.pointer.setHpr(angle,0,0)
        pass

# class for showing named zones
class Zone(NodePath):
    def __init__(self, scene, zone_data):
        NodePath.__init__(self, f"zone-{zone_data['name']}")
        self.reparentTo(scene.render)

        self.scene = scene
        self.name = zone_data["name"]
        self.vertices = zone_data["vertices_grid"]

        # Random bright color
        self.color = (
            random.uniform(0.5, 1.0),
            random.uniform(0.5, 1.0),
            random.uniform(0.5, 1.0),
            0.5
        )

        self._create_polygon()
        self._create_label()

    # -------------------------
    # Create filled polygon
    # -------------------------
    def _create_polygon(self):
        format = GeomVertexFormat.getV3()
        vdata = GeomVertexData("zone", format, Geom.UHStatic)

        vertex = GeomVertexWriter(vdata, "vertex")

        # Convert grid → world
        scaled_vertices = []
        for x, y in self.vertices:
            wx = x * self.scene.cellSize
            wy = y * self.scene.cellSize
            scaled_vertices.append((wx, -wy))
            vertex.addData3(wx, -wy, 0)

        # Triangulation (fan)
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(1, len(scaled_vertices) - 1):
            tris.addVertices(0, i, i + 1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)

        node = GeomNode(f"zone-geom-{self.name}")
        node.addGeom(geom)

        self.geom_np = self.attachNewNode(node)

        # Appearance
        self.geom_np.setTwoSided(True)
        self.geom_np.setRenderModeFilled()
        self.geom_np.setColor(*self.color)
        self.geom_np.setTransparency(True)
        self.geom_np.setLightOff()
        self.geom_np.setZ(0.01)  # avoid z-fighting

    # -------------------------
    # Create floating label
    # -------------------------
    def _create_label(self):
        cx, cy = self._compute_center()

        text = TextNode(f"zone-label-{self.name}")
        text.setText(self.name)
        text.setAlign(TextNode.ACenter)

        self.label_np = self.attachNewNode(text)
        self.label_np.setScale(1)
        self.label_np.setPos(cx, cy,0.1)
        self.label_np.setBillboardPointEye()
        self.label_np.setLightOff()

    # -------------------------
    # Compute center of polygon
    # -------------------------
    def _compute_center(self):
        x = sum(v[0] for v in self.vertices) / len(self.vertices)
        y = sum(v[1] for v in self.vertices) / len(self.vertices)

        return ((x+0.5) * self.scene.cellSize, -(y+0.5) * self.scene.cellSize)

    # -------------------------
    # Optional: highlight zone
    # -------------------------
    def set_highlight(self, enabled=True):
        if enabled:
            self.geom_np.setColor(1, 1, 0, 0.7)  # yellow highlight
        else:
            self.geom_np.setColor(*self.color)