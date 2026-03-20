import cv2
import time
import mediapipe as mp
from picamera2 import Picamera2

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

picam2 = Picamera2()

sensor_mode_res = (2304,1296)  # Mode 1

config = picam2.create_preview_configuration(
	main={"size": sensor_mode_res,"format": "RGB888"},
	raw={"size": sensor_mode_res}
)
picam2.configure(config)
picam2.start()
cap = picam2
time.sleep(0.5)

window_name = "Hospital Robot Vision"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)


while True:
    frame = cap.capture_array()
    if frame is None:
        break
    factor = 0.5
    frame = cv2.resize(frame, (0,0), fx=factor, fy=factor)


    h, w, _ = frame.shape
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # ===== Hands =====
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

    # ===== Faces (Multiple) =====
    face_results = face_detection.process(rgb)
    if face_results.detections:
        for detection in face_results.detections:
            mp_draw.draw_detection(frame, detection)
            # ~ bbox = detection.location_data.relative_bounding_box

            # ~ x1 = int(bbox.xmin * w)
            # ~ y1 = int(bbox.ymin * h)
            # ~ bw = int(bbox.width * w)
            # ~ bh = int(bbox.height * h)

            # ~ cv2.rectangle(
                # ~ frame,
                # ~ (x1, y1),
                # ~ (x1 + bw, y1 + bh),
                # ~ (255, 0, 0),
                # ~ 5
            # ~ )


            # ~ fx = x1 + bw // 2
            # ~ fy = y1 + int(bh * 0.2)

            # ~ cv2.circle(frame, (fx, fy), 15, (255, 0, 0), -1)
            

    cv2.imshow(window_name, frame)
    cv2.resizeWindow(window_name, 1280, 720)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
