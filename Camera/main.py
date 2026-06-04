<<<<<<< HEAD
=======

>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
import cv2
import time
import argparse
import sys
import os
import numpy as np

<<<<<<< HEAD
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
=======
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # add parent folder to paths
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
from Server.Node import Node
print(cv2.__version__)

# ==========================
# Rotation Matrix to Euler
# ==========================
def rotation_matrix_to_euler_angles(R):
    sy = np.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
<<<<<<< HEAD
    singular = sy < 1e-6

    if not singular:
        roll  = np.arctan2(R[2, 1], R[2, 2])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw   = np.arctan2(R[1, 0], R[0, 0])
    else:
        roll  = np.arctan2(-R[1, 2], R[1, 1])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw   = 0
=======

    singular = sy < 1e-6

    if not singular:
        roll = np.arctan2(R[2, 1], R[2, 2])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw = np.arctan2(R[1, 0], R[0, 0])
    else:
        roll = np.arctan2(-R[1, 2], R[1, 1])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw = 0
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a

    return np.degrees([roll, pitch, yaw])


<<<<<<< HEAD
=======

>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
# ==========================
# Arguments
# ==========================
parser = argparse.ArgumentParser(description="Python AprilTag Camera Node")

<<<<<<< HEAD
parser.add_argument("--show", "-s", action="store_true", help="Show visualization window")
parser.add_argument("--camera", type=int, default=0, help="Camera index")
parser.add_argument("--width",  type=int, default=2304, help="Camera width")
parser.add_argument("--height", type=int, default=1296, help="Camera height")
parser.add_argument("--fps",    type=int, default=30,   help="Camera FPS")

args = parser.parse_args()

SHOW         = args.show
CAMERA_WIDTH = args.width
CAMERA_HEIGHT= args.height
CAMERA_FPS   = args.fps

OUTPUT_WIDTH  = 640
=======
parser.add_argument(
    "--show",
    "-s",
    action="store_true",
    help="Show visualization window"
)

parser.add_argument(
    "--camera",
    type=int,
    default=0,
    help="Camera index"
)

parser.add_argument(
    "--width",
    type=int,
    default=2304,
    help="Camera width"
)

parser.add_argument(
    "--height",
    type=int,
    default=1296,
    help="Camera height"
)

parser.add_argument(
    "--fps",
    type=int,
    default=30,
    help="Camera FPS"
)

args = parser.parse_args()

SHOW = args.show
CAMERA_WIDTH = args.width
CAMERA_HEIGHT = args.height
CAMERA_FPS = args.fps

# Output processing size
OUTPUT_WIDTH = 640
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
OUTPUT_HEIGHT = 360


# ==========================
# Camera Setup
# ==========================
cap = cv2.VideoCapture(args.camera)
<<<<<<< HEAD
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAMERA_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
cap.set(cv2.CAP_PROP_FPS,          CAMERA_FPS)
=======

cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a

if not cap.isOpened():
    print("Cannot open camera")
    exit()

print("Camera opened successfully")


# ==========================
# AprilTag Detector
# ==========================
<<<<<<< HEAD
aruco_dict   = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
aruco_params = cv2.aruco.DetectorParameters()
detector     = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)


# ==========================
# Calibration (.yaml)
# ==========================
fs = cv2.FileStorage("./Camera/camera_calib.yaml", cv2.FILE_STORAGE_READ)
camera_matrix = fs.getNode("camera_matrix").mat()
dist_coeffs   = fs.getNode("dist_coeffs").mat()
fs.release()

TAG_SIZE = 0.095

# 3D object points for a single tag
OBJ_POINTS = np.array([
    [-TAG_SIZE / 2,  TAG_SIZE / 2, 0],
    [ TAG_SIZE / 2,  TAG_SIZE / 2, 0],
    [ TAG_SIZE / 2, -TAG_SIZE / 2, 0],
    [-TAG_SIZE / 2, -TAG_SIZE / 2, 0]
], dtype=np.float32)


=======
aruco_dict = cv2.aruco.getPredefinedDictionary(
    cv2.aruco.DICT_APRILTAG_36h11
)

