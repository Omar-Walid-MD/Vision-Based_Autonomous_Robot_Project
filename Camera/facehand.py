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
# MediaPipe setup
# ==========================
mp_hands = mp.solutions.hands
mp_face_detection = mp.solutions.face_detection
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

face_detection = mp_face_detection.FaceDetection(
    model_selection=0,
    min_detection_confidence=0.6
)

# ==========================
# GStreamer shared-memory pipeline
# Must match the caps sent by your C++ appsrc
# ==========================
pipeline_str = (
    "shmsrc socket-path=/tmp/camera_stream is-live=true ! "
    "video/x-raw,format=YV12,width=2304,height=1296 ! "
    "appsink name=sink emit-signals=true max-buffers=1 drop=true sync=false"
)

pipeline = Gst.parse_launch(pipeline_str)
appsink = pipeline.get_by_name("sink")

pipeline.set_state(Gst.State.PLAYING)

# Give the stream a moment to start
time.sleep(0.5)

window_name = "Hospital Robot Vision"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

try:
    while True:
        sample = appsink.emit("pull-sample")

        if sample is None:
            continue

        buffer = sample.get_buffer()
        caps = sample.get_caps()
        structure = caps.get_structure(0)

        width = structure.get_value("width")
        height = structure.get_value("height")

        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            continue

        try:
            frame = np.ndarray(
                (height, width),
                dtype=np.uint8,
                buffer=map_info.data
            ).copy()
        finally:
            buffer.unmap(map_info)

        # ==========================
        # Downscale for MediaPipe speed
        # ==========================
        factor = 0.5
        # ~ frame = cv2.resize(frame, (0, 0), fx=factor, fy=factor)

        h, w = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)

        # ==========================
        # Hands
        # ==========================
        hand_results = hands.process(rgb)

        if hand_results.multi_hand_landmarks:
            for hand_landmarks in hand_results.multi_hand_landmarks:
                mp_draw.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS
                )

                lm = hand_landmarks.landmark[8]
                x, y = int(lm.x * w), int(lm.y * h)
                cv2.circle(frame, (x, y), 6, (0, 0, 255), -1)

        # ==========================
        # Face Detection
        # ==========================
        face_results = face_detection.process(rgb)

        if face_results.detections:
            for detection in face_results.detections:
                mp_draw.draw_detection(frame, detection)

        cv2.imshow(window_name, frame)
        cv2.resizeWindow(window_name, 1280, 720)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break

finally:
    pipeline.set_state(Gst.State.NULL)
    cv2.destroyAllWindows()

