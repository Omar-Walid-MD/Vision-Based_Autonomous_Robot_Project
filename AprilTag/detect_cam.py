import cv2
import numpy as np
import socketio
import json


# === Load camera calibration ===
data = np.load("camera_calib.npz")
camera_matrix = data["camera_matrix"]
dist_coeffs = data["dist_coeffs"]

# === AprilTag detection setup ===
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
parameters = cv2.aruco.DetectorParameters()

detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

# === Define tag size (in meters) ===
tag_size = 0.095

# === Open webcam ===
cap = cv2.VideoCapture(0)

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
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 0, 0), 2)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    corners, ids, _ = detector.detectMarkers(gray)

    if ids is not None:
        for corner, tag_id in zip(corners, ids.flatten()):
            # Estimate pose
            rvec, tvec, _ = cv2.aruco.estimatePoseSingleMarkers(
                corner, tag_size, camera_matrix, dist_coeffs
            )

            draw_pose_info(frame, rvec[0], tvec[0], tag_id, corner)

            # Draw marker boundary
            cv2.polylines(frame, [corner.astype(int)], True, (0, 255, 0), 2)

    cv2.imshow("AprilTag Pose Estimation", frame)
    if cv2.waitKey(1) == 27:  # ESC
        break

cap.release()
cv2.destroyAllWindows()
