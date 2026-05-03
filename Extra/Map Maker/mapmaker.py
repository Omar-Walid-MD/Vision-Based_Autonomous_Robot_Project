import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
import math
import json
import os

# --- إعدادات النافذة ---
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 750
DEFAULT_GRID_SIZE = 25
DEFAULT_SCALE = 20
NODE_RADIUS = 6
SNAP_DISTANCE = 20
EDGE_SNAP_DISTANCE = 15
STRAIGHT_TOLERANCE = 20

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
        self.pending_tag_wall = None
        self.zone_points = []

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
        
        tk.Button(toolbar, text="✋ Edit", command=lambda: self.set_mode("select"), **btn_style).pack(side=tk.LEFT, padx=10)
        tk.Button(toolbar, text="❌ Del", command=lambda: self.set_mode("delete"), bg="#c0392b", fg="white").pack(side=tk.LEFT, padx=2)

        # 2. Measurements
        tk.Label(toolbar, text=" | ", bg="#2c3e50", fg="gray").pack(side=tk.LEFT, padx=5)
        
        self.scale_slider = tk.Scale(toolbar, from_=1, to=100, orient=tk.HORIZONTAL, command=self.update_grid_size, 
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

        self.status = tk.Label(self.root, text="Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    # --- SAVE & LOAD SYSTEM (NEW) ---

    def save_project(self):
        # 1. Generate Robot Data (Grid, etc.) - نفس الكود القديم
        self.canvas.delete("vis_grid")
        active_walls = [w for w in self.walls if w is not None]
        occupied_cells = set()
        for w in active_walls:
            p1 = self.nodes[w['start']]['pos']; p2 = self.nodes[w['end']]['pos']
            dist = int(math.hypot(p2[0]-p1[0], p2[1]-p1[1]))
            if dist == 0: continue
            for i in range(dist):
                t = i / dist
                curr_x = p1[0] + t * (p2[0] - p1[0]); curr_y = p1[1] + t * (p2[1] - p1[1])
                c = int(curr_x // self.grid_size); r = int(curr_y // self.grid_size)
                occupied_cells.add((r, c))

        rows = WINDOW_HEIGHT // self.grid_size; cols = WINDOW_WIDTH // self.grid_size
        matrix = [[1 for _ in range(cols)] for _ in range(rows)]
        for r, c in occupied_cells:
            if 0 <= r < rows and 0 <= c < cols: matrix[r][c] = 0 
            
    
        def compute_tag_angle(p1, p2, side):
            dx = p2[0] - p1[0]
            dy = -(p2[1] - p1[1])  # 🔥 FIX: invert Y

            angle = math.atan2(dy, dx)

            if side == 1:
                angle += math.pi / 2
            else:
                angle -= math.pi / 2

            angle_deg = math.degrees(angle)
            angle_deg = (angle_deg + 360) % 360

            return angle_deg - 180
        
        # 2. Prepare Export Data (For Robot)
        robot_tags = []
        for t in self.april_tags:
            wall = self.walls[t['wall_idx']]
            p1 = self.nodes[wall['start']]['pos']; p2 = self.nodes[wall['end']]['pos']
            nx = p1[0] + (p2[0]-p1[0])*t['ratio']; ny = p1[1] + (p2[1]-p1[1])*t['ratio']
            angle = compute_tag_angle(p1,p2,t["side"])
            robot_tags.append({
                "id": t['tag_num'],
                "angle": angle,
                "pos_meter": [round((nx)/DEFAULT_SCALE, 2), round((ny)/DEFAULT_SCALE, 2)]
            })

        robot_zones = []
        for z in self.zones:
            grid_pts = [[round(p[0]/self.grid_size), round(p[1]/self.grid_size)] for p in z['points']]
            robot_zones.append({"name": z['name'], "vertices_grid": grid_pts})

        # 3. Prepare EDITOR STATE (For Loading Back) - ده الجزء الجديد المهم
        editor_state = {
            "grid_size": self.grid_size,
            "nodes": [n['pos'] for n in self.nodes], # Save raw positions
            "walls": [{"start": w['start'], "end": w['end']} for w in self.walls if w is not None], # Save indices
            "tags": [{"wall_idx": self.get_real_wall_index(t['wall_idx']), "ratio": t['ratio'], "side": t['side'], "id": t['tag_num']} for t in self.april_tags],
            "zones": [{"name": z['name'], "points": z['points']} for z in self.zones]
        }

        # Combine Everything
        final_json = {
            "metadata": {"grid_size": self.grid_size},
            "editor_state": editor_state, # This is for US (the app)
            "robot_data": {               # This is for the ROBOT
                "cell_size": self.grid_size / DEFAULT_SCALE,
                "grid": matrix,
                "tags": robot_tags,
                "zones": robot_zones
            }
        }

        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Robot Map JSON", "*.json")])
        if file_path:
            with open(file_path, 'w') as f: json.dump(final_json, f, indent=4)
            
            # 2. Generate OBJ path (same name)
            obj_path = file_path.replace(".json", ".obj")

            # 3. Call the generator
            self.generate_obj_from_editor(
                file_path,
                obj_path,
                wall_height=2,
                wall_thickness=0.01
            )
            messagebox.showinfo("Saved", "Project saved successfully!")
            

    def generate_obj_from_editor(self, json_path, obj_path,
                                wall_height=1.2,
                                wall_thickness=0.08):

        with open(json_path, 'r') as f:
            data = json.load(f)

        nodes = data["editor_state"]["nodes"]
        walls = data["editor_state"]["walls"]
        grid_size = data["metadata"]["grid_size"]

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
            self.history = []

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
            for t in state["tags"]:
                if t['wall_idx'] < len(self.walls):
                    new_tag = {'wall_idx': t['wall_idx'], 'ratio': t['ratio'], 'side': t['side'], 'tag_num': t['id'], 'id': []}
                    self.create_visual_tag(new_tag)
                    self.april_tags.append(new_tag)

            # Restore Zones
            for z in state["zones"]:
                self.recreate_zone(z['name'], z['points'])

            self.status.config(text="Project Loaded Successfully.")

        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def get_real_wall_index(self, internal_idx):
        # Helper to map sparse wall array (with Nones) to dense array for saving
        # This is tricky. Simplified: Save logic filters Nones. 
        # So we need to find what "rank" this wall is among active walls.
        active_walls = [w for w in self.walls if w is not None]
        if self.walls[internal_idx] in active_walls:
            return active_walls.index(self.walls[internal_idx])
        return -1

    def create_visual_tag(self, t):
        # Helper to draw tag without user interaction
        box = self.canvas.create_rectangle(0,0,0,0, fill="orange", outline="black", tags="tag")
        line = self.canvas.create_line(0,0,0,0, arrow=tk.LAST, fill="blue", tags="tag")
        txt = self.canvas.create_text(0,0, text=t['tag_num'], font=("Arial",8,"bold"), tags="tag")
        t['id'] = [box, line, txt]
        self.redraw_tag(t)

    def recreate_zone(self, name, points):
        poly = self.canvas.create_polygon(points, fill="#2ecc71", stipple="gray25", outline="#27ae60", width=2, tags="zone")
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        lbl = self.canvas.create_text(cx, cy, text=name, font=("Arial", 10, "bold"), fill="green", tags="zone")
        self.zones.append({'name': name, 'points': points, 'ids': [poly, lbl]})

    # --- Standard Builder Functions (Reused) ---
    def set_mode(self, mode):
        self.mode = mode
        self.zone_points = []
        self.canvas.delete("temp"); self.canvas.delete("temp_zone")
        self.status.config(text=f"Mode: {mode.upper()}")

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
        if self.mode == "draw_wall" and self.current_draw_start:
            sx, sy, snap_n, snap_w = self.get_smart_coords_with_info(event.x, event.y, exclude_start=True)
            self.canvas.delete(self.temp_line); self.canvas.delete(self.temp_text)
            if math.hypot(sx - self.current_draw_start[0], sy - self.current_draw_start[1]) > 5:
                if snap_w is not None and snap_n is None: snap_n = self.split_wall_at_point(snap_w, sx, sy)
                self.create_wall_from_coords(self.current_draw_start, (sx, sy))
            self.current_draw_start = None
        self.selected_node_idx = None

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
        r = 4; pt_id = self.canvas.create_oval(x-r, y-r, x+r, y+r, fill="#2ecc71", outline="black", tags="temp_zone")
        self.zone_points.append((x, y))
        if len(self.zone_points) > 1:
            self.canvas.create_line(self.zone_points[-2], self.zone_points[-1], fill="#2ecc71", dash=(2,2), tags="temp_zone")
            if math.hypot(x - self.zone_points[0][0], y - self.zone_points[0][1]) < 15 and len(self.zone_points) > 2: self.finish_zone()
    def finish_zone_shortcut(self, event):
        if self.mode == "create_zone" and len(self.zone_points) > 2: self.finish_zone()
    def finish_zone(self):
        name = simpledialog.askstring("Zone", "Name:")
        if name: self.recreate_zone(name, list(self.zone_points))
        self.canvas.delete("temp_zone"); self.zone_points = []
    
    # --- Deletion ---
    def delete_item_at(self, x, y):
        clicked = self.canvas.find_closest(x, y, halo=5); 
        if not clicked: return
        tags = self.canvas.gettags(clicked[0])
        if "wall" in tags:
            for i, w in enumerate(self.walls):
                if w and w['id'] == clicked[0]: self.remove_wall(i); break
        elif "tag" in tags: self.remove_tag_by_id(clicked[0])
        elif "zone" in tags:
             for z in self.zones:
                 if clicked[0] in z['ids']:
                     for cid in z['ids']: self.canvas.delete(cid)
                     self.zones.remove(z); break
        elif "node" in tags:
             for i, n in enumerate(self.nodes):
                 if n['id'] == clicked[0]:
                     walls_copy = list(n['connections'])
                     for wid in walls_copy: self.remove_wall(wid)
                     self.canvas.delete(n['id']); n['id'] = None; break

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
                    if n['id'] == item: self.selected_node_idx = i; return

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

if __name__ == "__main__":
    root = tk.Tk()
    app = SaveLoadMapBuilder(root)
    root.mainloop()