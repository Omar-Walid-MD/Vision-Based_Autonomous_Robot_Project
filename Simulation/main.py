from direct.showbase.ShowBase import ShowBase
from panda3d.core import loadPrcFileData, DirectionalLight, AmbientLight

confVars = """
win-size 1280 720
window-title My App
show-frame-rate-meter True
model-cache-dir
"""
loadPrcFileData("",confVars)
class MyApp(ShowBase):
    def __init__(self):
        super().__init__()
        
        self.disableMouse()
        env = self.loader.loadModel("./model.obj")
        env.reparentTo(self.render)
        env.setPos(0,16,0)
        env.setHpr(0,90,0)
        
        robot = self.loader.loadModel("./robot.obj")
        robot.reparentTo(self.render)
        robot.setPos(2,2,0)
        
        base.cam.setPos(8,8,40)
        base.cam.setHpr(90, -90, 0)   # (Heading, Pitch, Roll) in degrees
        
        dlight = DirectionalLight("light")
        self.render.setLight(self.render.attachNewNode(dlight))
        dlight.setPoint((2,28,100))
        dlight.setDirection((0,0.5,-1))
        dlight.setColor((0.25,0.25,0.5,1))  # light gray
        
        alight = AmbientLight("ambient")
        alight.setColor((0.3, 0.3, 0.3, 1))  # light gray
        alnp = self.render.attachNewNode(alight)
        self.render.setLight(alnp)

        
        self.taskMgr.add(self.update,"update")
        
    def update(self, task):
        
        return task.cont
                

app = MyApp()
app.run()
