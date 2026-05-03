#pragma once

// #define _DEBUG
#define REMOTE_UARTBUS

#include "util.h"
#include "hoverserial.h"
#include "globals.h"
#include "RotationSensor.h"
#include <HardwareSerial.h>
#include <ble.h>
#include <Preferences.h>

Preferences prefs;

struct CalibCycle {
  int durationSec;
  int speed;
};

#define START_SPEED 100
#define MINIMUM_SPEED 50

#define STALL_TIME 750

#define WHEEL_DIAMETER 0.16f   // meters (example)
#define WHEEL_BASE 0.465f    // meters (distance between wheels)
#define TICKS_PER_REV 90      // from hall sensors

#define BRAKE_DISTANCE_METERS 0.50f

#define HOVER_SWITCH 14




class HoverboardController {
public:
    // Constructor: two hardware serials
    HoverboardController(HardwareSerial& serialA,
                         HardwareSerial& serialB,
                         BLEModule& ble,
                         RotationSensor& imu)
        : _serialA(serialA),
          _serialB(serialB),
          _ble(ble),
          _imu(imu) {

            pinMode(HOVER_SWITCH,OUTPUT);
            on();

          }


    void on()
    {
      digitalWrite(HOVER_SWITCH,HIGH);
    }

    void off()
    {
      digitalWrite(HOVER_SWITCH,LOW);
    }

    void reset()
    {
      off();
      delay(500);
      on();
    }


    void setSpeed(int speed) {
        _baseSpeedLeft = speed;
        _baseSpeedRight = speed;
        setDirection(_dir);
    }

    void setSpeed(int left, int right) {
        _baseSpeedLeft = left;
        _baseSpeedRight = right;
        setDirection(_dir);
    }

    void setSpeedLeft(int left) {
        _baseSpeedLeft = left;
        setDirection(_dir);
    }

    void setSpeedRight(int right) {
        _baseSpeedRight = right;
        setDirection(_dir);
    }

    void setDirection(const int* newDir)
    {
      _dir[0] = newDir[0]; _dir[1] = newDir[1];

      if(_motionState == MOVING)
      {
        _speedLeft = (int) (_dir[0] * _linearSpeedLeft * _brakingFactor);
        _speedRight = (int) (_dir[1] * _linearSpeedRight * _brakingFactor);
      }
      else if(_motionState == ROTATING)
      {
        _speedLeft = (int) (_dir[0] * _baseSpeedLeft * _cal[0] * _brakingFactor);
        _speedRight = (int) (_dir[1] * _baseSpeedRight * _cal[1] * _brakingFactor);
      }
      else
      {
        _speedLeft = (int) (_dir[0] * _baseSpeedLeft * _cal[0]);
        _speedRight = (int) (_dir[1] * _baseSpeedRight * _cal[1]);
      }

      _speedLeft = _dir[0] * max(MINIMUM_SPEED,abs(_speedLeft));
      _speedRight = _dir[1] * max(MINIMUM_SPEED,abs(_speedRight));

    }

    void setState(int left, int right)
    {
      _stateLeft = left;
      _stateRight = right;
    }

    void sendSpeedBLE(int16_t speed0, int16_t speed1)
    {
        uint8_t payload[5];

        payload[0] = 0;

        // Motor 0
        payload[1] = speed0 & 0xFF;         // LOW
        payload[2] = (speed0 >> 8) & 0xFF;  // HIGH

        // Motor 1
        payload[3] = speed1 & 0xFF;         // LOW
        payload[4] = (speed1 >> 8) & 0xFF;  // HIGH

        _ble.sendRaw(payload, 5);
    }

    void sendOdomBLE(int32_t odom0, int32_t odom1)
    {
        uint8_t payload[9];

        payload[0] = 'o';

        // Motor 0 odom (little-endian)
        payload[1] = odom0 & 0xFF;
        payload[2] = (odom0 >> 8) & 0xFF;
        payload[3] = (odom0 >> 16) & 0xFF;
        payload[4] = (odom0 >> 24) & 0xFF;

        // Motor 1 odom (little-endian)
        payload[5] = odom1 & 0xFF;
        payload[6] = (odom1 >> 8) & 0xFF;
        payload[7] = (odom1 >> 16) & 0xFF;
        payload[8] = (odom1 >> 24) & 0xFF;

        _ble.sendRaw(payload, 9);
    }

    void update() {
      unsigned long now = millis();

      // ---- SEND COMMANDS FIRST (priority) ----
      if (now > _nextSend) {
          sendCommands();
          _nextSend = now + _sendInterval;
      }

      updateMotion();

      // ---- RECEIVE BOARD A (limited) ----
      SerialHover2Server tmpFeedbackA;
      int countA = 0;

      while (countA < 6 && Receive(_serialA, tmpFeedbackA)) {
          _feedbackA = tmpFeedbackA;
          _lastAUpdate = now;
          countA++;
      }

      // ---- RECEIVE BOARD B (limited) ----
      SerialHover2Server tmpFeedbackB;
      int countB = 0;

      while (countB < 6 && Receive(_serialB, tmpFeedbackB)) {
          _feedbackB = tmpFeedbackB;
          _lastBUpdate = now;
          countB++;
      }

      // ---- BLE SEND (throttled) ----

      if (now - _lastBle >= _bleInterval) {
          sendSpeedBLE(_feedbackA.iSpeed, _feedbackB.iSpeed);
          // _ble.send("Speed L: "+String(abs(_speedLeft)));
          // _ble.send("Speed R: "+String(abs(_speedLeft)));
          // sendOdomBLE(_feedbackA.iOdom, _feedbackB.iOdom);
          _lastBle = now;
      }
  }

