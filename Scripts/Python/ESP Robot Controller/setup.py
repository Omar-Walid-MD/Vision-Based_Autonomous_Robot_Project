import cx_Freeze

cx_Freeze.setup(
    name="Robot Bluetooth Control",
    options={"build_exe": {"packages":["customtkinter"]}},
    executables = [cx_Freeze.Executable("robot_bluetooth_control.py",
    base="Win32GUI",
    target_name="Robot Bluetooth Control.exe")]

)
