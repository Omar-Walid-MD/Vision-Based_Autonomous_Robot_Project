from panda3d.core import NodePath

class Robot(NodePath):
    def __init__(self, parent):

        NodePath.__init__(self,'robot-root')

        parent.loader.loadModel("./models/robot.obj").reparentTo(self)
        self.reparentTo(parent.render)
        print(self.parent)
        
        self.setPos(2,2,0)
        self.setHpr(-90,0,0)
        self.setScale(0.75,0.75,0.75)