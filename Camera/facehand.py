import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import cv2
import mediapipe as mp
import numpy as np
import time

# ==========================
# Init GStreamer
# ==========================
Gst.init(None)

# ==========================
# Camera calibration
# from camera_calib.yaml
# ==========================
fx = 496.46403905471658
fy = 504.89413233877974
cx = 313.51048466146784
cy = 135.25353105824394


FACE_REAL_WIDTH_M  = 0.14
HAND_REAL_WIDTH_M  = 0.08


def pixel_to_meter(px, py, Z, fx, fy, cx, cy):
    X = (px - cx) * Z / fx
    Y = (py - cy) * Z / fy
    return X, Y


def estimate_z(real_width_m, box_width_px, focal_length_px):
    """
    Z = (real_width * focal_length) / box_width_pixels
    """
    if box_width_px < 1:
        return None
    return (real_width_m * focal_length_px) / box_width_px

# ==========================
# MediaPipe setup
# ==========================
mp_hands        = mp.solutions.hands
mp_face_detect  = mp.solutions.face_detection
mp_draw         = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    max_num_hands=4,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

face_detection = mp_face_detect.FaceDetection(
    model_selection=0,
    min_detection_confidence=0.6
)

# ==========================
# GStreamer pipeline
# ==========================
pipeline_str = (
    "shmsrc socket-path=/tmp/camera_stream is-live=true ! "
    "video/x-raw,format=BGR,width=640,height=360,framerate=15/1 ! "
    "appsink name=sink emit-signals=true max-buffers=1 drop=true sync=false"
)

pipeline = Gst.parse_launch(pipeline_str)
appsink  = pipeline.get_by_name("sink")

pipeline.set_state(Gst.State.PLAYING)
time.sleep(0.5)

window_name = "Hospital Robot Vision"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

try:
    while True:
        sample = appsink.emit("pull-sample")

        if sample is None:
            continue

        buffer    = sample.get_buffer()
        caps      = sample.get_caps()
        structure = caps.get_structure(0)

        width  = structure.get_value("width")
        height = structure.get_value("height")

        success, map_info = buffer.map(Gst.MapFlags.READ)

        if not success:
            continue

        try:
            frame = np.ndarray(
                (height, width, 3),
                dtype=np.uint8,
                buffer=map_info.data
            ).copy()
        finally:
            buffer.unmap(map_info)

        rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = frame.shape[:2]

        # ==========================
        # Hand Detection
        # ==========================
        hand_results = hands.process(rgb)

        best_hand       = None
        best_hand_lms   = None
        best_hand_area  = 0

        if hand_results.multi_hand_landmarks:
            for hand_landmarks in hand_results.multi_hand_landmarks:

                xs = [lm.x * w for lm in hand_landmarks.landmark]
                ys = [lm.y * h for lm in hand_landmarks.landmark]

                x_min, x_max = min(xs), max(xs)
                y_min, y_max = min(ys), max(ys)

                area = (x_max - x_min) * (y_max - y_min)

                if area > best_hand_area:
                    best_hand_area = area
                    best_hand      = (x_min, y_min, x_max, y_max)
                    best_hand_lms  = hand_landmarks

        if best_hand_lms is not None:
            x_min, y_min, x_max, y_max = best_hand

            mp_draw.draw_landmarks(
                frame,
                best_hand_lms,
                mp_hands.HAND_CONNECTIONS
            )

            wrist    = best_hand_lms.landmark[0]
            center_x = int(wrist.x * w)
            center_y = int(wrist.y * h)

            cv2.circle(frame, (center_x, center_y), 6, (0, 0, 255), -1)

            box_w = x_max - x_min
            Z     = estimate_z(HAND_REAL_WIDTH_M, box_w, fx)

            if Z is not None:
                X, Y = pixel_to_meter(center_x, center_y, Z, fx, fy, cx, cy)

                print(f"[HAND]  X={X:.3f}m  Y={Y:.3f}m  Z={Z:.3f}m")

                cv2.putText(
                    frame,
                    f"Hand Z={Z:.2f}m",
                    (int(x_min), int(y_min) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

            cv2.rectangle(
                frame,
                (int(x_min), int(y_min)),
                (int(x_max), int(y_max)),
                (0, 255, 0),
                2
            )

        # ==========================
        # Face Detection
        # ==========================
        face_results = face_detection.process(rgb)

        best_face      = None
        best_face_area = 0

        if face_results.detections:
            for detection in face_results.detections:
                bbox = detection.location_data.relative_bounding_box

                bx = int(bbox.xmin * w)
                by = int(bbox.ymin * h)
                bw = int(bbox.width  * w)
                bh = int(bbox.height * h)

                area = bw * bh

                if area > best_face_area:
                    best_face_area = area
                    best_face      = (bx, by, bw, bh, detection)

        if best_face is not None:
            bx, by, bw, bh, detection = best_face

            mp_draw.draw_detection(frame, detection)

            center_x = bx + bw // 2
            center_y = by + bh // 2

            Z = estimate_z(FACE_REAL_WIDTH_M, bw, fx)

            if Z is not None:
                X, Y = pixel_to_meter(center_x, center_y, Z, fx, fy, cx, cy)

                print(f"[FACE]  X={X:.3f}m  Y={Y:.3f}m  Z={Z:.3f}m")

                cv2.putText(
                    frame,
                    f"Face Z={Z:.2f}m",
                    (bx, by - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 100, 0),
                    2
                )

        cv2.imshow(window_name, frame)
        cv2.resizeWindow(window_name, 1280, 720)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break

finally:
    pipeline.set_state(Gst.State.NULL)
    cv2.destroyAllWindows()