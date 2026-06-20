import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog, colorchooser
import math
import json

# --- إعدادات النافذة ---
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 750
DEFAULT_GRID_SIZE = 25
DEFAULT_SCALE = 100
NODE_RADIUS = 6
SNAP_DISTANCE = 5
EDGE_SNAP_DISTANCE = 5
STRAIGHT_TOLERANCE = 20
ZONE_CLOSE_DISTANCE = 15
DEFAULT_ZONE_COLOR = "#9be7ff"
ZONE_STIPPLE = "gray25"
ORIENTATION_MIN_DRAG = 8
ORIENTATION_DEFAULT_LENGTH = 55
DEFAULT_OBSTACLE_WIDTH = 60
DEFAULT_OBSTACLE_HEIGHT = 40
OBSTACLE_HEIGHT_3D = 0.8
OBSTACLE_COLOR = "#e67e22"
OBSTACLE_STIPPLE = "gray50"

class SaveLoadMapBuilder:
    def __init__(self, root):
        self.root = root
        self.root.title("Robot Map Builder: Save & Load Project")
        
        # --- البيانات ---
        self.grid_size = DEFAULT_GRID_SIZE
        self.nodes = []         
        self.walls = []         
        self.april_tags = []    
        self.zones = []
        self.orientations = []
        self.obstacles = []
        self.history = []       

        # حالات التحكم
        self.mode = "select" 
        self.snap_enabled = tk.BooleanVar(value=True)
        self.straight_enabled = tk.BooleanVar(value=True) 
        
        # متغيرات التشغيل
        self.current_draw_start = None
        self.temp_line = None
        self.temp_text = None 
        self.selected_node_idx = None
        self._selected_obstacle_idx = None
        self.selected_zone_idx = None
        self.pending_tag_wall = None
        self.zone_points = []
        self.pending_orientation = None
        self.next_zone_uid = 1

        self.setup_ui()

    def setup_ui(self):
        toolbar = tk.Frame(self.root, bg="#2c3e50", pady=8)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        btn_style = {"bg": "#34495e", "fg": "white", "bd": 1, "activebackground": "#5D6D7E"}
        
        # 1. Tools
        tk.Label(toolbar, text=" TOOLS ", bg="#2c3e50", fg="#bdc3c7", font=("bold")).pack(side=tk.LEFT)
        tk.Button(toolbar, text="✏️ Wall", command=lambda: self.set_mode("draw_wall"), **btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="🏷️ Tag", command=lambda: self.set_mode("place_tag"), **btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="🟩 Zone", command=lambda: self.set_mode("create_zone"), bg="#27ae60", fg="white", bd=1).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="🛏️ Orientation", command=lambda: self.set_mode("orientation"), bg="#16a085", fg="white", bd=1).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="🪑 Furniture", command=lambda: self.set_mode("place_furniture"), bg="#d35400", fg="white", bd=1).pack(side=tk.LEFT, padx=2)
        
        tk.Button(toolbar, text="✋ Edit", command=lambda: self.set_mode("select"), **btn_style).pack(side=tk.LEFT, padx=10)
        tk.Button(toolbar, text="🎨 Zone Color", command=self.change_selected_zone_color, bg="#1abc9c", fg="white", bd=1).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="❌ Del", command=lambda: self.set_mode("delete"), bg="#c0392b", fg="white").pack(side=tk.LEFT, padx=2)

        # 2. Measurements
        tk.Label(toolbar, text=" | ", bg="#2c3e50", fg="gray").pack(side=tk.LEFT, padx=5)
        
        self.scale_slider = tk.Scale(toolbar, from_=5, to=100, orient=tk.HORIZONTAL, command=self.update_grid_size, 
                         showvalue=1, length=200, bg="#2c3e50", fg="white", highlightthickness=0)
        self.scale_slider.set(DEFAULT_GRID_SIZE)
        self.scale_slider.pack(side=tk.LEFT, padx=2)


        # 3. Save / Load (الجزء الجديد)
        tk.Button(toolbar, text="📂 LOAD", command=self.load_project, bg="#e67e22", fg="white", font=("bold")).pack(side=tk.RIGHT, padx=5)
        tk.Button(toolbar, text="💾 SAVE", command=self.save_project, bg="#8e44ad", fg="white", font=("bold")).pack(side=tk.RIGHT, padx=5)
        
        # Undo
        tk.Button(toolbar, text="↩️ Undo", command=self.undo, bg="#f39c12", fg="black").pack(side=tk.RIGHT, padx=15)

        self.canvas = tk.Canvas(self.root, width=WINDOW_WIDTH, height=WINDOW_HEIGHT, bg="white", cursor="cross")
        self.canvas.pack()
        self.draw_grid_background()

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_hover) 
        self.canvas.bind("<Button-3>", self.finish_zone_shortcut)
        self.root.bind("<Return>", self.finish_zone_shortcut_key)
        self.root.bind("<Delete>", self.on_delete_key)
        self.root.bind("<Key-c>", self.on_change_zone_color_key)
        self.root.bind("<Key-C>", self.on_change_zone_color_key)
        self.root.bind("<Key-r>", self.on_rotate_obstacle_key)
        self.root.bind("<Key-R>", self.on_rotate_obstacle_key)
        self.root.bind("<Key-l>", self.on_rotate_obstacle_key_neg)
        self.root.bind("<Key-L>", self.on_rotate_obstacle_key_neg)
        self.root.bind("<Escape>", self.on_escape_key)
        self.canvas.focus_set()

        self.status = tk.Label(self.root, text="Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    # --- SAVE & LOAD SYSTEM (NEW) ---

    def save_project(self):
        self.canvas.delete("vis_grid")
        active_walls = [w for w in self.walls if w is not None]
        occupied_cells = set()
        
        # 1. Rasterize Walls
        for w in active_walls:
            p1 = self.nodes[w['start']]['pos']; p2 = self.nodes[w['end']]['pos']
            dist = int(math.hypot(p2[0]-p1[0], p2[1]-p1[1]))
            if dist == 0: continue
            for i in range(dist):
                t = i / dist
                curr_x = p1[0] + t * (p2[0] - p1[0]); curr_y = p1[1] + t * (p2[1] - p1[1])
                c = int(curr_x // self.grid_size); r = int(curr_y // self.grid_size)
                occupied_cells.add((r, c))

        # 2. Rasterize Furniture (Obstacles)
        for obs in self.obstacles:
            cx, cy = obs['pos']
            w, h = obs['width'], obs['height']
            
            # Simple bounding box without clipping
            min_c = int((cx - w/2) // self.grid_size)
            max_c = int((cx + w/2) // self.grid_size)
            min_r = int((cy - h/2) // self.grid_size)
            max_r = int((cy + h/2) // self.grid_size)
            
            for r in range(min_r, max_r + 1):
                for c in range(min_c, max_c + 1):
                    # Check intersection with rotated rect
                    cell_cx = (c + 0.5) * self.grid_size
                    cell_cy = (r + 0.5) * self.grid_size
                    if self.point_in_rotated_rect(cell_cx, cell_cy, cx, cy, w, h, obs.get('angle', 0)):
                        occupied_cells.add((r, c))

        # Full Canvas Grid (No Clipping)
        rows = WINDOW_HEIGHT // self.grid_size
        cols = WINDOW_WIDTH // self.grid_size
        matrix = [[1 for _ in range(cols)] for _ in range(rows)]
        for r, c in occupied_cells:
            if 0 <= r < rows and 0 <= c < cols: matrix[r][c] = 0 
            
        def compute_tag_angle(p1, p2, side):
            dx = p2[0] - p1[0]
            dy = -(p2[1] - p1[1])
            angle = math.atan2(dy, dx)
            if side == 1: angle += math.pi / 2
            else: angle -= math.pi / 2
            angle_deg = math.degrees(angle)
            angle_deg = (angle_deg + 360) % 360
            return angle_deg - 180
        
        # Prepare Robot Tags
        robot_tags = []
        for t in self.april_tags:
            wall = self.walls[t['wall_idx']]
            if wall is None: continue
            p1 = self.nodes[wall['start']]['pos']; p2 = self.nodes[wall['end']]['pos']
            nx = p1[0] + (p2[0]-p1[0])*t['ratio']; ny = p1[1] + (p2[1]-p1[1])*t['ratio']
            angle = compute_tag_angle(p1,p2,t["side"])
            robot_tags.append({
                "id": t['tag_num'],
                "angle": angle,
                "pos_meter": [round((nx)/DEFAULT_SCALE, 4), round((ny)/DEFAULT_SCALE, 4)]
            })

        # Prepare Robot Zones (Grid Vertices + Orientation inside Zone)
        robot_zones = []
        for z in self.zones:
            grid_pts = [[int(p[0]//self.grid_size), int(p[1]//self.grid_size)] for p in z['points']]
            zone_data = {"name": z['name'], "vertices_grid": grid_pts, "color": z.get('color', DEFAULT_ZONE_COLOR)}
            if 'orientation' in z:
                zone_data['orientation'] = z['orientation']
            robot_zones.append(zone_data)

        # Editor State
        editor_tags = []
        for t in self.april_tags:
            dense_idx = self.get_real_wall_index(t['wall_idx'])
            if dense_idx < 0: continue
            editor_tags.append({"wall_idx": dense_idx, "ratio": t['ratio'], "side": t['side'], "id": t['tag_num']})

        editor_state = {
            "grid_size": self.grid_size,
            "nodes": [n['pos'] for n in self.nodes], 
            "walls": [{"start": w['start'], "end": w['end']} for w in self.walls if w is not None], 
            "tags": editor_tags,
            "zones": [{"name": z['name'], "points": z['points'], "orientation": z.get('orientation', None), "color": z.get('color', DEFAULT_ZONE_COLOR)} for z in self.zones],
            "obstacles": [{"pos": o['pos'], "width": o['width'], "height": o['height'], "angle": o.get('angle', 0)} for o in self.obstacles]
        }

        final_json = {
            "metadata": {"grid_size": self.grid_size, "default_scale": DEFAULT_SCALE},
            "editor_state": editor_state, 
            "robot_data": {               
                "cell_size": self.grid_size / DEFAULT_SCALE,
                "map_origin": [0.0, 0.0],
                "grid": matrix,
                "tags": robot_tags,
                "zones": robot_zones
            }
        }

        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Robot Map JSON", "*.json")])
        if file_path:
            with open(file_path, 'w') as f: json.dump(final_json, f, indent=4)
            obj_path = file_path.replace(".json", ".obj")
            self.generate_obj_from_editor(file_path, obj_path, wall_height=2, wall_thickness=0.01)
            messagebox.showinfo("Saved", "Project saved successfully!")       

    def generate_obj_from_editor(self, json_path, obj_path,
                                wall_height=1.2,
                                wall_thickness=0.08):

        with open(json_path, 'r') as f:
            data = json.load(f)

        nodes = data["editor_state"]["nodes"]
        walls = data["editor_state"]["walls"]

        if not nodes or not walls:
            with open(obj_path, "w") as f:
                f.write("# Empty OBJ (no wall geometry)\n")
            return

        vertices = []
        normals = []
        faces = []

        # -------------------------
        # Helpers
        # -------------------------

        def to_world(p):
            x = (p[0]) / DEFAULT_SCALE
            z = (p[1]) / DEFAULT_SCALE
            return x, z

        def normalize(v):
            l = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
            return [v[0]/l, v[1]/l, v[2]/l] if l > 0 else [0,1,0]

        def compute_normal(v1, v2, v3):
            ux, uy, uz = v2[0]-v1[0], v2[1]-v1[1], v2[2]-v1[2]
            vx, vy, vz = v3[0]-v1[0], v3[1]-v1[1], v3[2]-v1[2]
            return normalize([
                uy*vz - uz*vy,
                uz*vx - ux*vz,
                ux*vy - uy*vx
            ])

        def add_triangle(i1, i2, i3):
            v1 = vertices[i1-1]
            v2 = vertices[i2-1]
            v3 = vertices[i3-1]

            n = compute_normal(v1, v2, v3)
            normals.append(n)
            n_idx = len(normals)

            faces.append([
                (i1, n_idx),
                (i2, n_idx),
                (i3, n_idx)
            ])

        def add_quad(v0, v1, v2, v3):
            idx = len(vertices) + 1
            vertices.extend([v0, v1, v2, v3])

            # correct winding (CCW outward)
            add_triangle(idx,     idx+2, idx+1)
            add_triangle(idx,     idx+3, idx+2)

        # -------------------------
        # Wall generation
        # -------------------------

        def add_wall(p1, p2):
            x1, z1 = to_world(p1)
            x2, z2 = to_world(p2)

            dx = x2 - x1
            dz = z2 - z1
            length = math.hypot(dx, dz)
            if length == 0:
                return

            dx /= length
            dz /= length

            # perpendicular
            px = -dz
            pz = dx

            t = wall_thickness / 2

            # bottom rectangle
            b0 = [x1 + px*t, 0, z1 + pz*t]
            b1 = [x2 + px*t, 0, z2 + pz*t]
            b2 = [x2 - px*t, 0, z2 - pz*t]
            b3 = [x1 - px*t, 0, z1 - pz*t]

            # top rectangle
            t0 = [b0[0], wall_height, b0[2]]
            t1 = [b1[0], wall_height, b1[2]]
            t2 = [b2[0], wall_height, b2[2]]
            t3 = [b3[0], wall_height, b3[2]]

            # faces (6 sides)

            # bottom
            add_quad(b0, b1, b2, b3)

            # top
            add_quad(t0, t3, t2, t1)

            # sides
            add_quad(b0, t0, t1, b1)
            add_quad(b1, t1, t2, b2)
            add_quad(b2, t2, t3, b3)
            add_quad(b3, t3, t0, b0)

        # build all walls
        for w in walls:
            p1 = nodes[w["start"]]
            p2 = nodes[w["end"]]
            add_wall(p1, p2)

        # -------------------------
        # Obstacle boxes (furniture)
        # -------------------------

        obstacles = data["editor_state"].get("obstacles", [])
        for obs in obstacles:
            cx_s, cy_s = obs["pos"]
            ow, oh = obs["width"], obs["height"]
            oangle = obs.get("angle", 0.0)
            rad = math.radians(oangle)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            hw, hh = ow / 2, oh / 2
            corners_local = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
            corners_screen = [(cx_s + lx * cos_a - ly * sin_a, cy_s + lx * sin_a + ly * cos_a)
                              for lx, ly in corners_local]
            world_corners = [to_world(c) for c in corners_screen]

            # bottom and top y
            y_bot = 0
            y_top = OBSTACLE_HEIGHT_3D

            b = [[wc[0], y_bot, wc[1]] for wc in world_corners]
            t = [[wc[0], y_top, wc[1]] for wc in world_corners]

            add_quad(b[3], b[2], b[1], b[0])  # bottom
            add_quad(t[1], t[2], t[3], t[0])  # top
            for i in range(4):
                ni = (i + 1) % 4
                # add_quad(b[i], t[i], t[ni], b[ni])  # sides
                add_quad(b[ni], t[ni], t[i], b[i])  # sides

        # -------------------------
        # Ground plane
        # -------------------------

        xs = [p[0] for p in nodes]
        zs = [p[1] for p in nodes]

        min_x, max_x = min(xs), max(xs)
        min_z, max_z = min(zs), max(zs)

        x1, z1 = to_world([min_x, min_z])
        x2, z2 = to_world([max_x, max_z])

        g0 = [x1, 0, z1]
        g1 = [x2, 0, z1]
        g2 = [x2, 0, z2]
        g3 = [x1, 0, z2]

        add_quad(g0, g1, g2, g3)

        # -------------------------
        # Write OBJ
        # -------------------------

        with open(obj_path, "w") as f:
            for v in vertices:
                f.write(f"v {v[0]} {v[1]} {v[2]}\n")

            for n in normals:
                f.write(f"vn {n[0]} {n[1]} {n[2]}\n")

            for face in faces:
                f.write("f " + " ".join(f"{vi}//{ni}" for vi,ni in face) + "\n")

        print(f"OBJ saved to {obj_path}")

    def load_project(self):
        file_path = filedialog.askopenfilename(filetypes=[("Robot Map JSON", "*.json")])
        if not file_path: return

        try:
            with open(file_path, 'r') as f: data = json.load(f)
            
            if "editor_state" not in data:
                messagebox.showerror("Error", "This file doesn't contain editable data (Old version?).")
                return

            # Reset App State
            self.canvas.delete("all")
            self.nodes = []
            self.walls = []
            self.april_tags = []
            self.zones = []
            self.orientations = []
            self.obstacles = []
            self.history = []
            self.zone_points = []
            self.selected_zone_idx = None
            self.next_zone_uid = 1
            self.pending_orientation = None

            # Restore Settings
            state = data["editor_state"]
            self.grid_size = state.get("grid_size", DEFAULT_GRID_SIZE)
            self.scale_slider.set(self.grid_size)
            self.draw_grid_background()

            # Restore Nodes
            for pos in state["nodes"]:
                self.create_node_obj(pos)

            # Restore Walls
            for w in state["walls"]:
                # Check indices validity
                if w['start'] < len(self.nodes) and w['end'] < len(self.nodes):
                    self.create_wall_obj(w['start'], w['end'])

            # Restore Tags
            # Note: We need to map saved wall indices to new wall indices (since None holes are gone)
            # But here we cleared everything and appended in order, so indices should match 
            # IF the saved "walls" list didn't have Nones. My save logic filtered Nones.
            # So index i in saved list = index i in new list.
            for t in state.get("tags", []):
                if t['wall_idx'] < len(self.walls):
                    new_tag = {'wall_idx': t['wall_idx'], 'ratio': t['ratio'], 'side': t['side'], 'tag_num': t['id'], 'id': []}
                    self.create_visual_tag(new_tag)
                    self.april_tags.append(new_tag)

            # Restore Zones
            for z in state.get("zones", []):
                self.recreate_zone(
                    z.get('name', 'Zone'),
                    z.get('points', []),
                    color=z.get('color', DEFAULT_ZONE_COLOR),
                    uid=z.get('uid')
                )

            # Restore Orientations
            for o in state.get("orientations", []):
                if o.get("type") != "bed_orientation":
                    continue
                pos = o.get("pos", None)
                if not isinstance(pos, (list, tuple)) or len(pos) != 2:
                    continue
                zone_uid = o.get("zone_uid", None)
                if zone_uid is None:
                    zone_idx = self.find_zone_index_by_point(pos[0], pos[1])
                    if zone_idx is None:
                        continue
                    zone_uid = self.zones[zone_idx]['uid']
                if self.get_zone_index_by_uid(zone_uid) is None:
                    continue
                self.create_or_update_orientation(
                    zone_uid,
                    (float(pos[0]), float(pos[1])),
                    float(o.get("angle_degrees", 0.0)),
                    float(o.get("length", ORIENTATION_DEFAULT_LENGTH))
                )

            # Restore Obstacles (Furniture)
            for obs in state.get("obstacles", []):
                pos = obs.get("pos", None)
                if not isinstance(pos, (list, tuple)) or len(pos) != 2:
                    continue
                w = float(obs.get("width", DEFAULT_OBSTACLE_WIDTH))
                h = float(obs.get("height", DEFAULT_OBSTACLE_HEIGHT))
                a = float(obs.get("angle", 0.0))
                self.create_obstacle_obj(float(pos[0]), float(pos[1]), w, h, a)

            self.status.config(text="Project Loaded Successfully.")

        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def get_real_wall_index(self, internal_idx):
        # Helper to map sparse wall array (with Nones) to dense array for saving
        # This is tricky. Simplified: Save logic filters Nones. 
        # So we need to find what "rank" this wall is among active walls.
        if internal_idx < 0 or internal_idx >= len(self.walls):
            return -1
        if self.walls[internal_idx] is None:
            return -1
        active_walls = [w for w in self.walls if w is not None]
        if self.walls[internal_idx] in active_walls:
            return active_walls.index(self.walls[internal_idx])
        return -1

    def screen_to_world_point(self, point):
        # Conversion path intentionally uses grid_size and DEFAULT_SCALE.
        cell_size_world = self.grid_size / DEFAULT_SCALE
        gx = point[0] / self.grid_size
        gy = point[1] / self.grid_size
        return [round(gx * cell_size_world, 4), round(gy * cell_size_world, 4)]

    def create_visual_tag(self, t):
        # Helper to draw tag without user interaction
        box = self.canvas.create_rectangle(0,0,0,0, fill="orange", outline="black", tags="tag")
        line = self.canvas.create_line(0,0,0,0, arrow=tk.LAST, fill="blue", tags="tag")
        txt = self.canvas.create_text(0,0, text=t['tag_num'], font=("Arial",8,"bold"), tags="tag")
        t['id'] = [box, line, txt]
        self.redraw_tag(t)

    def recreate_zone(self, name, points, color=DEFAULT_ZONE_COLOR, uid=None):
        clean_points = []
        for p in points:
            if isinstance(p, (list, tuple)) and len(p) == 2:
                clean_points.append((float(p[0]), float(p[1])))

        if len(clean_points) < 3:
            return None

        if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
            color = DEFAULT_ZONE_COLOR

        if uid is None:
            uid = self.next_zone_uid
            self.next_zone_uid += 1
        else:
            uid = int(uid)
            self.next_zone_uid = max(self.next_zone_uid, uid + 1)

        poly = self.canvas.create_polygon(
            clean_points,
            fill=color,
            stipple=ZONE_STIPPLE,
            outline=self.zone_outline_color(color),
            width=2,
            tags="zone"
        )
        cx, cy = self.polygon_centroid(clean_points)
        lbl = self.canvas.create_text(cx, cy, text=name, font=("Arial", 10, "bold"), fill="#1f4d2e", tags="zone")
        self.canvas.tag_lower(poly, "wall")
        self.zones.append({'uid': uid, 'name': name, 'points': clean_points, 'color': color, 'ids': [poly, lbl]})
        return len(self.zones) - 1

    def polygon_centroid(self, points):
        n = len(points)
        if n == 0:
            return 0.0, 0.0
        if n < 3:
            cx = sum(p[0] for p in points) / n
            cy = sum(p[1] for p in points) / n
            return cx, cy

        area2 = 0.0
        cx = 0.0
        cy = 0.0
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            cross = x0 * y1 - x1 * y0
            area2 += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross

        if abs(area2) < 1e-7:
            cx = sum(p[0] for p in points) / n
            cy = sum(p[1] for p in points) / n
            return cx, cy

        return cx / (3.0 * area2), cy / (3.0 * area2)

    def point_on_segment(self, px, py, p1, p2, eps=1e-6):
        x1, y1 = p1
        x2, y2 = p2
        cross = (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)
        if abs(cross) > eps:
            return False
        dot = (px - x1) * (px - x2) + (py - y1) * (py - y2)
        return dot <= eps

    def point_in_polygon(self, wx, wy, points):
        # Standard ray-casting test with edge check for robust zone hit detection.
        inside = False
        n = len(points)
        if n < 3:
            return False

        j = n - 1
        for i in range(n):
            xi, yi = points[i]
            xj, yj = points[j]

            if self.point_on_segment(wx, wy, (xi, yi), (xj, yj)):
                return True

            intersects = ((yi > wy) != (yj > wy)) and (
                wx < (xj - xi) * (wy - yi) / ((yj - yi) + 1e-12) + xi
            )
            if intersects:
                inside = not inside
            j = i

        return inside

    def zone_outline_color(self, fill_color):
        try:
            r = int(fill_color[1:3], 16)
            g = int(fill_color[3:5], 16)
            b = int(fill_color[5:7], 16)
        except Exception:
            return "#2b6d8a"
        factor = 0.65
        return "#{:02x}{:02x}{:02x}".format(int(r * factor), int(g * factor), int(b * factor))

    # --- Standard Builder Functions (Reused) ---
    def set_mode(self, mode):
        self.mode = mode
        self.zone_points = []
        self.pending_orientation = None
        self.canvas.delete("temp")
        self.canvas.delete("temp_zone")
        self.canvas.delete("temp_zone_hover")
        self.canvas.delete("temp_orientation")

        mode_messages = {
            "draw_wall": "Mode: DRAW WALL (click-drag-release)",
            "place_tag": "Mode: PLACE TAG (select wall side with mouse)",
            "create_zone": "Mode: CREATE ZONE (click points, Enter/Right-Click to close)",
            "orientation": "Mode: ORIENTATION (click inside zone, drag and release)",
            "place_furniture": "Mode: FURNITURE (click to place, Esc to cancel)",
            "select": "Mode: SELECT (click node/zone/obstacle)",
            "delete": "Mode: DELETE (click item to remove)"
        }
        self.status.config(text=mode_messages.get(mode, f"Mode: {mode.upper()}"))

    def update_grid_size(self, val):
        self.grid_size = int(val)
        self.draw_grid_background()
        self.refresh_all_labels(None)


    def calculate_length_m(self, x1, y1, x2, y2):
        return (math.hypot(x2 - x1, y2 - y1)) / DEFAULT_SCALE

    def refresh_all_labels(self, event):
        for w in self.walls:
            if w: self.update_wall_label(w)

    def update_wall_label(self, wall):
        p1 = self.nodes[wall['start']]['pos']; p2 = self.nodes[wall['end']]['pos']
        length_m = self.calculate_length_m(p1[0], p1[1], p2[0], p2[1])
        mid_x = (p1[0] + p2[0]) / 2; mid_y = (p1[1] + p2[1]) / 2 - 10
        self.canvas.coords(wall['text_id'], mid_x, mid_y)
        self.canvas.itemconfigure(wall['text_id'], text=f"{length_m:.2f}m")
        self.canvas.tag_raise(wall['text_id'])

    def on_click(self, event):
        x, y = event.x, event.y
        if self.mode == "create_zone": self.handle_zone_click(x, y); return
        if self.mode == "orientation": self.start_orientation_placement(x, y); return
        if self.mode == "place_furniture": self.place_furniture(x, y); return
        sx, sy, snap_n, snap_w = self.get_smart_coords_with_info(x, y) 
        if self.mode == "draw_wall":
            if snap_w is not None and snap_n is None: snap_n = self.split_wall_at_point(snap_w, sx, sy)
            self.current_draw_start = (sx, sy)
            self.temp_line = self.canvas.create_line(sx, sy, x, y, fill="gray", dash=(2,2), tags="temp")
            self.temp_text = self.canvas.create_text(x, y-15, text="0.00m", fill="blue", font=("Arial", 8, "bold"), tags="temp")
        elif self.mode == "select": self.check_selection(x, y)
        elif self.mode == "place_tag":
            if self.pending_tag_wall: self.finalize_tag()
            else: self.start_tag_placement(x, y)
        elif self.mode == "delete": self.delete_item_at(x, y)

    def on_drag(self, event):
        x, y = event.x, event.y
        if self.mode == "create_zone": return
        if self.mode == "orientation" and self.pending_orientation:
            self.update_temp_orientation(x, y)
            return
        if self.mode == "select" and getattr(self, '_selected_obstacle_idx', None) is not None:
            idx = self._selected_obstacle_idx
            if 0 <= idx < len(self.obstacles):
                obs = self.obstacles[idx]
                obs['pos'] = (x, y)
                self.update_obstacle_visual(obs)
                self._obstacle_dragged = True
            return
        sx, sy, _, _ = self.get_smart_coords_with_info(x, y, exclude_start=True)
        if self.mode == "draw_wall" and self.current_draw_start:
            self.canvas.coords(self.temp_line, self.current_draw_start[0], self.current_draw_start[1], sx, sy)
            dist_m = self.calculate_length_m(self.current_draw_start[0], self.current_draw_start[1], sx, sy)
            mid_x = (self.current_draw_start[0] + sx) / 2; mid_y = (self.current_draw_start[1] + sy) / 2 - 15
            self.canvas.coords(self.temp_text, mid_x, mid_y)
            self.canvas.itemconfigure(self.temp_text, text=f"{dist_m:.2f}m")
        elif self.mode == "select" and self.selected_node_idx is not None:
            self.move_node(self.selected_node_idx, x, y)

    def on_release(self, event):
        if self.mode == "orientation" and self.pending_orientation:
            self.finalize_orientation(event.x, event.y)
            self.selected_node_idx = None
            return

        if self.mode == "draw_wall" and self.current_draw_start:
            sx, sy, snap_n, snap_w = self.get_smart_coords_with_info(event.x, event.y, exclude_start=True)
            self.canvas.delete(self.temp_line); self.canvas.delete(self.temp_text)
            if math.hypot(sx - self.current_draw_start[0], sy - self.current_draw_start[1]) > 5:
                if snap_w is not None and snap_n is None: snap_n = self.split_wall_at_point(snap_w, sx, sy)
                self.create_wall_from_coords(self.current_draw_start, (sx, sy))
            self.current_draw_start = None
        self.selected_node_idx = None
        if hasattr(self, '_selected_obstacle_idx'):
            if self._selected_obstacle_idx is not None and getattr(self, '_obstacle_dragged', False):
                if 0 <= self._selected_obstacle_idx < len(self.obstacles):
                    obs = self.obstacles[self._selected_obstacle_idx]
                    self.canvas.itemconfigure(obs['id'], outline="#a04000", width=2)
                self._selected_obstacle_idx = None
            self._obstacle_dragged = False

    def create_node_obj(self, pos):
        for i, node in enumerate(self.nodes):
            if math.hypot(pos[0]-node['pos'][0], pos[1]-node['pos'][1]) < 2: return i
        r = NODE_RADIUS
        oid = self.canvas.create_oval(pos[0]-r, pos[1]-r, pos[0]+r, pos[1]+r, fill="#3498db", outline="white", width=2, tags="node")
        self.nodes.append({'pos': pos, 'id': oid, 'connections': []})
        return len(self.nodes) - 1

    def create_wall_obj(self, idx1, idx2):
        p1 = self.nodes[idx1]['pos']; p2 = self.nodes[idx2]['pos']
        lid = self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], width=4, fill="#34495e", capstyle=tk.ROUND, tags="wall")
        mid_x = (p1[0] + p2[0]) / 2; mid_y = (p1[1] + p2[1]) / 2 - 10
        dist_m = self.calculate_length_m(p1[0], p1[1], p2[0], p2[1])
        tid = self.canvas.create_text(mid_x, mid_y, text=f"{dist_m:.2f}m", fill="#e67e22", font=("Arial", 9, "bold"), tags="measure")
        self.canvas.tag_lower(lid, "node")
        wall_data = {'start': idx1, 'end': idx2, 'id': lid, 'text_id': tid}
        self.walls.append(wall_data)
        self.nodes[idx1]['connections'].append(len(self.walls)-1); self.nodes[idx2]['connections'].append(len(self.walls)-1)
        return len(self.walls)-1
    
    def create_wall_from_coords(self, p1, p2):
        self.create_wall_obj(self.create_node_obj(p1), self.create_node_obj(p2))

    def split_wall_at_point(self, wall_idx, split_x, split_y):
        old_wall = self.walls[wall_idx]
        p1 = self.nodes[old_wall['start']]['pos']; p2 = self.nodes[old_wall['end']]['pos']
        total_len = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
        split_ratio = math.hypot(split_x-p1[0], split_y-p1[1]) / total_len if total_len > 0 else 0.5
        
        new_mid = self.create_node_obj((split_x, split_y))
        tags = [t for t in self.april_tags if t['wall_idx'] == wall_idx]
        
        self.remove_wall_keep_nodes(wall_idx)
        w1 = self.create_wall_obj(old_wall['start'], new_mid)
        w2 = self.create_wall_obj(new_mid, old_wall['end'])
        
        for t in tags:
            if t['ratio'] <= split_ratio:
                t['wall_idx'] = w1; t['ratio'] = t['ratio']/split_ratio if split_ratio>0 else 0
            else:
                t['wall_idx'] = w2; t['ratio'] = (t['ratio']-split_ratio)/(1-split_ratio) if (1-split_ratio)>0 else 0
            self.redraw_tag(t)
        return new_mid

    def remove_wall_keep_nodes(self, idx):
        if not self.walls[idx]: return
        w = self.walls[idx]; self.canvas.delete(w['id']); self.canvas.delete(w['text_id'])
        if idx in self.nodes[w['start']]['connections']: self.nodes[w['start']]['connections'].remove(idx)
        if idx in self.nodes[w['end']]['connections']: self.nodes[w['end']]['connections'].remove(idx)
        self.walls[idx] = None

    def get_smart_coords_with_info(self, x, y, exclude_start=False):
        final_x, final_y = x, y; snap_n = None; snap_w = None
        if self.snap_enabled.get():
            nx, ny, dist, idx = self.find_closest_node(x, y, exclude_start)
            if dist < SNAP_DISTANCE: return nx, ny, idx, None
            ex, ey, edist, widx = self.find_closest_edge_point(x, y)
            if edist < EDGE_SNAP_DISTANCE: final_x, final_y = ex, ey; snap_w = widx
        if self.straight_enabled.get() and self.current_draw_start:
            sx, sy = self.current_draw_start
            if abs(final_x - sx) < STRAIGHT_TOLERANCE: final_x = sx
            elif abs(final_y - sy) < STRAIGHT_TOLERANCE: final_y = sy
        return final_x, final_y, snap_n, snap_w

    def find_closest_node(self, x, y, exclude_start):
        best = (x, y); min_dist = float('inf'); idx = None
        for i, node in enumerate(self.nodes):
            if exclude_start and self.current_draw_start and node['pos'] == self.current_draw_start: continue
            dist = math.hypot(x - node['pos'][0], y - node['pos'][1])
            if dist < min_dist: min_dist = dist; best = node['pos']; idx = i
        return best[0], best[1], min_dist, idx

    def find_closest_edge_point(self, x, y):
        best = (x, y); min_dist = float('inf'); widx = None
        for i, wall in enumerate(self.walls):
            if not wall: continue
            p1 = self.nodes[wall['start']]['pos']; p2 = self.nodes[wall['end']]['pos']
            nx, ny, dist, t = self.point_line_projection(x, y, p1, p2)
            if 0.05 < t < 0.95 and dist < min_dist: min_dist = dist; best = (nx, ny); widx = i
        return best[0], best[1], min_dist, widx

    # --- Tags, Zones, Etc ---
    def start_tag_placement(self, x, y):
        # (Same as before, simplified for space)
        best_wall = None; min_dist = 40; proj_info = None
        for i, wall in enumerate(self.walls):
            if not wall: continue
            p1 = self.nodes[wall['start']]['pos']; p2 = self.nodes[wall['end']]['pos']
            nx, ny, dist, t = self.point_line_projection(x, y, p1, p2)
            if dist < min_dist and 0.05 <= t <= 0.95: min_dist = dist; best_wall = i; proj_info = (nx, ny, t)
        if best_wall is not None:
            self.pending_tag_wall = {'idx': best_wall, 'ratio': proj_info[2], 'proj_pos': (proj_info[0], proj_info[1])}
            self.canvas.delete("temp_arrow")
            self.temp_arrow = self.canvas.create_line(x, y, x, y, arrow=tk.LAST, width=2, fill="red", tags="temp_arrow")
            self.status.config(text="Move mouse to choose SIDE -> Click to Confirm")

    def on_hover(self, event):
        if self.mode == "place_tag" and self.pending_tag_wall:
            w_idx = self.pending_tag_wall['idx']
            p1 = self.nodes[self.walls[w_idx]['start']]['pos']; p2 = self.nodes[self.walls[w_idx]['end']]['pos']
            dx, dy = p2[0]-p1[0], p2[1]-p1[1]
            cross = dx * (event.y - p1[1]) - dy * (event.x - p1[0])
            self.pending_tag_wall['side'] = 1 if cross > 0 else -1
            px, py = self.pending_tag_wall['proj_pos']
            ang = math.atan2(dy, dx) + (math.pi/2 * self.pending_tag_wall['side'])
            ax = px + 20 * math.cos(ang); ay = py + 20 * math.sin(ang)
            self.canvas.coords(self.temp_arrow, px, py, ax, ay)
        elif self.mode == "create_zone":
            self.update_zone_hover_preview(event.x, event.y)
        else:
            self.canvas.delete("temp_zone_hover")

    def finalize_tag(self):
        tid = simpledialog.askstring("Tag", "ID:")
        if tid:
            new_tag = {'wall_idx': self.pending_tag_wall['idx'], 'ratio': self.pending_tag_wall['ratio'], 
                       'side': self.pending_tag_wall['side'], 'tag_num': tid, 'id': []}
            self.create_visual_tag(new_tag)
            self.april_tags.append(new_tag)
        self.canvas.delete("temp_arrow"); self.pending_tag_wall = None; self.set_mode("select")

    def redraw_tag(self, tag):
        wall = self.walls[tag['wall_idx']]
        p1 = self.nodes[wall['start']]['pos']; p2 = self.nodes[wall['end']]['pos']
        nx = p1[0] + (p2[0]-p1[0])*tag['ratio']; ny = p1[1] + (p2[1]-p1[1])*tag['ratio']
        ang = math.atan2(p2[1]-p1[1], p2[0]-p1[0]) + (math.pi/2 * tag['side'])
        tx = nx + 20*math.cos(ang); ty = ny + 20*math.sin(ang)
        self.canvas.coords(tag['id'][0], tx-10, ty-10, tx+10, ty+10)
        self.canvas.coords(tag['id'][1], nx, ny, tx, ty); self.canvas.coords(tag['id'][2], tx, ty)

    def handle_zone_click(self, x, y):
        if len(self.zone_points) > 2:
            sx, sy = self.zone_points[0]
            if math.hypot(x - sx, y - sy) <= ZONE_CLOSE_DISTANCE:
                self.finish_zone()
                return

        r = 4
        self.canvas.create_oval(x-r, y-r, x+r, y+r, fill="#2ecc71", outline="black", tags="temp_zone")
        self.zone_points.append((x, y))
        if len(self.zone_points) > 1:
            self.canvas.create_line(self.zone_points[-2], self.zone_points[-1], fill="#2ecc71", dash=(2,2), tags="temp_zone")
        self.update_zone_hover_preview(x, y)

    def update_zone_hover_preview(self, x, y):
        self.canvas.delete("temp_zone_hover")
        if not self.zone_points:
            return
        lx, ly = self.zone_points[-1]
        self.canvas.create_line(lx, ly, x, y, fill="#16a085", dash=(4,3), width=2, tags="temp_zone_hover")
        if len(self.zone_points) > 1:
            sx, sy = self.zone_points[0]
            self.canvas.create_line(x, y, sx, sy, fill="#95a5a6", dash=(2,4), tags="temp_zone_hover")

    def finish_zone_shortcut(self, event):
        if self.mode == "create_zone" and len(self.zone_points) > 2: self.finish_zone()

    def finish_zone_shortcut_key(self, event):
        self.finish_zone_shortcut(event)

    def finish_zone(self):
        if len(self.zone_points) < 3:
            self.canvas.delete("temp_zone")
            self.canvas.delete("temp_zone_hover")
            self.zone_points = []
            return

        name = simpledialog.askstring("Zone", "Zone Name:")
        if name:
            idx = self.recreate_zone(name.strip(), list(self.zone_points), color=DEFAULT_ZONE_COLOR)
            if idx is not None:
                self.select_zone(idx)
                self.status.config(text=f"Zone '{name}' created.")
        else:
            self.status.config(text="Zone creation canceled.")

        self.canvas.delete("temp_zone")
        self.canvas.delete("temp_zone_hover")
        self.zone_points = []

    def find_zone_index_by_point(self, x, y):
        for idx in range(len(self.zones) - 1, -1, -1):
            if self.point_in_polygon(x, y, self.zones[idx]['points']):
                return idx
        return None

    def update_zone_style(self, idx, selected=False):
        if idx is None or idx < 0 or idx >= len(self.zones):
            return
        zone = self.zones[idx]
        outline = "#f39c12" if selected else self.zone_outline_color(zone['color'])
        width = 3 if selected else 2
        self.canvas.itemconfigure(zone['ids'][0], fill=zone['color'], stipple=ZONE_STIPPLE, outline=outline, width=width)

    def clear_zone_selection(self):
        if self.selected_zone_idx is not None and 0 <= self.selected_zone_idx < len(self.zones):
            self.update_zone_style(self.selected_zone_idx, selected=False)
        self.selected_zone_idx = None

    def select_zone(self, idx):
        if idx is None or idx < 0 or idx >= len(self.zones):
            self.clear_zone_selection()
            return
        if self.selected_zone_idx is not None and self.selected_zone_idx != idx:
            self.update_zone_style(self.selected_zone_idx, selected=False)
        self.selected_zone_idx = idx
        self.update_zone_style(idx, selected=True)
        self.status.config(text=f"Selected zone: {self.zones[idx]['name']} (C = color, Delete = remove)")

    def change_selected_zone_color(self):
        if self.selected_zone_idx is None or self.selected_zone_idx >= len(self.zones):
            messagebox.showinfo("Zone", "Select a zone first in Edit mode.")
            return

        zone = self.zones[self.selected_zone_idx]
        picked = colorchooser.askcolor(initialcolor=zone['color'], title=f"Color for {zone['name']}")
        if picked and picked[1]:
            zone['color'] = picked[1]
            self.update_zone_style(self.selected_zone_idx, selected=True)

    def on_change_zone_color_key(self, event):
        if self.mode == "select":
            self.change_selected_zone_color()

    def on_delete_key(self, event):
        if self.mode == "select":
            if getattr(self, '_selected_obstacle_idx', None) is not None:
                idx = self._selected_obstacle_idx
                if 0 <= idx < len(self.obstacles):
                    obs = self.obstacles[idx]
                    self.canvas.delete(obs['id'])
                    self.canvas.delete(obs['label_id'])
                    self.obstacles.pop(idx)
                    self._selected_obstacle_idx = None
                    self.status.config(text="Furniture deleted.")
                    return
            if self.selected_zone_idx is not None:
                self.delete_zone_by_index(self.selected_zone_idx)

    def on_escape_key(self, event):
        self.set_mode("select")

    def on_rotate_obstacle_key(self, event):
        if self.mode == "select" and getattr(self, '_selected_obstacle_idx', None) is not None:
            self.rotate_obstacle(self._selected_obstacle_idx, 15)

    def on_rotate_obstacle_key_neg(self, event):
        if self.mode == "select" and getattr(self, '_selected_obstacle_idx', None) is not None:
            self.rotate_obstacle(self._selected_obstacle_idx, -15)

    def place_furniture(self, x, y):
        width = simpledialog.askfloat("Furniture Width", "Width (px):", initialvalue=DEFAULT_OBSTACLE_WIDTH, minvalue=10, maxvalue=500)
        if width is None:
            return
        height = simpledialog.askfloat("Furniture Height", "Height (px):", initialvalue=DEFAULT_OBSTACLE_HEIGHT, minvalue=10, maxvalue=500)
        if height is None:
            return
        self.create_obstacle_obj(x, y, width, height, angle=0.0)
        self.status.config(text=f"Furniture placed at ({x},{y}), size {int(width)}×{int(height)}")

    def delete_zone_by_index(self, idx):
        if idx is None or idx < 0 or idx >= len(self.zones):
            return

        zone = self.zones[idx]
        for cid in zone['ids']:
            self.canvas.delete(cid)
        self.remove_orientation_by_zone_uid(zone['uid'])
        self.zones.pop(idx)

        if self.selected_zone_idx == idx:
            self.selected_zone_idx = None
        elif self.selected_zone_idx is not None and self.selected_zone_idx > idx:
            self.selected_zone_idx -= 1

        if self.selected_zone_idx is not None and self.selected_zone_idx < len(self.zones):
            self.update_zone_style(self.selected_zone_idx, selected=True)

        self.status.config(text=f"Zone '{zone['name']}' deleted.")

    def get_zone_index_by_uid(self, zone_uid):
        for i, z in enumerate(self.zones):
            if z['uid'] == zone_uid:
                return i
        return None

    # --- Orientation Tool ---
    def start_orientation_placement(self, x, y):
        zone_idx = self.find_zone_index_by_point(x, y)
        if zone_idx is None:
            self.pending_orientation = None
            self.canvas.delete("temp_orientation")
            self.status.config(text="Orientation mode: click inside a zone first.")
            return

        self.select_zone(zone_idx)
        self.pending_orientation = {
            'zone_uid': self.zones[zone_idx]['uid'],
            'center': (x, y)
        }
        self.update_temp_orientation(x + ORIENTATION_DEFAULT_LENGTH, y)

    def vector_to_math_angle(self, dx, dy):
        # 0° = East, positive counter-clockwise, with canvas Y inverted.
        return (math.degrees(math.atan2(-dy, dx)) + 360.0) % 360.0

    def angle_to_canvas_vector(self, angle_deg, length):
        rad = math.radians(angle_deg)
        return length * math.cos(rad), -length * math.sin(rad)

    def update_temp_orientation(self, x, y):
        if not self.pending_orientation:
            return

        cx, cy = self.pending_orientation['center']
        dx = x - cx
        dy = y - cy
        dist = math.hypot(dx, dy)
        if dist < ORIENTATION_MIN_DRAG:
            dx, dy = ORIENTATION_DEFAULT_LENGTH, 0
            dist = ORIENTATION_DEFAULT_LENGTH

        angle = self.vector_to_math_angle(dx, dy)
        length = max(ORIENTATION_MIN_DRAG * 2, min(dist, 100))
        vx, vy = self.angle_to_canvas_vector(angle, length)

        self.canvas.delete("temp_orientation")
        self.canvas.create_oval(cx-11, cy-11, cx+11, cy+11, outline="#7f8c8d", width=2, dash=(3,2), tags="temp_orientation")
        self.canvas.create_line(cx, cy, cx+vx, cy+vy, fill="#e74c3c", width=3, dash=(4,2), arrow=tk.LAST, tags="temp_orientation")
        self.canvas.create_text(cx+vx+16, cy+vy, text=f"{angle:.1f}°", fill="#c0392b", font=("Arial", 9, "bold"), tags="temp_orientation")

    def create_or_update_orientation(self, zone_uid, pos, angle_deg, length=ORIENTATION_DEFAULT_LENGTH):
        if self.get_zone_index_by_uid(zone_uid) is None:
            return

        self.remove_orientation_by_zone_uid(zone_uid)
        cx, cy = pos
        vx, vy = self.angle_to_canvas_vector(angle_deg, length)

        tags = ("orientation",)
        circle = self.canvas.create_oval(cx-11, cy-11, cx+11, cy+11, fill="#ecf0f1", outline="#2c3e50", width=2, tags=tags)
        arrow = self.canvas.create_line(
            cx, cy, cx+vx, cy+vy,
            fill="#e74c3c", width=4, arrow=tk.LAST,
            arrowshape=(14, 16, 6),
            tags=tags
        )
        text = self.canvas.create_text(cx+vx+18, cy+vy, text=f"{angle_deg:.1f}°", fill="#c0392b", font=("Arial", 10, "bold"), tags=tags)

        self.orientations.append({
            'type': 'bed_orientation',
            'zone_uid': zone_uid,
            'pos': (cx, cy),
            'angle_degrees': angle_deg,
            'length': length,
            'id': [circle, arrow, text]
        })

    def finalize_orientation(self, x, y):
        if not self.pending_orientation:
            return

        cx, cy = self.pending_orientation['center']
        dx = x - cx
        dy = y - cy
        dist = math.hypot(dx, dy)

        if dist < ORIENTATION_MIN_DRAG:
            self.canvas.delete("temp_orientation")
            self.pending_orientation = None
            self.status.config(text="Orientation canceled: drag farther to define direction.")
            return

        angle = self.vector_to_math_angle(dx, dy)
        length = max(ORIENTATION_MIN_DRAG * 2, min(dist, 100))
        self.create_or_update_orientation(self.pending_orientation['zone_uid'], (cx, cy), angle, length)
        self.canvas.delete("temp_orientation")
        self.pending_orientation = None
        self.status.config(text=f"Bed orientation set: {angle:.1f}°")

    def remove_orientation_by_zone_uid(self, zone_uid):
        for o in list(self.orientations):
            if o['zone_uid'] == zone_uid:
                for cid in o['id']:
                    self.canvas.delete(cid)
                self.orientations.remove(o)

    def remove_orientation_by_canvas_id(self, cid):
        for o in list(self.orientations):
            if cid in o['id']:
                for oid in o['id']:
                    self.canvas.delete(oid)
                self.orientations.remove(o)
                return
    
    # --- Deletion ---
    def delete_item_at(self, x, y):
        nearby = self.canvas.find_overlapping(x-6, y-6, x+6, y+6)

        for item in nearby:
            tags = self.canvas.gettags(item)
            if "wall" in tags:
                for i, w in enumerate(self.walls):
                    if w and w['id'] == item:
                        self.remove_wall(i)
                        return

        for item in nearby:
            tags = self.canvas.gettags(item)
            if "tag" in tags:
                self.remove_tag_by_id(item)
                return
            if "orientation" in tags:
                self.remove_orientation_by_canvas_id(item)
                return
            if "obstacle" in tags:
                for i, obs in enumerate(self.obstacles):
                    if obs['id'] == item or obs['label_id'] == item:
                        self.canvas.delete(obs['id'])
                        self.canvas.delete(obs['label_id'])
                        self.obstacles.pop(i)
                        self.status.config(text="Furniture deleted.")
                        return
            if "node" in tags:
                for i, n in enumerate(self.nodes):
                    if n['id'] == item:
                        walls_copy = list(n['connections'])
                        for wid in walls_copy:
                            self.remove_wall(wid)
                        self.canvas.delete(n['id'])
                        n['id'] = None
                        return

        zone_idx = self.find_zone_index_by_point(x, y)
        if zone_idx is not None:
            self.delete_zone_by_index(zone_idx)

    def remove_wall(self, idx):
        if not self.walls[idx]: return
        self.remove_wall_keep_nodes(idx)
        tags = [t for t in self.april_tags if t['wall_idx'] == idx]
        for t in tags: 
            for x in t['id']: self.canvas.delete(x)
            self.april_tags.remove(t)

    def undo(self):
        # Undo is complex with saving/loading. For simplicity, we just clear history on load.
        # This function would need to be very robust to handle ID changes.
        # Keeping it basic:
        if not self.history: return
        # ... (Same as before, omitted for safety as Load is better)

    def point_line_projection(self, px, py, p1, p2):
        x1,y1=p1; x2,y2=p2; dx,dy = x2-x1, y2-y1
        if dx==0 and dy==0: return x1,y1,999,0
        t = ((px-x1)*dx + (py-y1)*dy) / (dx*dx + dy*dy)
        nx = x1+t*dx; ny = y1+t*dy
        return nx, ny, math.hypot(px-nx, py-ny), t
    
    def move_node(self, idx, nx, ny):
        # (Same as before)
        node = self.nodes[idx]; node['pos'] = (nx, ny)
        r = NODE_RADIUS; self.canvas.coords(node['id'], nx-r, ny-r, nx+r, ny+r)
        seen = set()
        for wid in node['connections']:
            if wid not in seen:
                w = self.walls[wid]; p1=self.nodes[w['start']]['pos']; p2=self.nodes[w['end']]['pos']
                self.canvas.coords(w['id'], p1[0], p1[1], p2[0], p2[1])
                self.update_wall_label(w)
                for t in self.april_tags:
                    if t['wall_idx'] == wid: self.redraw_tag(t)
                seen.add(wid)

    def check_selection(self, x, y):
        clicked = self.canvas.find_overlapping(x-5, y-5, x+5, y+5)
        for item in clicked:
            if "node" in self.canvas.gettags(item):
                for i, n in enumerate(self.nodes):
                    if n['id'] == item:
                        self.clear_zone_selection()
                        self.clear_obstacle_selection()
                        self.selected_node_idx = i
                        return

        for item in clicked:
            if "tag" in self.canvas.gettags(item):
                self.clear_zone_selection()
                self.clear_obstacle_selection()
                self.selected_node_idx = None
                return

        obs_idx = self.find_obstacle_index_at(x, y)
        if obs_idx is not None:
            self.clear_zone_selection()
            self.clear_obstacle_selection()
            self.selected_node_idx = None
            self._selected_obstacle_idx = obs_idx
            self.canvas.itemconfigure(self.obstacles[obs_idx]['id'], outline="#f1c40f", width=3)
            self.status.config(text="Furniture selected (R=rotate CW, L=rotate CCW, drag=move, Del=remove)")
            return

        zone_idx = self.find_zone_index_by_point(x, y)
        if zone_idx is not None:
            self.selected_node_idx = None
            self.clear_obstacle_selection()
            self.select_zone(zone_idx)
            return

        self.selected_node_idx = None
        self.clear_obstacle_selection()
        self.clear_zone_selection()

    def remove_tag_by_id(self, cid):
        for t in self.april_tags:
            if cid in t['id']:
                for x in t['id']: self.canvas.delete(x)
                self.april_tags.remove(t); return

    def draw_grid_background(self):
        self.canvas.delete("grid")
        for i in range(0, WINDOW_WIDTH, self.grid_size): self.canvas.create_line(i,0,i,WINDOW_HEIGHT, fill="#f0f0f0", tags="grid")
        for i in range(0, WINDOW_HEIGHT, self.grid_size): self.canvas.create_line(0,i,WINDOW_WIDTH,i, fill="#f0f0f0", tags="grid")
        self.canvas.tag_lower("grid")

    # --- Obstacle (Furniture) Helpers ---

    def create_obstacle_obj(self, cx, cy, width, height, angle=0.0):
        corners = self.get_obstacle_corners(cx, cy, width, height, angle)
        flat = []
        for c in corners:
            flat.extend([c[0], c[1]])
        oid = self.canvas.create_polygon(*flat, fill=OBSTACLE_COLOR, stipple=OBSTACLE_STIPPLE,
                                          outline="#a04000", width=2, tags="obstacle")
        lbl = self.canvas.create_text(cx, cy, text=f"{int(width)}×{int(height)}",
                                       font=("Arial", 8, "bold"), fill="#7f2c00", tags="obstacle")
        self.canvas.tag_lower(oid, "wall")
        obs = {'pos': (cx, cy), 'width': width, 'height': height, 'angle': angle, 'id': oid, 'label_id': lbl}
        self.obstacles.append(obs)
        return len(self.obstacles) - 1

    def get_obstacle_corners(self, cx, cy, w, h, angle_deg):
        rad = math.radians(angle_deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        hw, hh = w / 2, h / 2
        corners_local = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        return [(cx + lx * cos_a - ly * sin_a, cy + lx * sin_a + ly * cos_a)
                for lx, ly in corners_local]

    def update_obstacle_visual(self, obs):
        corners = self.get_obstacle_corners(obs['pos'][0], obs['pos'][1], obs['width'], obs['height'], obs['angle'])
        flat = []
        for c in corners:
            flat.extend([c[0], c[1]])
        self.canvas.coords(obs['id'], *flat)
        self.canvas.coords(obs['label_id'], obs['pos'][0], obs['pos'][1])
        self.canvas.itemconfigure(obs['label_id'], text=f"{int(obs['width'])}×{int(obs['height'])}")

    def point_in_rotated_rect(self, px, py, cx, cy, w, h, angle_deg):
        rad = math.radians(-angle_deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        dx, dy = px - cx, py - cy
        local_x = dx * cos_a - dy * sin_a
        local_y = dx * sin_a + dy * cos_a
        return abs(local_x) <= w / 2 and abs(local_y) <= h / 2

    def find_obstacle_index_at(self, x, y):
        for i in range(len(self.obstacles) - 1, -1, -1):
            obs = self.obstacles[i]
            if self.point_in_rotated_rect(x, y, obs['pos'][0], obs['pos'][1],
                                            obs['width'], obs['height'], obs['angle']):
                return i
        return None

    def rotate_obstacle(self, idx, delta_deg):
        if 0 <= idx < len(self.obstacles):
            obs = self.obstacles[idx]
            obs['angle'] = (obs['angle'] + delta_deg) % 360
            self.update_obstacle_visual(obs)

    def clear_obstacle_selection(self):
        idx = getattr(self, '_selected_obstacle_idx', None)
        if idx is not None and 0 <= idx < len(self.obstacles):
            self.canvas.itemconfigure(self.obstacles[idx]['id'], outline="#a04000", width=2)
        self._selected_obstacle_idx = None

if __name__ == "__main__":
    root = tk.Tk()
    app = SaveLoadMapBuilder(root)
    root.mainloop()