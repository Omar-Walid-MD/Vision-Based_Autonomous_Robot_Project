#include <opencv2/opencv.hpp>
#include <iostream>
#include <chrono>
#include <opencv2/calib3d.hpp>
//~ #include <nlohmann/json.hpp>
#include <gst/app/gstappsink.h>
#include <gst/app/gstappsrc.h>
#include <signal.h>

//~ #include "Node.h"

extern "C" {
#include <apriltag/apriltag.h>
#include <apriltag/tag36h11.h>
#include <apriltag/common/image_u8.h>
#include <apriltag/apriltag_pose.h>

}



using namespace cv;
using namespace std;

// compilation command without node:
// g++ main.cpp -o apriltag `pkg-config --cflags --libs opencv4 gstreamer-1.0 gstreamer-app-1.0` -lapriltag -lpthread -std=c++17 -Wall
    
// compilation command with node
// g++ main.cpp Node.cpp -o main \
    `pkg-config --cflags --libs opencv4 gstreamer-1.0 gstreamer-app-1.0` \
    -I/usr/local/include \
    -L/usr/local/lib -lsioclient \
    -lboost_system -lboost_thread -lssl -lcrypto \
    -lapriltag -lpthread \
    -std=c++17 -Wall
    
// ==========================
// Rotation Matrix to Euler
// ==========================
Vec3d rotationMatrixToEulerAngles(Mat R)
{
    double sy = sqrt(R.at<double>(0,0)*R.at<double>(0,0) +
                     R.at<double>(1,0)*R.at<double>(1,0));

    bool singular = sy < 1e-6;

    double roll, pitch, yaw;

    if (!singular)
    {
        roll  = atan2(R.at<double>(2,1), R.at<double>(2,2));
        pitch = atan2(-R.at<double>(2,0), sy);
        yaw   = atan2(R.at<double>(1,0), R.at<double>(0,0));
    }
    else
    {
        roll  = atan2(-R.at<double>(1,2), R.at<double>(1,1));
        pitch = atan2(-R.at<double>(2,0), sy);
        yaw   = 0;
    }

    return Vec3d(roll*180/CV_PI,
                 pitch*180/CV_PI,
                 yaw*180/CV_PI);
}


GstElement *global_input_pipe = nullptr;
GstElement *global_output_pipe = nullptr;


void handle_sigint(int)
{
    std::cout << "\nStopping...\n";

    if (global_input_pipe)
    {
        gst_element_set_state(global_input_pipe, GST_STATE_NULL);
        gst_object_unref(global_input_pipe);
    }

    if (global_output_pipe)
    {
        gst_element_set_state(global_output_pipe, GST_STATE_NULL);
        gst_object_unref(global_output_pipe);
    }

    system("rm -f /tmp/camera_stream*");

    exit(0);
}


