from panda3d.core import NodePath, DirectionalLight, AmbientLight

class Environment(NodePath):
    def __init__(self, parent):

        NodePath.__init__(self,'env-root')

        parent.loader.loadModel("./models/model.obj").reparentTo(self)
        self.reparentTo(parent.render)
        
        self.setPos(0,0,0)
        self.setHpr(0,90,0)
        
        if parent.show:
            # set up camera and lighting
            base.cam.setHpr(0, -90, 0)
            
            dlight = DirectionalLight("light")
            parent.render.setLight(parent.render.attachNewNode(dlight))
            dlight.setPoint((2,28,100))
            dlight.setDirection((0,0.5,-1))
            dlight.setColor((0.25,0.25,0.5,1))
            
            alight = AmbientLight("ambient")
            alight.setColor((0.3, 0.3, 0.3, 1))
            alnp = parent.render.attachNewNode(alight)
            parent.render.setLight(alnp)