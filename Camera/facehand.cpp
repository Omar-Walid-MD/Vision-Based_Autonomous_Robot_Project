#include <opencv2/opencv.hpp>
#include <iostream>
using namespace cv;
using namespace std;

// g++ -std=c++11 -o facehand facehand.cpp `pkg-config --cflags --libs opencv4`

int main()
{
    // ================= GStreamer Pipeline for Raspberry Pi Camera =================
    std::string pipeline = "libcamerasrc ! "
                           "video/x-raw,width=1280,height=720,framerate=30/1 ! "
                           "v4l2convert ! "
                           "video/x-raw,format=BGR ! "
                           "appsink";

    VideoCapture cap(pipeline, CAP_GSTREAMER);
    
    if (!cap.isOpened())
    {
        cout << "Error: Cannot open Raspberry Pi Camera with GStreamer pipeline!" << endl;
        return -1;
    }

    // Load face cascade
    CascadeClassifier face_cascade;
    if (!face_cascade.load("haarcascade_frontalface_default.xml"))
    {
        cout << "Error loading face cascade\n";
        return -1;
    }

    Mat frame, hsv, mask;

    cout << "Press ESC to exit..." << endl;

    while (true)
    {
        cap >> frame;
        if (frame.empty())
        {
            cout << "Empty frame!" << endl;
            break;
        }

        // ================= FACE DETECTION =================
        vector<Rect> faces;
        face_cascade.detectMultiScale(frame, faces, 1.1, 5, 0, Size(80, 80));
        
        for (auto &f : faces)
        {
            rectangle(frame, f, Scalar(255, 0, 0), 2);
            putText(frame, "Face", Point(f.x, f.y - 10),
                    FONT_HERSHEY_SIMPLEX, 0.7, Scalar(255, 0, 0), 2);
        }

        // ================= HAND DETECTION (Skin Color) =================
        cvtColor(frame, hsv, COLOR_BGR2HSV);
        
        Scalar lower(0, 30, 60);
        Scalar upper(20, 150, 255);
        inRange(hsv, lower, upper, mask);

        GaussianBlur(mask, mask, Size(5, 5), 0);
        erode(mask, mask, Mat(), Point(-1, -1), 2);
        dilate(mask, mask, Mat(), Point(-1, -1), 2);

        vector<vector<Point>> contours;
        findContours(mask, contours, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE);

        for (auto &cnt : contours)
        {
            double area = contourArea(cnt);
            if (area > 5000)
            {
                Rect handRect = boundingRect(cnt);
                rectangle(frame, handRect, Scalar(0, 255, 0), 2);
                putText(frame, "Hand", Point(handRect.x, handRect.y - 10),
                        FONT_HERSHEY_SIMPLEX, 0.7, Scalar(0, 255, 0), 2);
            }
        }

        imshow("Face + Hand Detection - Pi Camera", frame);

        if (waitKey(1) == 27)  // ESC key
            break;
    }

    cap.release();
    destroyAllWindows();
    return 0;
}