    void setMode2()
    {
        sendHexString(Serial1, "2F-02-00-42-28-00-00-00-00-00-00-02-FF-D1-B0");
        sendHexString(Serial1, "2F-02-01-42-28-00-00-00-00-00-00-02-FF-98-68");
    }

    void setMode3()
    {
        sendHexString(Serial1, "2F-02-00-42-28-00-00-00-00-00-00-03-FF-E0-83");
        sendHexString(Serial1, "2F-02-01-42-28-00-00-00-00-00-00-03-FF-A9-5B");
    }

    void loadCalibration()
    {
        prefs.begin("hover", true); // read-only

        _cal[0] = prefs.getFloat("cal0", 1.0f);
        _cal[1] = prefs.getFloat("cal1", 1.0f);

        _ble.send(
          "CAL,0," + String(_cal[0], 4) +
          ",1," + String(_cal[1], 4)
        );

        prefs.end();
    }

    void saveCalibration()
    {
        prefs.begin("hover", false);

        prefs.putFloat("cal0", _cal[0]);
        prefs.putFloat("cal1", _cal[1]);

        _ble.send(
          "CAL,0," + String(_cal[0], 4) +
          ",1," + String(_cal[1], 4)
        );

        prefs.end();
    }

    void setCalibration(float left, float right)
    {
        _cal[0] = left;
        _cal[1] = right;
    }



    void move(float centimeters)
    {
        if (_motionState != IDLE) return;

        _motionState = MOVING;

        _leftStart  = getLeftOdom();
        _rightStart = getRightOdom();

        _linearTarget = metersToTicks(centimeters / 100.0f);

        _brakingFactor = 1;

        if (centimeters > 0)
            setDirection(FORWARD);
        else
            setDirection(BACKWARD);

        _ble.send("moving");
    }


    void rot(float degrees) {
        if (_motionState != IDLE) return;

        _motionState = ROTATING;

        _leftStart  = getLeftOdom();
        _rightStart = getRightOdom();

        _brakingFactor = 1;
        // _yawTarget = _imu.getOffsetMagYaw(degrees);

        int32_t ticks = degreesToTurnTicks(degrees);

        _turnTarget = ticks;

        if (degrees > 0)
        {
          setDirection(RIGHT);
          _turnDir = -1;
        }
        else
        {
          setDirection(LEFT);
          _turnDir = 1;
        }

        // if(abs(degrees) <= 180)
        // {
        brakeTicks = metersToTicks(BRAKE_DISTANCE_METERS);
        // }
        // else
        // {
        //   brakeTicks = (int) (1.25 * metersToTicks(BRAKE_DISTANCE_METERS));
        // }

        _ble.send("rotating");
    }

    void stopMotion() {
        _motionState = IDLE;
        setDirection(STOP);

        _linearTarget = 0;
        _turnTarget = 0;
        _yawTarget = 0;
        
        _linearSpeedLeft = 0;
        _linearSpeedRight = 0;

        _leftStart = 0;
        _rightStart = 0;

        _brakingFactor = 1;

    }
    
    void updateMotion()
    {

        handleStall();

        if (_motionState == IDLE) return;

        unsigned long now = millis();
    
        // -----------------------------
        // Linear movement
        // -----------------------------
        if (_motionState == MOVING)
        {

            int32_t dl = getLeftOdom()  - _leftStart;
            int32_t dr = getRightOdom() - _rightStart;

            // positive if left has traveled farther than right
            int32_t error = dl - dr;

            // PD correction
            int correction = (int)(error * kP);

            _linearSpeedLeft  = _baseSpeedLeft  - correction;
            _linearSpeedRight = _baseSpeedRight + correction;

            _linearSpeedLeft  = constrain(_linearSpeedLeft,  MINIMUM_SPEED, _baseSpeedLeft  + 100);
            _linearSpeedRight = constrain(_linearSpeedRight, MINIMUM_SPEED, _baseSpeedRight + 100);

            setDirection(_dir);

            // stop if either wheel reached target
            int32_t progress =
                (abs(dl) > abs(dr))
                ? abs(dl)
                : abs(dr);

            int32_t remaining = abs(_linearTarget) - progress;

            // braking
            if (remaining <= brakeTicks && remaining > 0)
            {
                float f = (float)remaining / (float)brakeTicks;
                _brakingFactor = constrain(f, 0.15f, 1.0f);

                setDirection(_dir);
            }

            if (remaining <= 0)
            {
                stopMotion();
                _ble.send("stop linear");
                return;
            }
        }

        // -----------------------------
        // Rotation
        // -----------------------------
        else if (_motionState == ROTATING)
        {
            int32_t dl = getLeftOdom()  - _leftStart;
            int32_t dr = getRightOdom() - _rightStart;

            int32_t turn = max(abs(dl), abs(dr));

            int32_t remaining = abs(_turnTarget) - turn;

            if (remaining <= brakeTicks && remaining > 0)
            {
                float f = (float)remaining / (float)brakeTicks;
                _brakingFactor = constrain(f, 0.15f, 1.0f);

                setDirection(_dir);
            }

            if (remaining <= 0)
            {
              stopMotion();
              _ble.send("stop rotation");
              return;

            }

          
        }
    }

