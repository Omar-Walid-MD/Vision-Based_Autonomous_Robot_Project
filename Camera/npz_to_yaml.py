import numpy as np
import cv2

# Load the .npz file
data = np.load("camera_calib.npz")

# Print available keys so you can confirm the names
print("Keys in npz:", data.files)

# Adjust these names if your npz uses different keys
camera_matrix = data["camera_matrix"]
dist_coeffs = data["dist_coeffs"]

# Write to OpenCV-style YAML
fs = cv2.FileStorage("camera_calib.yaml", cv2.FILE_STORAGE_WRITE)

fs.write("camera_matrix", camera_matrix)
fs.write("dist_coeffs", dist_coeffs)

fs.release()

print("Created camera_calib.yaml")
