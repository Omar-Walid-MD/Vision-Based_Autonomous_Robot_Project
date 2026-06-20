#pragma once

#include <Arduino.h>
#include <Wire.h>

class MPU
{
public:
    bool begin()
    {
        Wire.begin(8,9);

        // Wake MPU6500
        Wire.beginTransmission(MPU_ADDR);
        Wire.write(MPU_PWR_MGMT_1);
        Wire.write(0x00);
        if (Wire.endTransmission() != 0)
            return false;

        // Gyro range ±250 deg/s
        Wire.beginTransmission(MPU_ADDR);
        Wire.write(MPU_GYRO_CONFIG);
        Wire.write(0x00);
        Wire.endTransmission();

        delay(100);

        lastUpdateUs = micros();

        return true;
    }

    void calibrate(uint16_t samples = 1000)
    {
        float sum = 0.0f;

        Serial.println("Calibrating MPU... Keep robot still.");

        for (uint16_t i = 0; i < samples; i++)
        {
            sum += readGyroZRaw();
            delay(2);
        }

        gyroBiasZ = sum / samples;

        Serial.print("Gyro Z Bias: ");
        Serial.println(gyroBiasZ);
    }

    void update()
    {
        uint32_t now = micros();

        float dt =
            (now - lastUpdateUs) / 1000000.0f;

        lastUpdateUs = now;

        float gyroZ =
            (readGyroZRaw() - gyroBiasZ) /
            GYRO_SCALE;

        yaw += gyroZ * dt;
    }

    float readYaw() const
    {
        return yaw;
    }

    void reset()
    {
        yaw = 0.0f;
        lastUpdateUs = micros();
    }

private:
    static constexpr uint8_t MPU_ADDR = 0x70;

    static constexpr uint8_t MPU_PWR_MGMT_1 = 0x6B;
    static constexpr uint8_t MPU_GYRO_CONFIG = 0x1B;
    static constexpr uint8_t MPU_GYRO_ZOUT_H = 0x47;

    // ±250 deg/s sensitivity
    static constexpr float GYRO_SCALE = 131.0f;

    float gyroBiasZ = 0.0f;
    float yaw = 0.0f;

    uint32_t lastUpdateUs = 0;

    int16_t readGyroZRaw()
    {
        Wire.beginTransmission(MPU_ADDR);
        Wire.write(MPU_GYRO_ZOUT_H);
        Wire.endTransmission(false);

        Wire.requestFrom(MPU_ADDR, (uint8_t)2);

        if (Wire.available() < 2)
            return 0;

        return (Wire.read() << 8) | Wire.read();
    }
};