    void setKP(float kpNew)
    {
      kP = kpNew;
    }

    void setIdle()
    {
      _motionState = IDLE;
    }

    void setLeftBrakingFactor(float factor)
    {
      leftBrakingFactor = factor;
    }

    // ---- Accessors ----
    // bool availableA() const {
    //     return (millis() - _lastAUpdate) < 200;
    // }

    // bool availableB() const {
    //     return (millis() - _lastBUpdate) < 200;
    // }

    SerialHover2Server getA() const { return _feedbackA; }
    SerialHover2Server getB() const { return _feedbackB; }

    float getBattery() {
      return _feedbackA.iVolt / 100;
    }

private:
    enum MotionState {
        IDLE = 0,
        MOVING,
        ROTATING
    };
    MotionState _motionState = IDLE;

    HardwareSerial& _serialA; // Serial1
    HardwareSerial& _serialB; // Serial2

    // base speed without calibration and direction
    int _baseSpeedLeft = START_SPEED;
    int _baseSpeedRight = START_SPEED;

    // net speed after calibration and direction
    int _speedLeft = 0;
    int _speedRight = 0;

    // base speed during linear motion
    int _linearSpeedLeft = 0;
    int _linearSpeedRight = 0;

    int _dir[2] = {0, 0};
    float _cal[2] = {1.0f, 1.0f};

    uint8_t _stateRight = 0;
    uint8_t _stateLeft = 0;


    SerialHover2Server _feedbackA{};
    SerialHover2Server _feedbackB{};

    BLEModule& _ble;
    RotationSensor& _imu;

    unsigned long _nextSend = 0;
    unsigned long _sendInterval = 20;

    unsigned long _lastBle = 0;
    const unsigned long _bleInterval = 200;

    unsigned long _lastAUpdate = 0;
    unsigned long _lastBUpdate = 0;

    float kP = 1.5f;

    int32_t _leftStart = 0;
    int32_t _rightStart = 0;

    int32_t _linearTarget;
    int32_t _turnTarget = 0;
    float _yawTarget = 0;
    int _turnDir = 1;

    float _brakingFactor = 1.0f;
    

    uint32_t _leftStallStart = 0;
    uint32_t _rightStallStart = 0;

    unsigned long _motionStartTime = 0;
    unsigned long _lastProgressTime = 0;

    int32_t _lastMotionValue = 0;

    int32_t brakeTicks = metersToTicks(BRAKE_DISTANCE_METERS);

    float leftBrakingFactor = 1.0f;

    void sendCommands() {
        // Send via Serial1 TX (shared line)

        HoverSend(_serialA, 0, _speedLeft, _stateLeft);

        // small spacing (optional but still good practice)
        delayMicroseconds(200);

        HoverSend(_serialA, 1, _speedRight, _stateRight);
    }

    int32_t getLeftOdom() {
        return _feedbackA.iOdom;
    }

    int32_t getRightOdom() {
        return -_feedbackB.iOdom;  // invert once here
    }

    float ticksPerMeter() {
        return TICKS_PER_REV / (3.14159f * WHEEL_DIAMETER);
    }

    int32_t metersToTicks(float m) {
        return (int32_t)(m * ticksPerMeter());
    }

    int32_t degreesToTurnTicks(float deg)
    {
        float rad = deg * 3.1415926f / 180.0f;

        float halfWheelBase = WHEEL_BASE / 2.0f;

        float arc = rad * halfWheelBase;

        float ticks = arc * ticksPerMeter();

        return (int32_t)ticks;
    }

    void handleStall()
    {
      uint32_t now = millis();

      // LEFT MOTOR
      if (abs(_speedLeft) > MINIMUM_SPEED && abs(_feedbackA.iSpeed/10) < 50)
      {
          if (_leftStallStart == 0)
              _leftStallStart = now;

          if (now - _leftStallStart > STALL_TIME)
          {
              _ble.send("Left Stall");
              stopMotion();
          }
      }
      else
      {
          _leftStallStart = 0;
      }

      // RIGHT MOTOR
      if (abs(_speedRight) > MINIMUM_SPEED && abs(_feedbackB.iSpeed/10) < 50)
      {
          if (_rightStallStart == 0)
              _rightStallStart = now;

          if (now - _rightStallStart > STALL_TIME)
          {
              _ble.send("Right Stall");
              stopMotion();
          }
      }
      else
      {
          _rightStallStart = 0;
      }
    }
};


