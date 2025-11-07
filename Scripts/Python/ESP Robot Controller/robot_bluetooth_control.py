import customtkinter as ctk
import asyncio
import threading
import time
from bleak import BleakClient, BleakScanner, BleakError

# -----------------------------
# BLE Configuration
# -----------------------------
DEVICE_NAME = "ESP32_ROBOT"           # Must match ESP32 name
DEVICE_ADDRESS = "80:65:99:DF:4C:89"  # Replace with your actual MAC
SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # Write
TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # Notify

controls = {
    "w": "F",
    "a": "L",
    "s": "B",
    "d": "R",
    "m": "M",
    "n": "N"
}

controls_keyup = {"w": "S", "a": "S", "s": "S", "d": "S", "m": "S", "n": "S"}


# -----------------------------
# App Class
# -----------------------------
class RobotRemoteApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Robot Remote Control (BLE)")
        self.geometry("600x500")
        
        self.pressed_keys = set()  # 👈 keep track of currently pressed keys

        self.client = None
        self.connected = False
        self.stop_threads = False
        self.loop = asyncio.new_event_loop()

        self.error_var = ctk.StringVar(value="")

        # Top Frame
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(fill="x", pady=5)

        self.connect_btn = ctk.CTkButton(top_frame, text="Connect BLE", command=self.start_ble_thread)
        self.connect_btn.pack(side="left", padx=10)

        self.status_label = ctk.CTkLabel(top_frame, text="Disconnected", text_color="red")
        self.status_label.pack(side="left", padx=10)

        # Controls
        controls_frame = ctk.CTkFrame(self)
        controls_frame.pack(pady=10)
        self.key_labels = {}
        for i, key in enumerate(controls.keys()):
            lbl = ctk.CTkLabel(controls_frame, text=key.upper(), width=50, height=50, fg_color="gray30")
            lbl.grid(row=0, column=i, padx=5, pady=5)
            self.key_labels[key] = lbl

        # Terminal
        terminal_frame = ctk.CTkFrame(self)
        terminal_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.terminal = ctk.CTkTextbox(terminal_frame, wrap="word", state="disabled")
        self.terminal.pack(fill="both", expand=True)

        # Input + Send
        input_frame = ctk.CTkFrame(self)
        input_frame.pack(fill="x", pady=5)
        self.input_entry = ctk.CTkEntry(input_frame, placeholder_text="Type command...")
        self.input_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.send_btn = ctk.CTkButton(input_frame, text="Send", command=self.send_text_input)
        self.send_btn.pack(side="left", padx=5)

        self.error_label = ctk.CTkLabel(self, textvariable=self.error_var, text_color="red")
        self.error_label.pack(side="bottom", pady=5)

        # Bindings
        self.bind_all("<KeyPress>", self.on_keydown)
        self.bind_all("<KeyRelease>", self.on_keyup)

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
        threading.Thread(target=self.run_ble_loop, daemon=True).start()

    def run_ble_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.ble_connect())

    async def ble_connect(self):
        self.status_label.configure(text="Connecting...", text_color="orange")
        try:
            device = await BleakScanner.find_device_by_address(DEVICE_ADDRESS, timeout=5.0)
            if not device:
                raise Exception("Device not found")

            async with BleakClient("80:65:99:DF:4C:89") as client:
                self.client = client
                self.connected = True
                self.status_label.configure(text="Connected", text_color="green")
                self.error_var.set("")
                self.log_to_terminal(f"✅ Connected to {DEVICE_NAME}")

                # Set up notifications
                await client.start_notify(TX_UUID, self.notification_handler)

                # Keep connection alive
                while self.connected:
                    await asyncio.sleep(0.1)

        except BleakError as e:
            self.log_to_terminal(f"❌ BLE Error: {e}")
            self.error_var.set(f"BLE Error: {e}")
        except Exception as e:
            self.log_to_terminal(f"⚠️ Connection failed: {e}")
            self.error_var.set(str(e))
        finally:
            self.connected = False
            self.status_label.configure(text="Disconnected", text_color="red")

    def notification_handler(self, sender, data):
        msg = data.decode("utf-8", errors="ignore")
        self.log_to_terminal(f"ESP → {msg}")

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
        if not self.connected:
            self.error_var.set("Not connected to ESP32.")
            return
        asyncio.run_coroutine_threadsafe(self.ble_send(message), self.loop)

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

    def send_text_input(self):
        text = self.input_entry.get().strip()
        if text:
            self.send_ble(text)
            self.input_entry.delete(0, "end")

    def on_closing(self):
        self.stop_threads = True
        self.connected = False
        if self.client:
            try:
                asyncio.run_coroutine_threadsafe(self.client.disconnect(), self.loop)
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
