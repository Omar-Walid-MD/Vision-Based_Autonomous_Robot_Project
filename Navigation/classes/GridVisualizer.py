from panda3d.core import CardMaker, TransparencyAttrib, NodePath, Texture
from PIL import Image, ImageDraw

# class for visualizing grid 
class GridVisualizer(NodePath):
    def __init__(self, scene):
        NodePath.__init__(self, "grid")
        self.reparentTo(scene.render)

        self.scene = scene
        self.grid = scene.grid
        self.width = len(self.grid[0])
        self.height = len(self.grid)
        self.cell_size = scene.cellSize
        
        self.pathOverlay = PathOverlay(scene)

        self.create_grid_plane()
    
  
    def create_grid_texture(self, grid, cell_px=20):
        
        height = len(grid)
        width = len(grid[0])

        min_x, min_y = width, height
        max_x, max_y = 0, 0
        
        for y in range(height):
            for x in range(width):
                if grid[y][x] != 1:  # adjust condition if needed
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)


        width = max_x - min_x + 1
        height = max_y - min_y + 1

        img_w = width * cell_px
        img_h = height * cell_px

        img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        for gy in range(min_y, max_y + 1):
            for gx in range(min_x, max_x + 1):
                val = grid[gy][gx]

                px = (gx - min_x) * cell_px
                py = (gy - min_y) * cell_px

                # flip Y
                py = img_h - py - cell_px

                if val == 1:
                    color = (0, 0, 0, 0)  # fully transparent
                else:
                    color = (0, 0, 0, 80)  # walkable

                draw.rectangle(
                    [px, py, px + cell_px, py + cell_px],
                    fill=color,
                    outline=(0, 0, 0, 100)
                )

        tex = Texture()
        tex.setup2dTexture(img_w, img_h, Texture.T_unsigned_byte, Texture.F_rgba)
        tex.setRamImage(img.tobytes())

        return tex, width, height, min_x, min_y

    
    def create_grid_plane(self):
        
        texture, width, height, min_x, min_y = self.create_grid_texture(self.grid)

        cm = CardMaker("grid")
        cm.setFrame(0, width * self.cell_size, 0, height * self.cell_size)

        grid_np = self.scene.render.attachNewNode(cm.generate())
        grid_np.setP(-90)
        grid_np.setPos(min_x * self.cell_size,-(height+min_y) * self.cell_size,0.02)

        grid_np.setTexture(texture)
        grid_np.setTransparency(TransparencyAttrib.M_alpha)
        grid_np.setLightOff()

        return grid_np
                            
# class for visualizing pathfinding points
class PathOverlay:
    def __init__(self, scene):
        self.scene = scene
        self.cell_size = scene.cellSize
        self.nodes = []

    def show_path(self, path):
        self.clear()

        cm = CardMaker("path")
        cm.setFrame(0, self.cell_size, 0, self.cell_size)

        for i, (x, y) in enumerate(path):
            node = self.scene.render.attachNewNode(cm.generate())
            node.setP(-90)
            node.setPos(x * self.cell_size, -(y+1) * self.cell_size, 0.05)

            if i == 0:
                node.setColor(0, 1, 0, 0.9)  # start
            elif i == len(path) - 1:
                node.setColor(1, 0, 0, 0.9)  # end
            else:
                node.setColor(0, 0, 1, 0.6)  # path

            node.setTransparency(True)
            node.setLightOff()

            self.nodes.append(node)

    def clear(self):
        for n in self.nodes:
            n.removeNode()
        self.nodes.clear()