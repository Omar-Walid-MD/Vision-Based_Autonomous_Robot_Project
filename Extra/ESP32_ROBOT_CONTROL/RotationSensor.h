#ifndef ROTATION_SENSOR_H
#define ROTATION_SENSOR_H

#include <Wire.h>
#include <MPU6500_WE.h>
#include <QMC5883LCompass.h>
#include <Preferences.h>
#include <ble.h>


class RotationSensor {
public:
    RotationSensor(BLEModule& ble);
    
    bool begin();                    
    void calibrateCompass(bool forceRecal = false);   // Now supports force
    void calibrateGyro(bool force = false);
    
    float getYaw();                  
    float getCurrentYaw();            
    float getMagYaw();
    float getOffsetMagYaw(float offset);
            
    void setZeroHeading();           
    void printCalibration();
    void update();
    

private:
    MPU6500_WE mpu;
    QMC5883LCompass compass;
    Preferences prefs;
    BLEModule& _ble;
    

    float yaw = 0.0f;
    float mag_yaw = 0.0f;
    unsigned long last_time = 0;
    xyzFloat gyr_offset = {0.0f, 0.0f, 0.0f};
    float yaw_offset = 0.0f;

    unsigned long _lastBle = 0;
    const unsigned long _bleInterval = 100;
    bool _calibrating = false;


    // Magnetometer calibration storage
    float mag_offset[3] = {0};
    float mag_scale[3]  = {1.0f, 1.0f, 1.0f};

    void loadGyroOffsets();
    void saveGyroOffsets();
    
    void loadMagCalibration();
    void saveMagCalibration();

    void loadZeroHeading();
    
    void computeTiltCompensatedMagYaw();
};

#endif