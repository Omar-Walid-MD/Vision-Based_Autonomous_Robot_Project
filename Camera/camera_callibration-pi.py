import cv2
import numpy as np
import time
import os
import sys
sys.path.append('/usr/lib/python3/dist-packages')
from picamera2 import Picamera2


# === Parameters ===
CHECKERBOARD = (9, 6)  # inner corners (9 columns, 6 rows)
SQUARE_SIZE = 25 # millimeters or any consistent unit

SAVE_DIR = "calib_images"
CALIB_FILE = "camera_calib.npz"

# Create save folder if it doesn't exist
os.makedirs(SAVE_DIR, exist_ok=True)

# Prepare object points (0,0,0), (1,0,0), ..., (8,5,0)
objp = np.zeros((CHECKERBOARD[0]*CHECKERBOARD[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)
objp *= SQUARE_SIZE  # scale to real-world units

objpoints = []  # 3D points in real world
imgpoints = []  # 2D points in image plane

# === Step 1: Capture images ===

picam2 = Picamera2()
sensor_mode_res = (2304,1296)  # Mode 1

config = picam2.create_preview_configuration(
    main={"size": sensor_mode_res,"format": "RGB888"},
    raw={"size": sensor_mode_res}
)
picam2.configure(config)
picam2.start()

time.sleep(0.5)

cv2.namedWindow("Camera", cv2.WINDOW_NORMAL)  # allow resizing
cv2.resizeWindow("Camera", 1280, 720)         # set fixed window size


print("[INFO] Press 's' to save an image, 'q' to quit and calibrate")

img_count = 0

while True:
    frame = picam2.capture_array()
    if frame is None:   # check if capture failed
        break
    
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

    

    cv2.imshow("Camera", frame)
    key = cv2.waitKey(1)

    if key == ord('s'):
        print("before searching for corners")

        found, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)

        print("after searching for corners")

        if found:

            img_path = os.path.join(SAVE_DIR, f"calib_{img_count}.jpg")
            cv2.imwrite(img_path, frame)
            print(f"[INFO] Saved {img_path}")
            objpoints.append(objp.copy())
            imgpoints.append(corners)
            img_count += 1
        else:
            print("not found")

    elif key == ord('q'):
        break

picam2.stop()
cv2.destroyAllWindows()

if len(objpoints) < 5:
    print("[ERROR] Not enough images for calibration. Need at least 5.")
    exit()

# === Step 2: Run calibration ===
ret, K, dist, rvecs, tvecs = cv2.calibrateCamera(
    objpoints, imgpoints, gray.shape[::-1], None, None
)

print("\n=== Calibration Results ===")
print("Camera matrix (K):\n", K)
print("Distortion coefficients:\n", dist.ravel())

# === Save calibration to file ===
np.savez(CALIB_FILE, camera_matrix=K, dist_coeffs=dist)
print(f"[INFO] Calibration saved to {CALIB_FILE}")
