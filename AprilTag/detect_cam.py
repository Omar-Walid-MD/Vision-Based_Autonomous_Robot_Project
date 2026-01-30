import cv2
import numpy as np
import socketio
import json
import sys
import time
sys.path.append('/usr/lib/python3/dist-packages')
from picamera2 import Picamera2
import cv2.aruco as aruco


# === Load camera calibration ===
data = np.load("camera_calib.npz")
camera_matrix = data["camera_matrix"]
dist_coeffs = data["dist_coeffs"]

# === AprilTag detection setup ===
dictionary = aruco.getPredefinedDictionary(aruco.DICT_APRILTAG_36h11)
parameters = aruco.DetectorParameters_create()


# === Define tag size (in meters) ===
tag_size = 0.095
scale_factor = 0.25

# ----------------------------
# Initialize Camera
# ----------------------------
picam2 = Picamera2()

# sensor_mode_res = (1536, 864)  # Mode 0 (quarter-res, cropped)
sensor_mode_res = (2304,1296)  # Mode 1
# sensor_mode_res = (4608,2592)  # Mode 2

preview_res = (640, 360)         # Fast preview

config = picam2.create_preview_configuration(
    main={"size": sensor_mode_res, "format": "RGB888"},
    raw={"size": sensor_mode_res}
)

picam2.configure(config)
picam2.start()

time.sleep(0.5)  # warm-up

cv2.namedWindow("Camera", cv2.WINDOW_NORMAL)  # allow resizing
cv2.resizeWindow("Camera", 1280, 720)         # set fixed window size

prev_time = time.time()
fps = 0

# === Open webcam ===
# picam2.set_controls({"ExposureTime": 15000, "AnalogueGain": 8.0})

def draw_pose_info(img, rvec, tvec, tag_id, corner):
    cv2.drawFrameAxes(img, camera_matrix, dist_coeffs, rvec, tvec, 0.05)

    # Tag center
    center = np.mean(corner.reshape(-1, 2), axis=0).astype(int)

    # Convert rotation to Euler angles
    R, _ = cv2.Rodrigues(rvec)
    sy = np.sqrt(R[0,0]**2 + R[1,0]**2)
    singular = sy < 1e-6
    if not singular:
        x = np.arctan2(R[2,1], R[2,2])
        y = np.arctan2(-R[2,0], sy)
        z = np.arctan2(R[1,0], R[0,0])
    else:
        x = np.arctan2(-R[1,2], R[1,1])
        y = np.arctan2(-R[2,0], sy)
        z = 0
    angles = np.degrees([x, y, z])

    info = f"ID:{tag_id} Pos:{tvec.ravel()} Rot(deg):{angles.round(1)}"
    print(info)
    cv2.putText(img, info, (center[0] - 100, center[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2)

while True:
    # time.sleep(0.01)
    frame = picam2.capture_array()
    if frame is None:   # check if capture failed
        break

    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    frame_small = cv2.resize(frame, (0,0), fx=scale_factor, fy=scale_factor)

    corners, ids, rejected = aruco.detectMarkers(frame_small, dictionary, parameters=parameters)

    corners = [corner / scale_factor for corner in corners]

    if ids is not None:
        for corner, tag_id in zip(corners, ids.flatten()):
            # Estimate pose
            rvec, tvec, _ = cv2.aruco.estimatePoseSingleMarkers(
                corner, tag_size, camera_matrix, dist_coeffs
            )

            draw_pose_info(frame, rvec[0], tvec[0], tag_id, corner)

            # Draw marker boundary
            cv2.polylines(frame, [corner.astype(int)], True, (0, 255, 0), 2)

    curr_time = time.time()
    fps = 1.0 / (curr_time - prev_time)
    prev_time = curr_time
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    cv2.imshow("Camera", frame)
    if cv2.waitKey(1) == 27:  # ESC
        break

picam2.stop()
cv2.destroyAllWindows()
