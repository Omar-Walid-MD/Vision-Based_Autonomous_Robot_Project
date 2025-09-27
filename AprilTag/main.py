from AprilTagCam import AprilTagCam

if __name__ == "__main__":
    cam = AprilTagCam(True)
    while True:
        result = cam.detect()
        print(result)
        