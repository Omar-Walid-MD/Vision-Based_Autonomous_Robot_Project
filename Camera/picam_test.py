from picamera2 import Picamera2
import cv2
import time

# Create camera object
picam2 = Picamera2()

sensor_mode_res = (1536,864)
# sensor_mode_res = (2304,1296)
# sensor_mode_res = (4608,2592)

# Output size you want to send to OpenCV (keep same aspect ratio!)

config = picam2.create_preview_configuration(
    main={"size": sensor_mode_res, "format": "RGB888"},
    raw={"size": sensor_mode_res}  # Force the quarter-resolution sensor mode
)

picam2.configure(config)
picam2.start()



time.sleep(0.5)  # allow camera to warm up

cv2.namedWindow("Camera", cv2.WINDOW_NORMAL)  # allow resizing
cv2.resizeWindow("Camera", 1280, 720)         # set fixed window size


while True:
    frame = picam2.capture_array()  # Get frame as a NumPy array (RGB888)

    # Convert to BGR for OpenCV
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

    cv2.imshow("Camera",frame_gray)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

picam2.stop()
cv2.destroyAllWindows()
