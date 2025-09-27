import json
import cv2
import numpy as np

class AprilTagCam:
    
    def __init__(self,show=False):
        data = np.load("camera_calib.npz")
        self.camera_matrix = data["camera_matrix"]
        self.dist_coeffs = data["dist_coeffs"]
        
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
        self.parameters = cv2.aruco.DetectorParameters()

        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)

        self.tag_size = 0.095

        # === Open webcam ===
        self.cap = cv2.VideoCapture(0)
        
        self.show = show

        
    
    def detect(self):
        ret, frame = self.cap.read()
        if not ret:
            return False

        if self.show:
            cv2.imshow("April Tag Detection",frame)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
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
                    "tag_id": int(tag_id),
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
                