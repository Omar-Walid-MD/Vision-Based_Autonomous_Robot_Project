import cv2
import numpy as np
import os
import time
from dotenv import load_dotenv

# ----------------- Environment -----------------
load_dotenv()
platform = os.getenv("PLATFORM")

if platform == "RPI":
    import sys
    sys.path.append('/usr/lib/python3/dist-packages')
    from picamera2 import Picamera2

# ----------------- Parameters -----------------
CHECKERBOARD = (9, 6)
SQUARE_SIZE = 25  # mm

SAVE_DIR = "calib_images"
CALIB_FILE_NPZ = "camera_calib.npz"
CALIB_FILE_YAML = "camera_calib.yaml"

os.makedirs(SAVE_DIR, exist_ok=True)

# ----------------- Prepare Object Points -----------------
objp = np.zeros((CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)
objp *= SQUARE_SIZE

objpoints = []
imgpoints = []

# ----------------- Camera Setup -----------------
if platform == "RPI":
    print("[INFO] Using Picamera2 backend")

    picam2 = Picamera2()
    sensor_mode_res = (2304, 1296)

    config = picam2.create_preview_configuration(
        main={"size": sensor_mode_res, "format": "RGB888"},
        raw={"size": sensor_mode_res}
    )
    picam2.configure(config)
    picam2.start()

    time.sleep(0.5)

    def get_frame():
        frame = picam2.capture_array()
        if frame is None:
            return None, None
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        return frame, gray

else:
    print("[INFO] Using OpenCV VideoCapture backend")

    cap = cv2.VideoCapture(0)

    def get_frame():
        ret, frame = cap.read()
        if not ret:
            return None, None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return frame, gray

# ----------------- UI Setup -----------------
cv2.namedWindow("Calibration", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Calibration", 1280, 720)

print("[INFO] Press 's' to save image | 'q' to calibrate")

img_count = 0

# ----------------- Capture Loop -----------------
while True:
    frame, gray = get_frame()

    if frame is None:
        print("[ERROR] Failed to capture frame")
        break

    # Try detecting corners live (for visualization only)
    found, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)

    display = frame.copy()
    if found:
        cv2.drawChessboardCorners(display, CHECKERBOARD, corners, found)

    cv2.imshow("Calibration", display)
    key = cv2.waitKey(1)

    if key == ord('s'):
        if found:
            img_path = os.path.join(SAVE_DIR, f"calib_{img_count}.jpg")
            cv2.imwrite(img_path, frame)

            objpoints.append(objp.copy())
            imgpoints.append(corners)

            print(f"[INFO] Saved {img_path}")
            img_count += 1
        else:
            print("[WARN] Chessboard not detected")

    elif key == ord('q'):
        break

# ----------------- Cleanup -----------------
if platform == "RPI":
    picam2.stop()
else:
    cap.release()

cv2.destroyAllWindows()

# ----------------- Calibration -----------------
if len(objpoints) < 5:
    print("[ERROR] Need at least 5 valid images")
    exit()

ret, K, dist, rvecs, tvecs = cv2.calibrateCamera(
    objpoints, imgpoints, gray.shape[::-1], None, None
)

print("\n=== Calibration Results ===")
print("Camera matrix (K):\n", K)
print("Distortion coefficients:\n", dist.ravel())

# ----------------- Save NPZ -----------------
np.savez(CALIB_FILE_NPZ, camera_matrix=K, dist_coeffs=dist)
print(f"[INFO] Saved {CALIB_FILE_NPZ}")

# ----------------- Save YAML -----------------
fs = cv2.FileStorage(CALIB_FILE_YAML, cv2.FILE_STORAGE_WRITE)
fs.write("camera_matrix", K)
fs.write("dist_coeffs", dist)
fs.release()

print(f"[INFO] Saved {CALIB_FILE_YAML}")