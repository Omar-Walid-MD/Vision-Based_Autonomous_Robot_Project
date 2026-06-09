import customtkinter as ctk
import asyncio
import threading
import time
from bleak import BleakClient, BleakScanner, BleakError
import math
import struct
# -----------------------------
# BLE Configuration
# -----------------------------
DEVICE_NAME = "ESP32_BLE"           # Must match ESP32 name
DEVICE_ADDRESS = "80:65:99:DF:4C:89"  # Replace with your actual MAC
SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # Write
TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # Notify

controls = {
    "w": "F",
    "a": "L",
    "s": "B",
    "d": "R"
}

controls_keyup = {"w": "S", "a": "S", "s": "S", "d": "S", "m": "S", "n": "S"}

parameters = [
    {"key": "kp", "label": "K Proportional", "value": ""},
    {"key": "ki", "label": "K Integral", "value": ""},
    {"key": "kd", "label": "K Derivative", "value": ""},
    {"key": "ms", "label": "Max Speed", "value": ""},
]

# -----------------------------
# App Class
# -----------------------------
class RobotRemoteApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Robot Remote Control (BLE)")
        self.geometry("600x600")
        
        self.pressed_keys = set()  # 👈 keep track of currently pressed keys

        self.client = None
        self.connected = False
        self.stop_threads = False
        self.loop = asyncio.new_event_loop()

        self.error_var = ctk.StringVar(value="")
        
        # -----------------------------
        # Sensor state
        # -----------------------------
        self.current_angle = 0

        self.motor_speed = {
            0: 0,
            1: 0
        }
        
        self.command_history = []
        self.history_index = -1
        
        self.parameters = parameters
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=5)
        self.grid_rowconfigure(3, weight=1)

        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)

        # Top Frame
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)

        top_frame.grid_columnconfigure(0, weight=1)
        top_frame.grid_columnconfigure(1, weight=1)
        top_frame.grid_columnconfigure(2, weight=1)

        self.connect_btn = ctk.CTkButton(top_frame, text="Connect BLE", command=self.start_ble_thread)
        self.connect_btn.grid(row=0, column=1, padx=10)

        self.status_label = ctk.CTkLabel(top_frame, text="Disconnected", text_color="red")
        self.status_label.grid(row=0, column=2, padx=10)

        # Controls
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=1, column=0, columnspan=2, pady=0)
    
    
        self.key_labels = {}
        for i, key in enumerate(controls.keys()):
            lbl = ctk.CTkLabel(controls_frame, text=key.upper(), width=50, height=50, fg_color="gray30")
            lbl.grid(row=0, column=i, padx=5, pady=5)
            self.key_labels[key] = lbl
            
    
        
   

        # Terminal
        terminal_frame = ctk.CTkFrame(self)
        terminal_frame.grid(row=2, column=0, rowspan=2, sticky="nsew", padx=10, pady=10)

        self.terminal = ctk.CTkTextbox(terminal_frame, wrap="word", state="disabled")
        self.terminal.pack(fill="both", expand=True)
        
        side_frame = ctk.CTkFrame(self)
        side_frame.grid(row=2, column=1, rowspan=2, sticky="nsew", padx=10, pady=10)

        side_frame.grid_rowconfigure(0, weight=1)
        side_frame.grid_rowconfigure(1, weight=1)
        
        
        compass_frame = ctk.CTkFrame(side_frame)
        compass_frame.grid(row=0, column=0, sticky="nsew")

        self.compass_size = 150
        self.compass_center = self.compass_size // 2

        self.compass = ctk.CTkCanvas(
            compass_frame,
            width=self.compass_size,
            height=self.compass_size,
            bg="black",
            highlightthickness=0
        )
        self.compass.pack()
        
        self.compass.create_oval(
            5, 5,
            self.compass_size - 5,
            self.compass_size - 5,
            outline="white",
            width=2
        )

        self.compass.create_text(
            self.compass_center,
            15,
            text="N",
            fill="white",
            font=("Arial", 12, "bold")
        )

        self.needle = self.compass.create_line(
            self.compass_center,
            self.compass_center,
            self.compass_center,
            20,
            fill="red",
            width=3
        )
        
        
        speed_frame = ctk.CTkFrame(side_frame)
        speed_frame.grid(row=1, column=0, sticky="nsew")
        
        self.speed_canvas = ctk.CTkCanvas(
            speed_frame,
            width=300,
            height=180,
            bg="black",
            highlightthickness=0
        )
        self.speed_canvas.pack(fill="both", expand=True)
        
        self.speed_canvas.create_text(150, 10, text="Speed (km/h ×100)", fill="white",font=("Arial", 14, "bold"))

        self.bar0 = self.speed_canvas.create_rectangle(60, 150, 120, 150, fill="red")
        self.bar1 = self.speed_canvas.create_rectangle(180, 150, 240, 150, fill="blue")

        self.text0 = self.speed_canvas.create_text(90, 160,text="M0: 0",fill="white",font=("Arial", 12, "bold"))
        self.text1 = self.speed_canvas.create_text(210, 160,text="M1: 0",fill="white",font=("Arial", 12, "bold"))
        
        params_frame = ctk.CTkFrame(side_frame)
        params_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        
        side_frame.grid_rowconfigure(0, weight=1)  # compass
        side_frame.grid_rowconfigure(1, weight=1)  # speed graph
        side_frame.grid_rowconfigure(2, weight=0)  # parameters
        
        self.param_entries = {}

        for row, param in enumerate(self.parameters):
            label = ctk.CTkLabel(
                params_frame,
                text=param["label"],
                anchor="w"
            )
            label.grid(row=row, column=0, sticky="w", padx=5, pady=2)

            entry = ctk.CTkEntry(params_frame, width=80)
            entry.grid(row=row, column=1, padx=5, pady=2)

            if param["value"]:
                entry.insert(0, str(param["value"]))

            entry.bind(
                "<Return>",
                lambda event, p=param, e=entry:
                    self.send_parameter(p["key"], e)
            )

            self.param_entries[param["key"]] = entry

        # Input + Send
        input_frame = ctk.CTkFrame(self)
        input_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=5)
        
        input_frame.grid_columnconfigure(0, weight=1)

        self.input_entry = ctk.CTkEntry(input_frame, placeholder_text="Type command...")
        self.input_entry.grid(row=0, column=0, sticky="ew", padx=5)
        
        self.input_entry.bind("<Up>", self.history_up)
        self.input_entry.bind("<Down>", self.history_down)

        self.send_btn = ctk.CTkButton(input_frame, text="Send", command=self.send_text_input)
        self.send_btn.grid(row=0, column=1, padx=5)
        
        self.error_label = ctk.CTkLabel(input_frame,textvariable=self.error_var,text_color="red")
        self.error_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=5)

        # Bindings
        self.bind_all("<KeyPress>", self.on_keydown)
        self.bind_all("<KeyRelease>", self.on_keyup)
        self.bind_all("<Escape>", self.on_escape)

    # -----------------------------
    # Terminal Logger
    # -----------------------------
    def log_to_terminal(self, text):
        self.terminal.configure(state="normal")
        self.terminal.insert("end", text + "\n")
        self.terminal.see("end")
        self.terminal.configure(state="disabled")

    # -----------------------------
    # BLE Logic
    # -----------------------------
    def start_ble_thread(self):
        if self.connected:
            return

        threading.Thread(target=self.run_ble_loop, daemon=True).start()

    def run_ble_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.ble_connect())

    async def ble_connect(self):
        self.status_label.configure(text="Connecting...", text_color="orange")

        try:
            devices = await BleakScanner.discover(timeout=5.0)

            device = None
            for d in devices:
                if d.name == DEVICE_NAME:
                    device = d
                    break
            if not device:
                raise Exception("Device not found")

            self.client = BleakClient(device)

            await self.client.connect(timeout=10.0)

            self.connected = True
            self.status_label.configure(text="Connected", text_color="green")
            self.error_var.set("")
            self.log_to_terminal(f"✅ Connected to {DEVICE_NAME}")

            # Start notifications
            await self.client.start_notify(TX_UUID, self.notification_handler)

            # Keep alive loop
            while self.connected and self.client.is_connected:
                await asyncio.sleep(0.2)

        except Exception as e:
            self.log_to_terminal(f"⚠️ Connection error: {e}")
            self.error_var.set(str(e))

        finally:
            await self.cleanup_ble()
            
    async def cleanup_ble(self):
        if self.client:
            try:
                if self.client.is_connected:
                    await self.client.stop_notify(TX_UUID)
                    await self.client.disconnect()
            except Exception as e:
                self.log_to_terminal(f"Cleanup error: {e}")

        self.client = None
        self.connected = False

        self.status_label.configure(text="Disconnected", text_color="red")
        self.log_to_terminal("🔌 Disconnected")


    
    def notification_handler(self, sender, data):
        raw = list(data)

        if len(raw) == 0:
            return

        packet_id = raw[0]

        # -------------------------
        # SPEED PACKET (binary only)
        # -------------------------
        if packet_id == 0 and len(raw) >= 5:
            speedA = raw[1] | (raw[2] << 8)
            speedB = raw[3] | (raw[4] << 8)

            if speedA > 32767: speedA -= 65536
            if speedB > 32767: speedB -= 65536

            self.motor_speed[0] = abs(speedA)
            self.motor_speed[1] = abs(speedB)

            self.update_speed_graph()
            return

        

        if packet_id == ord('o') and len(raw) >= 9:
            odomA = struct.unpack_from("<i", bytes(raw), 1)[0]
            odomB = struct.unpack_from("<i", bytes(raw), 5)[0]

            self.log_to_terminal(f"ODOM A: {odomA}, ODOM B: {odomB}")
            return
        
        # -------------------------
        # YAW PACKET
        # -------------------------
        if packet_id == 3 and len(raw) >= 3:
            yaw = raw[1] | (raw[2] << 8)

            if yaw > 32767:
                yaw -= 65536

            self.current_angle = yaw
            self.update_compass()
            return

        # -------------------------
        # TEXT FALLBACK ONLY HERE
        # -------------------------
        try:
            msg = data.decode("utf-8")
            self.log_to_terminal(f"ESP → {msg}")
        except:
            self.log_to_terminal(f"ESP → <binary {len(raw)} bytes>")

    async def ble_send(self, message: str):
        if not self.client or not self.connected:
            self.error_var.set("Not connected to ESP32.")
            return
        try:
            await self.client.write_gatt_char(RX_UUID, message.encode("utf-8"), response=True)
            self.log_to_terminal(f"→ Sent: {message}")
            await asyncio.sleep(0.05)  # 🕐 Add a short delay (50 ms)
        except Exception as e:
            self.error_var.set(f"Send error: {e}")
            self.log_to_terminal(f"⚠️ Send error: {e}")

    def send_ble(self, message: str):
        if not self.connected or not self.client:
            self.error_var.set("Not connected to ESP32.")
            return

        asyncio.run_coroutine_threadsafe(self.ble_send(message), self.loop)
        
    def send_parameter(self, key, entry):
        value = entry.get().strip()

        if value == "":
            return

        try:
            float(value)
        except ValueError:
            self.error_var.set(f"Invalid value for {key}")
            return

        cmd = f"{key}{value}"

        self.send_ble(cmd)
        self.log_to_terminal(f"→ Sent: {cmd}")

    def update_compass(self):
        """Update compass needle. 0° = North, clockwise positive."""

        rad = math.radians(self.current_angle)

        length = self.compass_center - 15
        x = self.compass_center + length * math.sin(rad)
        y = self.compass_center - length * math.cos(rad)

        self.compass.coords(
            self.needle,
            self.compass_center,
            self.compass_center,
            x,
            y
        )

    def update_speed_graph(self):
        max_val = 500  # adjust scaling if needed

        def scale(v):
            return min(v / max_val, 1.0)

        m0 = self.motor_speed[0]
        m1 = self.motor_speed[1]

        h0 = 150 - (120 * scale(m0))
        h1 = 150 - (120 * scale(m1))

        # update bars
        self.speed_canvas.coords(self.bar0, 60, h0, 120, 150)
        self.speed_canvas.coords(self.bar1, 180, h1, 240, 150)

        # update labels
        self.speed_canvas.itemconfigure(self.text0, text=f"M0: {m0}")
        self.speed_canvas.itemconfigure(self.text1, text=f"M1: {m1}")
    # -----------------------------
    # Key Handling
    # -----------------------------
    def on_keydown(self, event):
        # Ignore repeats
        key = event.keysym.lower()
        if key in self.pressed_keys:
            return
        self.pressed_keys.add(key)

        if self.input_entry.focus_get() == self.input_entry._entry:
            if key == "return":
                self.send_text_input()
            return

        if key in controls:
            self.send_ble(controls[key])
            self.key_labels[key].configure(fg_color="green")

    def on_keyup(self, event):
        if self.input_entry.focus_get() == self.input_entry._entry:
            return
        key = event.keysym.lower()
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)
        if key in controls_keyup:
            self.send_ble(controls_keyup[key])
            self.key_labels[key].configure(fg_color="gray30")
            
    def on_escape(self, event):
        # Remove focus from input field
        self.focus_set()

        # Optional: visual feedback (clear cursor)
        self.input_entry.icursor(0)

    def send_text_input(self):
        text = self.input_entry.get().strip()

        if text:
            self.send_ble(text)

            # Store in history
            self.command_history.append(text)

            # Reset navigation index
            self.history_index = len(self.command_history)

            self.input_entry.delete(0, "end")
            
    def history_up(self, event=None):
        if not self.command_history:
            return

        # Move upward in history
        self.history_index = max(0, self.history_index - 1)

        cmd = self.command_history[self.history_index]

        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, cmd)


    def history_down(self, event=None):
        if not self.command_history:
            return

        # Move downward
        self.history_index = min(
            len(self.command_history),
            self.history_index + 1
        )

        self.input_entry.delete(0, "end")

        # If at newest position -> blank
        if self.history_index == len(self.command_history):
            return

        cmd = self.command_history[self.history_index]
        self.input_entry.insert(0, cmd)

    def on_closing(self):
        self.connected = False

        if self.loop and self.client:
            try:
                asyncio.run_coroutine_threadsafe(self.cleanup_ble(), self.loop)
            except:
                pass

        self.destroy()


# -----------------------------
# Run App
# -----------------------------
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    app = RobotRemoteApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
