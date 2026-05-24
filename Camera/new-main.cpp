#include <opencv2/opencv.hpp>
#include <iostream>
#include <chrono>
#include <opencv2/calib3d.hpp>
#include <gst/app/gstappsink.h>
#include <gst/app/gstappsrc.h>
#include <signal.h>

extern "C" {
#include <apriltag/apriltag.h>
#include <apriltag/tag36h11.h>
#include <apriltag/common/image_u8.h>
#include <apriltag/apriltag_pose.h>
}

using namespace cv;
using namespace std;

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

    return Vec3d(
        roll  * 180 / CV_PI,
        pitch * 180 / CV_PI,
        yaw   * 180 / CV_PI
    );
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

int main(int argc, char* argv[])
{
    bool show = false;
    bool enable_output = false;

    const int INPUT_WIDTH  = 1280;
    const int INPUT_HEIGHT = 720;

    const int OUTPUT_WIDTH  = 640;
    const int OUTPUT_HEIGHT = 360;

    double scale_up_x = INPUT_WIDTH  * 1.0 / OUTPUT_WIDTH;
    double scale_up_y = INPUT_HEIGHT * 1.0 / OUTPUT_HEIGHT;

    for (int i = 1; i < argc; ++i)
    {
        std::string arg = argv[i];

        if (arg == "--no-show" || arg == "--headless")
        {
            show = false;
        }
        else if (arg == "--show" || arg == "-s")
        {
            show = true;
        }
        else if (arg == "--output" || arg == "-o")
        {
            enable_output = true;
        }
    }

    if (show)
    {
        std::cout << "Display enabled (--show)\n";
    }
    else
    {
        std::cout << "Display disabled\n";
    }

    gst_init(&argc, &argv);

    signal(SIGINT, handle_sigint);

	// Raspberry Pi Camera input pipeline
	// Sensor mode 1 (2304x1296)
	// ==========================================
	std::string input_pipeline =
	"libcamerasrc ! "
	"video/x-raw,width=2304,height=1296,framerate=15/1 ! "
	"queue max-size-buffers=1 leaky=downstream ! "
	"videoconvert ! "
	"video/x-raw,format=BGR ! "
	"videoscale ! "
	"video/x-raw,width=" + std::to_string(INPUT_WIDTH) +
	",height=" + std::to_string(INPUT_HEIGHT) + " ! "
	"appsink name=camera_sink drop=true max-buffers=1 sync=false";
    
    // ==========================================
    // Shared memory output pipeline
    // ==========================================
    std::string output_pipeline =
    "appsrc name=python_src is-live=true block=false format=time ! "
    "video/x-raw,format=BGR,width=" + std::to_string(OUTPUT_WIDTH) +
    ",height=" + std::to_string(OUTPUT_HEIGHT) +
    ",framerate=15/1 ! "
    "queue leaky=2 max-size-buffers=2 ! "
    "shmsink socket-path=/tmp/camera_stream "
    "sync=false wait-for-connection=false";

    GError *err = nullptr;

    GstElement *input_pipe =
        gst_parse_launch(input_pipeline.c_str(), &err);

    if (!input_pipe)
    {
        std::cerr << "Failed to create input pipeline: "
                  << (err ? err->message : "unknown")
                  << std::endl;
        return -1;
    }

    GstElement *output_pipe = nullptr;

    if (enable_output)
    {
        output_pipe =
            gst_parse_launch(output_pipeline.c_str(), &err);

        if (!output_pipe)
        {
            std::cerr << "Failed to create output pipeline: "
                      << (err ? err->message : "unknown")
                      << std::endl;
            return -1;
        }
    }

    GstElement *appsink =
        gst_bin_get_by_name(GST_BIN(input_pipe), "camera_sink");

    if (!appsink)
    {
        std::cerr << "Could not find camera_sink\n";
        return -1;
    }

    GstElement *appsrc = nullptr;

    if (enable_output)
    {
        appsrc =
            gst_bin_get_by_name(GST_BIN(output_pipe), "python_src");

        if (!appsrc)
        {
            std::cerr << "Could not find python_src\n";
            return -1;
        }
    }

    gst_element_set_state(input_pipe, GST_STATE_PLAYING);

    if (enable_output)
    {
        gst_element_set_state(output_pipe, GST_STATE_PLAYING);
    }

    global_input_pipe = input_pipe;

    if (enable_output)
    {
        global_output_pipe = output_pipe;
    }

    // ==========================================
    // AprilTag setup
    // ==========================================
    apriltag_family_t *tf = tag36h11_create();

    apriltag_detector_t *td = apriltag_detector_create();

    apriltag_detector_add_family(td, tf);

    td->quad_decimate = 1.0;
    td->quad_sigma    = 0.0;
    td->nthreads      = 2;
    td->debug         = 0;
    td->refine_edges  = 1;

    // ==========================================
    // Camera calibration
    // ==========================================
    FileStorage fs("camera_calib.yaml", FileStorage::READ);

    Mat cameraMatrix, distCoeffs;

    fs["camera_matrix"] >> cameraMatrix;
    fs["dist_coeffs"]   >> distCoeffs;

    fs.release();

    double fx = cameraMatrix.at<double>(0,0);
    double fy = cameraMatrix.at<double>(1,1);
    double cx = cameraMatrix.at<double>(0,2);
    double cy = cameraMatrix.at<double>(1,2);

    double tag_size = 0.095;

    if (show)
    {
        cv::namedWindow(
            "AprilTag Detection",
            cv::WINDOW_NORMAL
        );

        cv::resizeWindow(
            "AprilTag Detection",
            720,
            405
        );
    }

    int frame_count = 0;

    auto start_time = std::chrono::steady_clock::now();
    
    cout << "STARTED\n";
    
    while (true)
    {
        GstSample *sample =
			gst_app_sink_try_pull_sample(
				GST_APP_SINK(appsink),
				GST_SECOND / 2
			);

        if (!sample)
		{
			cout << "no sample";
			continue;
		}
            

        GstBuffer *buffer =
            gst_sample_get_buffer(sample);

        GstMapInfo map;

        gst_buffer_map(buffer, &map, GST_MAP_READ);

        // ==========================================
        // Frame from webcam
        // ==========================================
        cv::Mat frame(
            INPUT_HEIGHT,
            INPUT_WIDTH,
            CV_8UC3,
            (void*)map.data
        );

        // ==========================================
        // Resize
        // ==========================================
        cv::Mat resized;

        cv::resize(
            frame,
            resized,
            cv::Size(OUTPUT_WIDTH, OUTPUT_HEIGHT),
            0,
            0,
            cv::INTER_LINEAR
        );

        // ==========================================
        // Convert to grayscale
        // ==========================================
        cv::Mat gray;

        cv::cvtColor(
            resized,
            gray,
            cv::COLOR_BGR2GRAY
        );

        if (!gray.isContinuous())
        {
            gray = gray.clone();
        }
        
         // ==========================================
        // AprilTag image
        // ==========================================
        image_u8_t im = {
            .width  = gray.cols,
            .height = gray.rows,
            .stride = gray.cols,
            .buf    = gray.data
        };

        zarray_t *detections =
            apriltag_detector_detect(td, &im);

        for (int i = 0; i < zarray_size(detections); i++)
        {
            apriltag_detection_t *det;

            zarray_get(detections, i, &det);

            apriltag_detection_info_t info;

            info.det     = det;
            info.tagsize = tag_size;
            info.fx      = fx;
            info.fy      = fy;
            info.cx      = cx;
            info.cy      = cy;

            apriltag_detection_t scaled_det = *det;

            for (int j = 0; j < 4; j++)
            {
                scaled_det.p[j][0] *= scale_up_x;
                scaled_det.p[j][1] *= scale_up_y;
            }

            scaled_det.c[0] *= scale_up_x;
            scaled_det.c[1] *= scale_up_y;

            info.det = &scaled_det;

            apriltag_pose_t pose;

            estimate_tag_pose(&info, &pose);

            Mat R(3,3,CV_64F, pose.R->data);
            Mat t(3,1,CV_64F, pose.t->data);

            Vec3d euler =
                rotationMatrixToEulerAngles(R);

            double pitch = euler[0];
            double yaw   = euler[1];
            double roll  = euler[2];

            yaw = fmod((yaw + 180.0), 360.0);

            if (yaw < 0)
                yaw += 360.0;

            yaw -= 180.0;

            double distance = norm(t);

            cout << "X Y Z: " << t.t() << endl;

            cout << "Roll: " << roll
                 << " Pitch: " << pitch
                 << " Yaw: " << yaw
                 << endl;

            cout << "------------------------" << endl;

            if (show)
            {
                for (int j = 0; j < 4; j++)
                {
                    Point p1(
                        static_cast<int>(
                            det->p[j][0] * scale_up_x
                        ),
                        static_cast<int>(
                            det->p[j][1] * scale_up_y
                        )
                    );

                    Point p2(
                        static_cast<int>(
                            det->p[(j+1)%4][0] * scale_up_x
                        ),
                        static_cast<int>(
                            det->p[(j+1)%4][1] * scale_up_y
                        )
                    );

                    line(
                        resized,
                        p1,
                        p2,
                        Scalar(200),
                        2
                    );
                }
                
                vector<Point3f> axis = {
                    Point3f(0,0,0),
                    Point3f(0.1,0,0),
                    Point3f(0,0.1,0),
                    Point3f(0,0,0.1)
                };

                vector<Point2f> imgpts;

                Mat rvec;

                Rodrigues(R, rvec);

                projectPoints(
                    axis,
                    rvec,
                    t,
                    cameraMatrix,
                    distCoeffs,
                    imgpts
                );

                for (auto& pt : imgpts)
                {
                    pt.x *= scale_up_x;
                    pt.y *= scale_up_y;
                }

                line(
                    resized,
                    imgpts[0],
                    imgpts[1],
                    Scalar(50),
                    3
                );

                line(
                    resized,
                    imgpts[0],
                    imgpts[2],
                    Scalar(150),
                    3
                );

                line(
                    resized,
                    imgpts[0],
                    imgpts[3],
                    Scalar(220),
                    3
                );

                putText(
                    resized,
                    "Dist: " + to_string(distance) + " m",
                    Point(20,40),
                    FONT_HERSHEY_SIMPLEX,
                    0.7,
                    Scalar(255),
                    2
                );

                putText(
                    resized,
                    "Roll: " + to_string(roll),
                    Point(20,80),
                    FONT_HERSHEY_SIMPLEX,
                    0.7,
                    Scalar(200),
                    2
                );

                putText(
                    resized,
                    "Pitch: " + to_string(pitch),
                    Point(20,120),
                    FONT_HERSHEY_SIMPLEX,
                    0.7,
                    Scalar(200),
                    2
                );

                putText(
                    resized,
                    "Yaw: " + to_string(yaw),
                    Point(20,160),
                    FONT_HERSHEY_SIMPLEX,
                    0.7,
                    Scalar(200),
                    2
                );
            }
        }

        apriltag_detections_destroy(detections);
        
        // ==========================================
        // Shared memory output
        // ==========================================
        if (enable_output)
        {
            size_t out_size =
                resized.total() * resized.elemSize();

            GstBuffer *out_buffer =
                gst_buffer_new_allocate(
                    nullptr,
                    out_size,
                    nullptr
                );

            GstMapInfo out_map;

            gst_buffer_map(
                out_buffer,
                &out_map,
                GST_MAP_WRITE
            );

            memcpy(
                out_map.data,
                resized.data,
                out_size
            );

            gst_buffer_unmap(out_buffer, &out_map);

            gst_app_src_push_buffer(
                GST_APP_SRC(appsrc),
                out_buffer
            );
        }

        // ==========================================
        // Display
        // ==========================================
        if (show)
        {
            if (frame_count == 0)
            {
                cv::resizeWindow(
                    "AprilTag Detection",
                    720,
                    405
                );
            }

            cv::imshow(
                "AprilTag Detection",
                resized
            );
        }

        // ==========================================
        // FPS
        // ==========================================
        frame_count++;

        if (frame_count >= 60)
        {
            auto now =
                std::chrono::steady_clock::now();
            auto total_duration = std::chrono::duration_cast<std::chrono::milliseconds>(now - start_time).count();
            
            double fps =
                (frame_count * 1000.0) / total_duration;

            std::cout
                << "Resolution: "
                << frame.cols
                << "x"
                << frame.rows
                << " | FPS: "
                << fps
                << " ("
                << frame_count
                << " frames / "
                << total_duration
                << " ms)\n";

            frame_count = 0;
            start_time = now;
        }

        if (show)
        {
            int key = cv::waitKey(1);

            if (key == 'q' || key == 27)
                break;
        }

        gst_buffer_unmap(buffer, &map);
        gst_sample_unref(sample);
    }

    apriltag_detector_destroy(td);
    tag36h11_destroy(tf);

    if (show)
    {
        cv::destroyAllWindows();
    }

    return 0;
}
