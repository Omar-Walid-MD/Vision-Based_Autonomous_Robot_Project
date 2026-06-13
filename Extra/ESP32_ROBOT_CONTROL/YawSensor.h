#pragma once

#include <Arduino.h>
#include <Wire.h>

// ─────────────────────────────────────────────────────────────────────────────
// YawSensor — MPU6500 gyro-based yaw measurement for ESP32
//
// Usage:
//   YawSensor yaw;
//
//   void setup() {
//       Wire.begin(SDA_PIN, SCL_PIN);
//       yaw.begin();           // init sensor
//       yaw.calibrate();       // keep robot still for ~2s during this
//   }
//
//   void loop() {
//       yaw.update();          // call as fast as possible (200Hz+ recommended)
//       float deg = yaw.read(); // degrees since last reset (positive = CCW)
//   }
//
//   // Before a motion:
//   yaw.reset();
//
//   // After motion stops:
//   float rotationDone = yaw.read();
// ─────────────────────────────────────────────────────────────────────────────

class YawSensor {
public:

    // ── Configuration ────────────────────────────────────────────────────────

    // I2C address: 0x68 if AD0 low (default), 0x69 if AD0 high
    static constexpr uint8_t MPU_ADDR = 0x68;

    // Gyro full-scale range setting — must match GYRO_FS_SEL register value:
    //   0 = ±250  dps → 131.0  LSB/dps
    //   1 = ±500  dps →  65.5  LSB/dps
    //   2 = ±1000 dps →  32.8  LSB/dps
    //   3 = ±2000 dps →  16.4  LSB/dps
    // For a robot doing slow/medium turns, ±250 or ±500 is most accurate.
    // Use ±500 if your robot turns fast (>180°/s).
    static constexpr uint8_t GYRO_FS_SEL = 1;          // ±500 dps
    static constexpr float   GYRO_SENS   = 65.5f;       // LSB/dps for ±500

    // Number of samples to average during bias calibration.
    // At 2ms per sample: 1000 samples = ~2 seconds.
    static constexpr uint16_t CALIB_SAMPLES = 1000;

    // Stationary threshold: gyro readings below this (dps) are treated as
    // zero to prevent bias from accumulating when robot is still.
    // Tune this down if it suppresses real slow rotations.
    static constexpr float STILL_THRESHOLD = 0.15f;     // degrees/second

    // ── MPU6500 Register Map ─────────────────────────────────────────────────
private:
    static constexpr uint8_t REG_PWR_MGMT_1   = 0x6B;
    static constexpr uint8_t REG_PWR_MGMT_2   = 0x6C;
    static constexpr uint8_t REG_GYRO_CONFIG   = 0x1B;
    static constexpr uint8_t REG_ACCEL_CONFIG  = 0x1C;
    static constexpr uint8_t REG_CONFIG        = 0x1A;  // DLPF config
    static constexpr uint8_t REG_SMPLRT_DIV    = 0x19;
    static constexpr uint8_t REG_GYRO_ZOUT_H   = 0x47;
    static constexpr uint8_t REG_WHO_AM_I      = 0x75;

    // ── State ────────────────────────────────────────────────────────────────
    float         _yaw         = 0.0f;   // accumulated yaw in degrees
    float         _biasZ       = 0.0f;   // gyro Z bias in raw LSB
    unsigned long _lastUs      = 0;      // last update timestamp (micros)
    bool          _calibrated  = false;
    bool          _ready       = false;

    // ── Low-level I2C helpers ────────────────────────────────────────────────
    void writeReg(uint8_t reg, uint8_t val) {
        Wire.beginTransmission(MPU_ADDR);
        Wire.write(reg);
        Wire.write(val);
        Wire.endTransmission();
    }

    uint8_t readReg(uint8_t reg) {
        Wire.beginTransmission(MPU_ADDR);
        Wire.write(reg);
        Wire.endTransmission(false);
        Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)1);
        return Wire.available() ? Wire.read() : 0;
    }

    int16_t readRawGyroZ() {
        Wire.beginTransmission(MPU_ADDR);
        Wire.write(REG_GYRO_ZOUT_H);
        Wire.endTransmission(false);
        Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)2);
        if (Wire.available() < 2) return 0;
        int16_t raw = (int16_t)(Wire.read() << 8 | Wire.read());
        return raw;
    }

