#include "RotationSensor.h"
#include <math.h>
#include <ble.h>

#define PI 3.1415926535f

RotationSensor::RotationSensor(BLEModule& ble) : mpu(MPU6500_WE(0x68)), _ble(ble) {}

// ==================== BEGIN ====================
bool RotationSensor::begin() {
    Wire.begin();

    // Initialize MPU6500
    if (!mpu.init()) {
        _ble.send("MPU6500 init failed!");
        return false;
    }
    mpu.setSampleRateDivider(5);
    mpu.setAccRange(MPU6500_ACC_RANGE_4G);
    mpu.setGyrRange(MPU6500_GYRO_RANGE_250);

    // Initialize QMC5883L
    compass.init();
    compass.setSmoothing(15, true);

    // compass.setSmoothing(10, true);
    compass.setCalibrationOffsets(8.00, -48.00, -522.00);
    compass.setCalibrationScales(0.89, 0.85, 1.44);

    mag_offset[0] = compass.getCalibrationOffset(0);
    mag_offset[1] = compass.getCalibrationOffset(1);
    mag_offset[2] = compass.getCalibrationOffset(2);
    mag_scale[0]  = compass.getCalibrationScale(0);
    mag_scale[1]  = compass.getCalibrationScale(1);
    mag_scale[2]  = compass.getCalibrationScale(2);

    // Load both calibrations from flash
    // calibrateCompass(false);
    calibrateGyro(false);

    loadZeroHeading();

    last_time = millis();

    // Initial yaw
    computeTiltCompensatedMagYaw();
    yaw = mag_yaw;

    _ble.send("RotationSensor initialized successfully.");
    printCalibration();
    return true;
}

void RotationSensor::loadZeroHeading() {
    prefs.begin("imu_cal", false);

    if(prefs.isKey("zh"))
    {
      yaw_offset = prefs.getFloat("zh",0.0f);
    }

    prefs.end();
}

// ==================== MAGNETOMETER CALIBRATION ====================
void RotationSensor::calibrateCompass(bool forceRecal) {
    prefs.begin("imu_cal", false);

    bool hasMagCal = prefs.isKey("mox") && prefs.isKey("moy") && prefs.isKey("moz") &&
                     prefs.isKey("msx") && prefs.isKey("msy") && prefs.isKey("msz");

    if (hasMagCal && !forceRecal) {
        _ble.send("Loading saved magnetometer calibration...");
        loadMagCalibration();
    } else {
        _calibrating = true;
        _ble.send("Starting magnetometer calibration...");
        _ble.send("Move the sensor in figure-8 motion for 20-30 seconds...");

        compass.calibrate();   // Blocking call from library

        // Read new calibration values
        mag_offset[0] = compass.getCalibrationOffset(0);
        mag_offset[1] = compass.getCalibrationOffset(1);
        mag_offset[2] = compass.getCalibrationOffset(2);
        mag_scale[0]  = compass.getCalibrationScale(0);
        mag_scale[1]  = compass.getCalibrationScale(1);
        mag_scale[2]  = compass.getCalibrationScale(2);

        saveMagCalibration();

        _calibrating = false;
        _ble.send("saved");
    }

    prefs.end();

    // Apply the calibration
    compass.setCalibrationOffsets(mag_offset[0], mag_offset[1], mag_offset[2]);
    compass.setCalibrationScales(mag_scale[0], mag_scale[1], mag_scale[2]);
}

// ==================== SAVE / LOAD MAG CALIBRATION ====================
void RotationSensor::saveMagCalibration() {
    prefs.putFloat("mox", mag_offset[0]);
    prefs.putFloat("moy", mag_offset[1]);
    prefs.putFloat("moz", mag_offset[2]);
    prefs.putFloat("msx", mag_scale[0]);
    prefs.putFloat("msy", mag_scale[1]);
    prefs.putFloat("msz", mag_scale[2]);
}

void RotationSensor::loadMagCalibration() {
    mag_offset[0] = prefs.getFloat("mox", 0.0f);
    mag_offset[1] = prefs.getFloat("moy", 0.0f);
    mag_offset[2] = prefs.getFloat("moz", 0.0f);
    mag_scale[0]  = prefs.getFloat("msx", 1.0f);
    mag_scale[1]  = prefs.getFloat("msy", 1.0f);
    mag_scale[2]  = prefs.getFloat("msz", 1.0f);
}

// ==================== GYRO  ====================
void RotationSensor::calibrateGyro(bool force) {
    prefs.begin("imu_cal", false);   // Note: same namespace is fine

    bool hasSaved = prefs.isKey("off_x") && prefs.isKey("off_y") && prefs.isKey("off_z");

    if (hasSaved && !force) {
        loadGyroOffsets();
    } else {
        // ... same gyro calibration code as before ...
        _calibrating = true;
        _ble.send("Starting gyro calibration.");
        delay(2000);
        int cal_count = 1200;
        xyzFloat sum = {0, 0, 0};
        for (int i = 0; i < cal_count; i++) {
            xyzFloat g = mpu.getGyrValues();
            sum.x += g.x; sum.y += g.y; sum.z += g.z;
            delay(8);
        }
        gyr_offset.x = sum.x / cal_count;
        gyr_offset.y = sum.y / cal_count;
        gyr_offset.z = sum.z / cal_count;

        saveGyroOffsets();
        _calibrating = false;
        _ble.send("saved");
    }
    prefs.end();
}

