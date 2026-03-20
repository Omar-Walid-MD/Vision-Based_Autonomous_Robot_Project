# convert_npz_to_yaml.py
import numpy as np
import cv2

data = np.load("camera_calib.npz")

# Change these two lines to match YOUR actual keys from print_keys.py
camera_matrix = data['camera_matrix']
dist_coeffs = data['dist_coeffs']

fs = cv2.FileStorage("camera_calib.yaml", cv2.FILE_STORAGE_WRITE)
fs.write("camera_matrix", camera_matrix)
fs.write("dist_coeffs", dist_coeffs)
fs.release()

print("done")