aruco_params = cv2.aruco.DetectorParameters()

detector = cv2.aruco.ArucoDetector(
    aruco_dict,
    aruco_params
)


# ==========================
# Calibration (.npz)
# ==========================
calib = np.load("./Camera/camera_calib.npz")

camera_matrix = calib["camera_matrix"]
dist_coeffs = calib["dist_coeffs"]

fx = camera_matrix[0, 0]
fy = camera_matrix[1, 1]
cx = camera_matrix[0, 2]
cy = camera_matrix[1, 2]

TAG_SIZE = 0.095

>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
# ==========================
# Socket Node
# ==========================
node = Node("camera0")


# ==========================
# Window
# ==========================
if SHOW:
    cv2.namedWindow("AprilTag Detection", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("AprilTag Detection", 1280, 720)


# ==========================
<<<<<<< HEAD
# FPS + Tag Records
# ==========================
frame_count = 0
start_time  = time.time()

tag_frame_count  = {}
=======
# FPS Measurement
# ==========================
frame_count = 0
start_time = time.time()

# ==========================
# Tag check records
# ==========================
tag_frame_count = {}

>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
TAG_APPROVED_COUNT = 3


# ==========================
# Main Loop
# ==========================
while True:

    ret, frame = cap.read()

    if not ret:
        print("Failed to read frame")
        break

<<<<<<< HEAD
    # Resize for display only
    resized = cv2.resize(frame, (OUTPUT_WIDTH, OUTPUT_HEIGHT), interpolation=cv2.INTER_LINEAR)

    # Convert to grayscale for detection
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    corners, ids, _ = detector.detectMarkers(gray)

=======
    # ===================================================
    # Resize ONCE (same scaling strategy as current C++)
    # ===================================================
    resized = cv2.resize(
        frame,
        (OUTPUT_WIDTH, OUTPUT_HEIGHT),
        interpolation=cv2.INTER_LINEAR
    )

    scale_up_x = CAMERA_WIDTH / OUTPUT_WIDTH
    scale_up_y = CAMERA_HEIGHT / OUTPUT_HEIGHT

    # ===================================================
    # Convert BGR -> Gray
    # ===================================================
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    corners, ids, rejected = detector.detectMarkers(gray)
    
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
    detected_tag_ids = []

    if ids is not None:

<<<<<<< HEAD
        # Estimate pose for each marker
        rvecs, tvecs = [], []
        for corner in corners:
            _, rvec, tvec = cv2.solvePnP(
                OBJ_POINTS,
                corner[0],
                camera_matrix,
                dist_coeffs
            )
            rvecs.append(rvec)
            tvecs.append(tvec)
=======
        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners,
            TAG_SIZE,
            camera_matrix,
            dist_coeffs
        )
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a

        for i in range(len(ids)):

            marker_id = ids[i][0]
<<<<<<< HEAD
=======
            
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
            detected_tag_ids.append(marker_id)

            rvec = rvecs[i]
            tvec = tvecs[i]

            # Draw marker border
<<<<<<< HEAD
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)

            # ==========================
            # Rotation matrix to Euler
            # ==========================
            R, _ = cv2.Rodrigues(rvec)

            sy = np.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
            singular = sy < 1e-6

            if not singular:
                pitch = np.arctan2(R[2, 1], R[2, 2])
                yaw   = np.arctan2(-R[2, 0], sy)
                roll  = np.arctan2(R[1, 0], R[0, 0])
            else:
                pitch = np.arctan2(-R[1, 2], R[1, 1])
                yaw   = np.arctan2(-R[2, 0], sy)
                roll  = 0
=======
            cv2.aruco.drawDetectedMarkers(
                frame,
                corners,
                ids
            )
            

            # ==========================
            # Rotation matrix
            # ==========================
            R, _ = cv2.Rodrigues(rvec)

            sy = np.sqrt(R[0,0] * R[0,0] + R[1,0] * R[1,0])

            singular = sy < 1e-6

            if not singular:
                pitch = np.arctan2(R[2,1], R[2,2])
                yaw = np.arctan2(-R[2,0], sy)
                roll = np.arctan2(R[1,0], R[0,0])
            else:
                pitch = np.arctan2(-R[1,2], R[1,1])
                yaw = np.arctan2(-R[2,0], sy)
                roll = 0
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a

            roll  = np.degrees(roll)
            pitch = np.degrees(pitch)
            yaw   = np.degrees(yaw)

