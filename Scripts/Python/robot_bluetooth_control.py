import customtkinter as ctk  # pip install customtkinter
import serial #pip install pyserial
import threading
import time

# -----------------------------
# Configuration
# -----------------------------
SERIAL_PORT = "COM7"
BAUD_RATE = 9600

controls = {
    "w": "F",
    "a": "L",
    "s": "B",
    "d": "R",
    "m": "M",
    "n": "N"
}

controls_keyup = {"w": "0", "a": "0", "s": "0", "d": "0","m":"0","n":"0"}

# -----------------------------
# App Class
# -----------------------------
class RobotRemoteApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Robot Remote Control")
        self.geometry("600x500")

        self.bt = None
        self.connected = False
        self.stop_threads = False
        self.error_var = ctk.StringVar(value="")

        # Top Frame: Connect Button + Status
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(fill="x", pady=5)

        self.connect_btn = ctk.CTkButton(top_frame, text="Connect", command=self.connect_bluetooth)
        self.connect_btn.pack(side="left", padx=10)

        self.status_label = ctk.CTkLabel(top_frame, text="Disconnected", text_color="red")
        self.status_label.pack(side="left", padx=10)

        # Middle Frame: Controls
        controls_frame = ctk.CTkFrame(self)
        controls_frame.pack(pady=10)

        self.key_labels = {}
        for i, key in enumerate(controls.keys()):
            lbl = ctk.CTkLabel(controls_frame, text=key.upper(), width=50, height=50, fg_color="gray30")
            lbl.grid(row=0, column=i, padx=5, pady=5)
            self.key_labels[key] = lbl

        # Terminal Output
        terminal_frame = ctk.CTkFrame(self)
        terminal_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.terminal = ctk.CTkTextbox(terminal_frame, wrap="word",state="disabled")
        self.terminal.pack(fill="both", expand=True)

        # Input + Send
        input_frame = ctk.CTkFrame(self)
        input_frame.pack(fill="x", pady=5)

        self.input_entry = ctk.CTkEntry(input_frame, placeholder_text="Type command...")
        self.input_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.send_btn = ctk.CTkButton(input_frame, text="Send", command=self.send_text_input)
        self.send_btn.pack(side="left", padx=5)

        # Error Label
        self.error_label = ctk.CTkLabel(self, textvariable=self.error_var, text_color="red")
        self.error_label.pack(side="bottom", pady=5)

        # Key bindings
        self.bind_all("<KeyPress>", self.on_keydown)
        self.bind_all("<KeyRelease>", self.on_keyup)

    # -----------------------------
    # Bluetooth Functions
    # -----------------------------
    def log_to_terminal(self, text):
        self.terminal.configure(state="normal")       # allow editing
        self.terminal.insert("end", text + "\n")      # append new line
        self.terminal.see("end")                      # auto scroll
        self.terminal.configure(state="disabled")     # back to read-only

    def connect_bluetooth(self):
        try:
            self.bt = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)
            self.connected = True
            self.status_label.configure(text="Connected", text_color="green")
            self.error_var.set("")
            # Start receiving thread
            threading.Thread(target=self.receive_bluetooth, daemon=True).start()
        except Exception as e:
            self.error_var.set(f"Connection failed: {e}")
            self.status_label.configure(text="Disconnected", text_color="red")
            self.connected = False

    def send_to_bluetooth(self, data):
        if self.connected and self.bt:
            try:
                self.bt.write(str(data).encode())
                self.log_to_terminal(f"Sent: {data}")
            except Exception as e:
                self.error_var.set(f"Send failed: {e}")
        else:
            self.error_var.set("Not connected to Bluetooth.")

    def receive_bluetooth(self):
        while self.connected and not self.stop_threads:
            try:
                if self.bt.in_waiting:
                    data = self.bt.readline().decode(errors="ignore").strip()
                    if data:
                        self.log_to_terminal(f"Received: {data}")
            except Exception as e:
                self.error_var.set(f"Receive failed: {e}")
                break

    # -----------------------------
    # Key Handling
    # -----------------------------
    def on_keydown(self, event):
        key = event.keysym.lower()
        if self.input_entry.focus_get() == self.input_entry._entry:
            if key == "return":
                self.send_text_input()
            return  # Ignore when typing in text box

        if key in controls:
            self.send_to_bluetooth(controls[key])
            self.key_labels[key].configure(fg_color="green")

    def on_keyup(self, event):
        if self.input_entry.focus_get() == self.input_entry._entry:
            return
        key = event.keysym.lower()
        if key in controls_keyup:
            self.send_to_bluetooth(controls_keyup[key])
            self.key_labels[key].configure(fg_color="gray30")

    def send_text_input(self):
        text = self.input_entry.get().strip()
        if text:
            self.send_to_bluetooth(text)
            self.input_entry.delete(0, "end")

    def on_closing(self):
        self.stop_threads = True
        if self.bt and self.bt.is_open:
            self.bt.close()
        self.destroy()


# -----------------------------
# Run App
# -----------------------------
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    app = RobotRemoteApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
