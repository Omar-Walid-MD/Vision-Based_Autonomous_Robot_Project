import time
from picamera2 import Picamera2

# Initialize camera
picam2 = Picamera2()

# Configure for video (higher FPS than preview)
picam2.configure(
    picam2.create_video_configuration(main={"size": (640, 480)})
)

picam2.start()

# Warm up
time.sleep(1)

print("[INFO] Measuring FPS for 5 seconds...")
frames = 0
t0 = time.time()

while time.time() - t0 < 5:
    frame = picam2.capture_array()
    frames += 1

elapsed = time.time() - t0
fps = frames / elapsed

print(f"[RESULT] Captured {frames} frames in {elapsed:.2f} seconds")
print(f"[RESULT] Approx. FPS = {fps:.2f}")