<<<<<<< HEAD
            print("ID:",       marker_id)
            print("Position:", tvec.flatten())
            print("Roll:",     roll)
            print("Pitch:",    pitch)
            print("Yaw:",      yaw)
            print("-------------------")

            if SHOW:
                cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, TAG_SIZE * 0.5)
=======
            distance = np.linalg.norm(tvec)

            print("ID:", marker_id)
            print("Position:", tvec.flatten())
            print("Roll:", roll)
            print("Pitch:", pitch)
            print("Yaw:", yaw)
            print("-------------------")

            if SHOW:
                
                # Draw pose axes
                cv2.drawFrameAxes(
                    frame,
                    camera_matrix,
                    dist_coeffs,
                    rvec,
                    tvec,
                    TAG_SIZE * 0.5
                )
                
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
                cv2.putText(
                    frame,
                    f"ID {marker_id}",
                    tuple(corners[i][0][0].astype(int)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
<<<<<<< HEAD
                    (0, 255, 0),
                    2
                )

            # ==========================
            # Tag approval logic
            # ==========================
            if tag_frame_count.get(marker_id, None):
                tag_frame_count[marker_id] += 1

                if tag_frame_count[marker_id] >= TAG_APPROVED_COUNT:
=======
                    (0,255,0),
                    2
                )
        
        
            if tag_frame_count.get(marker_id,None):
                tag_frame_count[marker_id] += 1
                
                if tag_frame_count[marker_id] >= TAG_APPROVED_COUNT:
                    
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
                    payload = {
                        "id": int(marker_id),
                        "pose": {
                            "position": tvec.flatten().tolist(),
<<<<<<< HEAD
                            "rotation": [float(roll), float(pitch), float(yaw)]
                        }
                    }
                    node.send("camera/tag_found", payload)
            else:
                tag_frame_count[marker_id] = 1

    # Remove tags no longer in frame
    tags_to_remove = [tid for tid in tag_frame_count if tid not in detected_tag_ids]
    for tid in tags_to_remove:
        tag_frame_count.pop(tid, None)

    # ==========================
    # FPS Measurement
    # ==========================
    frame_count += 1

    if frame_count >= 60:
        now      = time.time()
        duration = now - start_time
        fps      = frame_count / duration

        print(f"Resolution: {CAMERA_WIDTH}x{CAMERA_HEIGHT} | FPS: {fps:.2f}")

        frame_count = 0
        start_time  = now

    # ==========================
    # Display
    # ==========================
    if SHOW:
        cv2.imshow("AprilTag Detection", frame)
        key = cv2.waitKey(1)
=======
                            "rotation": [
                                float(roll),
                                float(pitch),
                                float(yaw)
                            ]
                        }
                    }
                    
                    node.send("camera/tags_found", payload)
            else:
                tag_frame_count[marker_id] = 1


    tags_to_remove = [id for id in tag_frame_count if id not in detected_tag_ids] 
    for id in tags_to_remove:
        tag_frame_count.pop(id,None)

    # ===================================================
    # FPS Measurement
    # ===================================================
    frame_count += 1

    if frame_count >= 60:
        now = time.time()
        duration = now - start_time

        fps = frame_count / duration

        print(
            f"Resolution: {CAMERA_WIDTH}x{CAMERA_HEIGHT} | "
            f"FPS: {fps:.2f}"
        )

        frame_count = 0
        start_time = now

    # ===================================================
    # Display
    # ===================================================
    if SHOW:
        cv2.imshow("AprilTag Detection", frame)

        key = cv2.waitKey(1)

>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
        if key == 27 or key == ord('q'):
            break


# ==========================
# Cleanup
# ==========================
cap.release()
cv2.destroyAllWindows()
<<<<<<< HEAD
print("Stopped")
=======

print("Stopped")
>>>>>>> 0b57e37d9717749f83a50d66b04c4878df578a8a