int main(int argc, char* argv[]) {
    
    // Parse command-line argument for --show or -s
    bool show = false;
    double detect_scale = 0.25;

    
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];

        if (arg == "--scale" || arg == "-scale") {
            if (i + 1 < argc) {
                detect_scale = std::atof(argv[++i]);
                if (detect_scale <= 0.0 || detect_scale > 1.0) {
                    std::cerr << "Invalid scale value. Using default 0.5\n";
                    detect_scale = 0.25;
                }
            }
        }
        else if (arg == "--no-show" || arg == "--headless") {
            show = false;
        }
        else if (arg == "--show" || arg == "-s") {
            show = true;
        }
    }

    if (show) {
        std::cout << "Display enabled (--show)\n";
    } else {
        std::cout << "Display disabled (run with --show or -s to enable)\n";
    }

    // GStreamer pipeline (high-res mode + hardware conversion)
    // You can change resolution/framerate here
    //~ std::string pipeline = "libcamerasrc ! "
                           //~ "video/x-raw,width=2304,height=1296,framerate=50/1 ! "
                           //~ "v4l2convert ! "
                           //~ "video/x-raw,format=BGR ! "
                           //~ "appsink";
                           
    //~ std::string pipeline = "libcamerasrc ! "
       //~ "video/x-raw,width=2304,height=1296,framerate=50/1 ! "
       //~ "v4l2convert ! "
       //~ "video/x-raw,format=YV12 ! "
       //~ "appsink";
       
       
    gst_init(&argc, &argv);
    
    signal(SIGINT, handle_sigint);
    
       
    std::string input_pipeline = "libcamerasrc ! queue max-size-buffers=1 leaky=downstream ! "
    "video/x-raw,width=2304,height=1296,framerate=30/1 ! "
    "v4l2convert ! "
    "video/x-raw,format=YV12 ! "
    "appsink name=camera_sink drop=true max-buffers=1 sync=false";
    
    std::string output_pipeline =
    "appsrc name=python_src is-live=true block=false format=time ! "
    "video/x-raw,format=BGR,width=640,height=360,framerate=30/1 ! "
    "queue leaky=2 max-size-buffers=2 ! "
    "shmsink socket-path=/tmp/camera_stream sync=false wait-for-connection=false";
    
    GError *err = nullptr;

    GstElement *input_pipe = gst_parse_launch(input_pipeline.c_str(), &err);
    if (!input_pipe) {
        std::cerr << "Failed to create input pipeline: "
                  << (err ? err->message : "unknown") << std::endl;
        return -1;
    }

    GstElement *output_pipe = gst_parse_launch(output_pipeline.c_str(), &err);
    if (!output_pipe) {
        std::cerr << "Failed to create output pipeline: "
                  << (err ? err->message : "unknown") << std::endl;
        return -1;
    }

    GstElement *appsink = gst_bin_get_by_name(GST_BIN(input_pipe), "camera_sink");
    GstElement *appsrc  = gst_bin_get_by_name(GST_BIN(output_pipe), "python_src");

    if (!appsink) {
        std::cerr << "Could not find camera_sink\n";
        return -1;
    }

    if (!appsrc) {
        std::cerr << "Could not find python_src\n";
        return -1;
    }

    gst_element_set_state(input_pipe, GST_STATE_PLAYING);
    gst_element_set_state(output_pipe, GST_STATE_PLAYING);
    
    global_input_pipe = input_pipe;
    global_output_pipe = output_pipe;
                           


    //~ std::cout << "Opening pipeline...\n";

    //~ cv::VideoCapture cap(pipeline, cv::CAP_GSTREAMER);

    //~ std::cout << "After constructor\n";

    //~ if (!cap.isOpened()) {
        //~ std::cerr << "Cannot open camera\n";
        //~ return -1;
    //~ }

    //~ std::cout << "Opened successfully\n";

    apriltag_family_t *tf = tag36h11_create();
    apriltag_detector_t *td = apriltag_detector_create();
    apriltag_detector_add_family(td, tf);

    td->quad_decimate = 1.0;      // No decimation
    td->quad_sigma    = 0.0;
    td->nthreads      = 2;        // Use 2 threads (good for Pi 4)
    td->debug         = 0;
    td->refine_edges  = 1;
    
    FileStorage fs("camera_calib.yaml", FileStorage::READ);

    Mat cameraMatrix, distCoeffs;
    fs["camera_matrix"] >> cameraMatrix;
    fs["dist_coeffs"] >> distCoeffs;
    fs.release();

    double fx = cameraMatrix.at<double>(0,0);
    double fy = cameraMatrix.at<double>(1,1);
    double cx = cameraMatrix.at<double>(0,2);
    double cy = cameraMatrix.at<double>(1,2);

    double tag_size = 0.095; // meters

    //~ SocketNode my_node("camera");
    
    if(show)
    {
        cv::namedWindow("AprilTag Detection", cv::WINDOW_NORMAL);
        cv::resizeWindow("AprilTag Detection", 720, 405); 
    }

    
    // Inside the detection loop, after getting 'det'

    //~ cv::Mat frame;

    // FPS measurement
    int frame_count = 0;
    auto start_time = std::chrono::steady_clock::now();

    while (true) {
        auto loop_start = std::chrono::steady_clock::now();

        //~ cap >> frame;
        //~ if (frame.empty()) {
            //~ std::cerr << "Blank frame grabbed\n";
            //~ break;
        //~ }
        
        GstSample *sample = gst_app_sink_pull_sample(GST_APP_SINK(appsink));

        GstBuffer *buffer = gst_sample_get_buffer(sample);
        GstMapInfo map;
        gst_buffer_map(buffer, &map, GST_MAP_READ);

        cv::Mat frame(1296, 2304, CV_8UC1, (void*)map.data);

        

        
        // Method 1: convert to gray (39 FPS)
        //~ cv::Mat gray;
        //~ cv::cvtColor(frame, gray, cv::COLOR_BGR2GRAY);
        
        int y_height = frame.rows * 2 / 3;  // For YUV420 formats, Y is exactly 2/3 of total buffer height
        cv::Mat gray(frame, cv::Rect(0, 0, frame.cols, y_height));
        
        double scale_up_x = 1.0 / detect_scale;  // = 4.0 if detect_scale = 0.25
        double scale_up_y = 1.0 / detect_scale;  // usually same, unless non-uniform resize

        cv::resize(gray, gray, cv::Size(), detect_scale, detect_scale, cv::INTER_NEAREST);  // fastest
        
         
        if (!gray.isContinuous()) {
            gray = gray.clone();
        }
        
        image_u8_t im = {
            .width = gray.cols,
            .height = gray.rows,
            .stride = gray.cols,
            .buf = gray.data
        };

        zarray_t *detections = apriltag_detector_detect(td, &im);

        for (int i = 0; i < zarray_size(detections); i++)
        {
            apriltag_detection_t *det;
            zarray_get(detections, i, &det);

            // ================= Pose Estimation =================
            apriltag_detection_info_t info;
            info.det = det;
            info.tagsize = tag_size;
            info.fx = fx;
            info.fy = fy;
            info.cx = cx;
            info.cy = cy;

            // IMPORTANT: scale corners back to original image coordinates
            // (pose estimation needs original pixel coords, not scaled!)
            apriltag_detection_t scaled_det = *det;  // copy detection
            for (int j = 0; j < 4; j++) {
                scaled_det.p[j][0] *= scale_up_x;
                scaled_det.p[j][1] *= scale_up_y;
            }
            scaled_det.c[0] *= scale_up_x;
            scaled_det.c[1] *= scale_up_y;

            // Use scaled detection for pose
            info.det = &scaled_det;
            apriltag_pose_t pose;
            estimate_tag_pose(&info, &pose);

            Mat R(3,3,CV_64F, pose.R->data);
            Mat t(3,1,CV_64F, pose.t->data);

            // Euler Angles (unchanged)
            Vec3d euler = rotationMatrixToEulerAngles(R);
            double pitch = euler[0];
            double yaw   = euler[1];
            double roll  = euler[2];

            // Normalize yaw
            yaw = fmod((yaw + 180.0), 360.0);
            if (yaw < 0) yaw += 360.0;
            yaw -= 180.0;

            double distance = norm(t);

            cout << "X Y Z: " << t.t() << endl;
            cout << "Roll: " << roll << " Pitch: " << pitch << " Yaw: " << yaw << endl;
            cout << "------------------------" << endl;
            
            // Build JSON object
            //~ nlohmann::json j;
            
            //~ j["id"] = det->id;
            //~ j["pose"] = {
                //~ {"position", {t.at<double>(0), t.at<double>(1), t.at<double>(2)}},
                //~ {"rotation", {roll, pitch, yaw}}
            //~ };
            
            //~ my_node.send("apriltag_detected", j.dump());

            if (show)
            {
                // ================= Draw Border =================
                for (int j = 0; j < 4; j++)
                {
                    Point p1(
                        static_cast<int>(det->p[j][0] * scale_up_x),
                        static_cast<int>(det->p[j][1] * scale_up_y)
                    );
                    Point p2(
                        static_cast<int>(det->p[(j+1)%4][0] * scale_up_x),
                        static_cast<int>(det->p[(j+1)%4][1] * scale_up_y)
                    );
                    line(frame, p1, p2, Scalar(0,255,0), 2);
                }

                // ================= Draw Axis =================
                vector<Point3f> axis = {
                    Point3f(0,0,0),
                    Point3f(0.1,0,0),
                    Point3f(0,0.1,0),
                    Point3f(0,0,0.1)
                };
                vector<Point2f> imgpts;
                Mat rvec;
                Rodrigues(R, rvec);
                projectPoints(axis, rvec, t,
                              cameraMatrix, distCoeffs, imgpts);

                // Scale axis points back to original image size
                for (auto& pt : imgpts) {
                    pt.x *= scale_up_x;
                    pt.y *= scale_up_y;
                }

                line(frame, imgpts[0], imgpts[1], Scalar(0,0,255), 3);
                line(frame, imgpts[0], imgpts[2], Scalar(0,255,0), 3);
                line(frame, imgpts[0], imgpts[3], Scalar(255,0,0), 3);

                // ================= Display Values =================
                putText(frame, "Dist: " + to_string(distance) + " m",
                        Point(20,40), FONT_HERSHEY_SIMPLEX,
                        0.7, Scalar(255,255,255), 2);
                putText(frame, "Roll: " + to_string(roll),
                        Point(20,80), FONT_HERSHEY_SIMPLEX,
                        0.7, Scalar(0,255,0), 2);
                putText(frame, "Pitch: " + to_string(pitch),
                        Point(20,120), FONT_HERSHEY_SIMPLEX,
                        0.7, Scalar(255,0,0), 2);
                putText(frame, "Yaw: " + to_string(yaw),
                        Point(20,160), FONT_HERSHEY_SIMPLEX,
                        0.7, Scalar(0,0,255), 2);
            }
        }
        
       
       GstBuffer *out_buffer = gst_buffer_new_allocate(nullptr, map.size, nullptr);
       GstMapInfo out_map;
       gst_buffer_map(out_buffer, &out_map, GST_MAP_WRITE);
       memcpy(out_map.data, map.data, map.size);
       
       gst_buffer_unmap(out_buffer, &out_map);
       gst_app_src_push_buffer(GST_APP_SRC(appsrc), out_buffer);
       gst_buffer_unmap(buffer, &map);
       gst_sample_unref(sample);
            

    
        
        if (show) {
            
            if (frame_count == 0) {  // only on first frame
                cv::resizeWindow("AprilTag Detection", 720, 405);
                std::cout << "Window resized to 720x405\n";
            }
            cv::imshow("AprilTag Detection", gray);
        }
    
        
        
        // FPS measurement
        frame_count++;
        if (frame_count >= 60) {
            auto now = std::chrono::steady_clock::now();
            auto total_duration = std::chrono::duration_cast<std::chrono::milliseconds>(now - start_time).count();
            double fps = (frame_count * 1000.0) / total_duration;
            std::cout << "Resolution: " << frame.cols << "" << frame.rows
                      << "q | FPS: " << fps
                      << " (" << frame_count << " frames / " << total_duration << " ms)\n";
            frame_count = 0;
            start_time = now;
        }
        
        if(show)
        {
            
            // Wait only if displaying
            int key = cv::waitKey(show ? 1 : 1);  // still allow 'q' to quit even if no window
            if (key == 'q' || key == 27) break;
        }
    }

    // Cleanup
    apriltag_detector_destroy(td);
    tag36h11_destroy(tf);
    //~ cap.release();
    if(show) cv::destroyAllWindows();

    return 0;
}
