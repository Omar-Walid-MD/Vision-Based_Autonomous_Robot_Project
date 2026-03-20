import cv2
import numpy as np
import glob
import os

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
cap = cv2.VideoCapture(0)
print("[INFO] Press 's' to save an image, 'q' to quit and calibrate")

img_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    found, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)

    if found:
        cv2.drawChessboardCorners(frame, CHECKERBOARD, corners, found)

    cv2.imshow("Calibration", frame)
    key = cv2.waitKey(1)

    if key == ord('s') and found:
        img_path = os.path.join(SAVE_DIR, f"calib_{img_count}.jpg")
        cv2.imwrite(img_path, frame)
        print(f"[INFO] Saved {img_path}")
        objpoints.append(objp.copy())
        imgpoints.append(corners)
        img_count += 1

    elif key == ord('q'):
        break

cap.release()
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