void RotationSensor::loadGyroOffsets() {
    gyr_offset.x = prefs.getFloat("off_x", 0.0f);
    gyr_offset.y = prefs.getFloat("off_y", 0.0f);
    gyr_offset.z = prefs.getFloat("off_z", 0.0f);
}

void RotationSensor::saveGyroOffsets() {
    prefs.putFloat("off_x", gyr_offset.x);
    prefs.putFloat("off_y", gyr_offset.y);
    prefs.putFloat("off_z", gyr_offset.z);
}

void RotationSensor::computeTiltCompensatedMagYaw() {
    compass.read();
    
    static float mx_f = 0, my_f = 0, mz_f = 0;

    float mx_raw = compass.getX();
    float my_raw = compass.getY();
    float mz_raw = compass.getZ();

    const float mag_alpha = 0.10f;

    mx_f += mag_alpha * (mx_raw - mx_f);
    my_f += mag_alpha * (my_raw - my_f);
    mz_f += mag_alpha * (mz_raw - mz_f);

    float mx = mx_f;
    float my = my_f;
    float mz = mz_f;

    static xyzFloat acc_filt = {0,0,0};

    xyzFloat acc_raw = mpu.getGValues();

    const float acc_alpha = 0.15f;   // lower = smoother

    acc_filt.x += acc_alpha * (acc_raw.x - acc_filt.x);
    acc_filt.y += acc_alpha * (acc_raw.y - acc_filt.y);
    acc_filt.z += acc_alpha * (acc_raw.z - acc_filt.z);

    xyzFloat acc = acc_filt;

    float roll  = atan2(acc.y, acc.z);
    float pitch = atan2(-acc.x, sqrt(acc.y*acc.y + acc.z*acc.z));

    float Xh = mx * cos(pitch) + mz * sin(pitch);
    float Yh = mx * sin(roll) * sin(pitch) + my * cos(roll) - mz * sin(roll) * cos(pitch);

    mag_yaw = atan2(Yh, Xh) * 180.0f / PI;
    if (mag_yaw < 0) mag_yaw += 360.0f;
}

float RotationSensor::getYaw() {
    // Full fusion (if you ever need it)
    unsigned long now = millis();
    float dt = (now - last_time) / 1000.0f;
    last_time = now;
    if (dt <= 0) dt = 0.05f;

    xyzFloat acc = mpu.getGValues();
    xyzFloat gyr = mpu.getGyrValues();
    gyr.x -= gyr_offset.x;
    gyr.y -= gyr_offset.y;
    gyr.z -= gyr_offset.z;

    computeTiltCompensatedMagYaw();   // Always fresh mag

    static float gz_f = 0;
    const float gyro_alpha = 0.2f;

    gz_f += gyro_alpha * (gyr.z - gz_f);
    float gyro_delta = gz_f * dt;

    float yaw_gyro = yaw + gyro_delta;

    float diff = mag_yaw - yaw_gyro;
    diff = fmod(diff + 540.0f, 360.0f) - 180.0f;

    float error = fabs(diff);
    float alpha = 0.98f;

    if (error > 10.0f)
        alpha = 0.90f;
    else if (error > 5.0f)
        alpha = 0.95f;

    yaw = yaw_gyro + (1.0f - alpha) * diff;

    if (yaw >= 360.0f) yaw -= 360.0f;
    if (yaw < 0.0f)    yaw += 360.0f;

    return yaw - yaw_offset;
}

void RotationSensor::update() {
    if (_calibrating) return;

    unsigned long now = millis();

    // Always update magnetometer reading first (this is what you want)
    getYaw();

    if (now - _lastBle >= _bleInterval) {
        _lastBle = now;

        float currentMagYaw = getMagYaw();

        uint8_t payload[3];
        int16_t y = (int16_t)(currentMagYaw + 0.5f);

        payload[0] = 3;
        payload[1] = y & 0xFF;
        payload[2] = (y >> 8) & 0xFF;

        _ble.sendRaw(payload, 3);
    }
}

float RotationSensor::getMagYaw() {
    float currentMagYaw = mag_yaw - yaw_offset;   // Apply local zero
    if (currentMagYaw < 0) currentMagYaw += 360.0f;
    return currentMagYaw;
}

float RotationSensor::getOffsetMagYaw(float offset) {
    float offsetMagMagYaw = mag_yaw - yaw_offset + offset;   // Apply local zero
    if (offsetMagMagYaw < 0) offsetMagMagYaw += 360.0f;
    return offsetMagMagYaw;
}


void RotationSensor::setZeroHeading() {
    yaw_offset = mag_yaw;

    prefs.begin("imu_cal", false);
    prefs.putFloat("zh",yaw_offset);
    prefs.end();
}

void RotationSensor::printCalibration() {
    Serial.printf("Gyro Offset: %.4f  %.4f  %.4f\n", gyr_offset.x, gyr_offset.y, gyr_offset.z);
    Serial.printf("Mag Offset : %.2f  %.2f  %.2f\n", mag_offset[0], mag_offset[1], mag_offset[2]);
    Serial.printf("Mag Scale  : %.3f  %.3f  %.3f\n", mag_scale[0], mag_scale[1], mag_scale[2]);
}