public:

    // ── begin() ──────────────────────────────────────────────────────────────
    // Call once after Wire.begin(). Returns true if MPU6500 is detected.
    bool begin() {
        // Verify device identity
        uint8_t whoami = readReg(REG_WHO_AM_I);
        // MPU6500 returns 0x70, MPU6050 returns 0x68 — accept both
        if (whoami != 0x70 && whoami != 0x68 && whoami != 0x71) {
            Serial.print("[YawSensor] WHO_AM_I failed: 0x");
            Serial.println(whoami, HEX);
            return false;
        }

        // Reset device
        writeReg(REG_PWR_MGMT_1, 0x80);
        delay(100);

        // Wake up, use PLL with X gyro as clock source (more stable than internal)
        writeReg(REG_PWR_MGMT_1, 0x01);
        delay(10);

        // Disable accel and temp to reduce noise on gyro power rail
        // PWR_MGMT_2: disable accel axes (bits 3-5), keep gyro enabled
        writeReg(REG_PWR_MGMT_2, 0x38);  // 0b00111000

        // Sample rate divider: 0 = gyro output rate (1kHz with DLPF enabled)
        writeReg(REG_SMPLRT_DIV, 0x00);

        // DLPF: bandwidth 41Hz, delay 5.9ms — good balance of noise vs latency
        // Higher bandwidth = more responsive but more noise
        // Lower bandwidth = smoother but slower to react
        writeReg(REG_CONFIG, 0x03);      // DLPF_CFG = 3 → 41Hz

        // Gyro full-scale range
        writeReg(REG_GYRO_CONFIG, (GYRO_FS_SEL << 3));

        _ready = true;
        _lastUs = micros();

        Serial.print("[YawSensor] MPU6500 ready. WHO_AM_I=0x");
        Serial.println(whoami, HEX);
        return true;
    }

    // ── calibrate() ──────────────────────────────────────────────────────────
    // Measures gyro Z bias. Robot MUST be completely still.
    // Prints progress to Serial. Blocks for ~2 seconds.
    void calibrate() {
        if (!_ready) {
            Serial.println("[YawSensor] calibrate() called before begin()");
            return;
        }

        Serial.println("[YawSensor] Calibrating — keep robot still...");

        // Discard first 50 samples (sensor settling)
        for (int i = 0; i < 50; i++) {
            readRawGyroZ();
            delay(2);
        }

        // Collect samples and average
        long sum = 0;
        for (uint16_t i = 0; i < CALIB_SAMPLES; i++) {
            sum += readRawGyroZ();
            delay(2);
        }

        _biasZ = (float)sum / (float)CALIB_SAMPLES;
        _calibrated = true;

        // Reset integration state after calibration
        _yaw   = 0.0f;
        _lastUs = micros();

        Serial.print("[YawSensor] Calibration done. Bias Z = ");
        Serial.print(_biasZ, 3);
        Serial.print(" LSB (");
        Serial.print(_biasZ / GYRO_SENS, 4);
        Serial.println(" dps)");
    }

    // ── reset() ──────────────────────────────────────────────────────────────
    // Zeroes the accumulated yaw. Call this just before a motion begins.
    void reset() {
        _yaw    = 0.0f;
        _lastUs = micros();
    }

    // ── update() ─────────────────────────────────────────────────────────────
    // Integrates gyro Z to accumulate yaw. Call as fast as possible in loop().
    // Minimum recommended: 200Hz (every 5ms). Better: 500Hz (every 2ms).
    void update() {
        if (!_ready) return;

        unsigned long now = micros();
        float dt = (float)(now - _lastUs) / 1e6f;
        _lastUs = now;

        // Guard against stale dt on first call or micros() overflow
        if (dt <= 0.0f || dt > 0.1f) return;

        int16_t rawZ = readRawGyroZ();
        float dps = ((float)rawZ - _biasZ) / GYRO_SENS;

        // Zero-rate clamping — suppress integration noise while stationary
        if (fabsf(dps) < STILL_THRESHOLD) dps = 0.0f;

        _yaw += dps * dt;
    }

    // ── read() ───────────────────────────────────────────────────────────────
    // Returns accumulated yaw in degrees since last reset().
    // Positive = counter-clockwise (right-hand rule about Z axis up).
    // Negative = clockwise.
    // No wrap-around — value can exceed ±360 for multiple rotations.
    float read() const {
        return _yaw;
    }

    // ── readNormalized() ─────────────────────────────────────────────────────
    // Returns yaw normalized to [0, 360). Useful for absolute heading display.
    float readNormalized() const {
        float y = fmodf(_yaw, 360.0f);
        if (y < 0.0f) y += 360.0f;
        return y;
    }

    // ── isCalibrated() ───────────────────────────────────────────────────────
    bool isCalibrated() const { return _calibrated; }

    // ── getBiasZ() ───────────────────────────────────────────────────────────
    // Returns raw LSB bias measured during calibration. Useful for diagnostics.
    float getBiasZ() const { return _biasZ; }

    // ── injectHeading() ──────────────────────────────────────────────────────
    // Overrides the current yaw value with a known true heading.
    // Use this if you have an external reference (e.g. a known alignment point).
    void injectHeading(float trueDegrees) {
        _yaw = trueDegrees;
    }
};