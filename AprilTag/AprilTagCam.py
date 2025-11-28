import cv2
import numpy as np
import os
import time

this_directory = os.path.dirname(os.path.abspath(__file__))

class AprilTagCam:
    
    def __init__(self,show=False):
        
        self.platform = os.getenv("PLATFORM")
        
        data = np.load(os.path.join(this_directory,"./camera_calib.npz"))
        self.camera_matrix = data["camera_matrix"]
        self.dist_coeffs = data["dist_coeffs"]
        
        self.tag_size = 0.095
        self.width = 640
        self.height = 480
        
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
        
        if self.platform == "RPI":
            from picamera2 import Picamera2
            picam2 = Picamera2()
            
            self.parameters = cv2.aruco.DetectorParameters_create()
            self.detector = cv2.aruco
            
            config = picam2.create_video_configuration(
                main={"size": (self.width, self.height), "format": "YUV420"}, 
                controls={"FrameDurationLimits": (16666, 16666)},  # ~60 FPS
                sensor={"output_size": (2304, 1296)}
            )
            picam2.configure(config)
            picam2.set_controls({"ExposureTime": 15000, "AnalogueGain": 8.0})
            picam2.start()
            self.cap = picam2
        else:
            self.parameters = cv2.aruco.DetectorParameters()

            self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)
        
            self.cap = cv2.VideoCapture(0)
        
        self.show = show

        
    
    def detect(self):
        
        frame = None
        gray = None
        
        if self.platform == "RPI":
            frame = self.cap.capture_array()
            if frame is None:   # check if capture failed
                return
            gray = frame[:self.height, :self.width]

        else:
            ret, frame = self.cap.read()
            if not ret:
                return False
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


        if self.show:
            cv2.imshow("April Tag Detection",frame)
            time.sleep(0.01)

        corners = None
        ids = None
        
        if self.platform == "RPI":
            corners, ids, _ = self.detector.detectMarkers(frame, self.aruco_dict, parameters=self.parameters)
        else:
            corners, ids, _ = self.detector.detectMarkers(gray)    
                
        if ids is not None:
            for corner, tag_id in zip(corners, ids.flatten()):
                rvec, tvec, _ = cv2.aruco.estimatePoseSingleMarkers(
                    corner, self.tag_size, self.camera_matrix, self.dist_coeffs
                )
                
                rvec = rvec[0]
                tvec = tvec[0]
                
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
                

                tag_data = {
                    "time": time.time_ns() // 1_000_000,
                    "id": int(tag_id),
                    "position": [
                        float(tvec[0][0]),
                        float(tvec[0][1]),
                        float(tvec[0][2])
                    ],
                    "rotation": [
                        float(angles[0]),
                        float(angles[1]),
                        float(angles[2])
                    ]
                }
                
                return tag_data
        else:
            return False        
                

    def close(self):
        print("Releasing camera...")
        if self.platform == "RPI":
            self.cap.stop()
            self.cap.close()
        
