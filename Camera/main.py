import cv2
import numpy as np
import time
import os
from dotenv import load_dotenv

# ----------------- Environment -----------------
load_dotenv()
platform = os.getenv("PLATFORM")

if platform == "RPI":
    import sys
    sys.path.append('/usr/lib/python3/dist-packages')
    from picamera2 import Picamera2

import cv2.aruco as aruco

# ----------------- Load Calibration -----------------
data = np.load("camera_calib.npz")
camera_matrix = data["camera_matrix"]
dist_coeffs = data["dist_coeffs"]

# ----------------- AprilTag Setup -----------------
dictionary = aruco.getPredefinedDictionary(aruco.DICT_APRILTAG_36h11)
parameters = aruco.DetectorParameters_create()

tag_size = 0.095  # meters
scale_factor = 0.25

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

# ----------------- UI -----------------
cv2.namedWindow("Camera", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Camera", 1280, 720)

prev_time = time.time()

# ----------------- Pose Drawing -----------------
def draw_pose_info(img, rvec, tvec, tag_id, corner):
    cv2.drawFrameAxes(img, camera_matrix, dist_coeffs, rvec, tvec, 0.05)

    center = np.mean(corner.reshape(-1, 2), axis=0).astype(int)

    # Rotation → Euler
    R, _ = cv2.Rodrigues(rvec)
    sy = np.sqrt(R[0, 0]**2 + R[1, 0]**2)
    singular = sy < 1e-6

    if not singular:
        x = np.arctan2(R[2, 1], R[2, 2])
        y = np.arctan2(-R[2, 0], sy)
        z = np.arctan2(R[1, 0], R[0, 0])
    else:
        x = np.arctan2(-R[1, 2], R[1, 1])
        y = np.arctan2(-R[2, 0], sy)
        z = 0

    angles = np.degrees([x, y, z])

    info = f"ID:{tag_id} Pos:{tvec.ravel()} Rot:{angles.round(1)}"
    print(info)

    cv2.putText(img, info,
                (center[0] - 100, center[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                2)

# ----------------- Main Loop -----------------
while True:
    frame, gray = get_frame()

    if frame is None:
        print("[ERROR] Frame capture failed")
        break

    # Downscale for faster detection
    small = cv2.resize(gray, (0, 0), fx=scale_factor, fy=scale_factor)

    corners, ids, rejected = aruco.detectMarkers(
        small, dictionary, parameters=parameters
    )

    if corners:
        corners = [corner / scale_factor for corner in corners]

    if ids is not None:
        for corner, tag_id in zip(corners, ids.flatten()):
            rvec, tvec, _ = cv2.aruco.estimatePoseSingleMarkers(
                corner, tag_size, camera_matrix, dist_coeffs
            )

            draw_pose_info(frame, rvec[0], tvec[0], tag_id, corner)

            cv2.polylines(frame, [corner.astype(int)], True, (0, 255, 0), 2)

    # FPS calculation
    curr_time = time.time()
    fps = 1.0 / (curr_time - prev_time)
    prev_time = curr_time

    cv2.putText(frame, f"FPS: {fps:.1f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2)

    cv2.imshow("Camera", frame)

    if cv2.waitKey(1) == 27:  # ESC
        break

# ----------------- Cleanup -----------------
if platform == "RPI":
    picam2.stop()
else:
    cap.release()

cv2.destroyAllWindows()