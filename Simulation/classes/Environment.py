from panda3d.core import NodePath

class Environment(NodePath):
    def __init__(self, parent):

        NodePath.__init__(self,'env-root')

        parent.loader.loadModel("./models/model.obj").reparentTo(self)
        self.reparentTo(parent.render)
        
        self.setPos(0,0,0)
        self.setHpr(0,90,0)