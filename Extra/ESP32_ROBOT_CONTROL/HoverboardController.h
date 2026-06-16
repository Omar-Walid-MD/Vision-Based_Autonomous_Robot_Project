#pragma once

// #define _DEBUG
#define REMOTE_UARTBUS

#include "util.h"
#include "hoverserial.h"
#include "globals.h"
#include <HardwareSerial.h>
#include <ble.h>
#include <Preferences.h>

Preferences prefs;

struct CalibCycle {
  int durationSec;
  int speed;
};

#define START_SPEED 180
#define MINIMUM_SPEED 70

#define ROTATE_SPEED_S 100
#define ROTATE_SPEED_L 125

#define MOVE_SPEED 150

#define STALL_TIME 750

#define WHEEL_DIAMETER 0.16f   // meters (example)
#define WHEEL_BASE 0.53f    // meters (distance between wheels)
#define TICKS_PER_REV 90      // from hall sensors

#define HOVER_SWITCH 13


class HoverboardController {
public:
    // Constructor: two hardware serials
    HoverboardController(HardwareSerial& serialA,
                         HardwareSerial& serialB,
                         BLEModule& ble)
        : _serialA(serialA),
          _serialB(serialB),
          _ble(ble)
          {

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
      delay(200);
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


    // change direction
    void setDirection(const int* newDir)
    {
      _dir[0] = newDir[0]; _dir[1] = newDir[1];

      if(_motionState == MOVING)
      {
        _speedLeft = (int) (_dir[0] * _linearSpeedLeft * leftLinearCal * _leftBrakingFactor);
        _speedRight = (int) (_dir[1] * _linearSpeedRight * _rightBrakingFactor);
      }
      else if(_motionState == ROTATING)
      {
        _speedLeft = (int) (_dir[0] * _baseSpeedLeft * _cal[0] * _leftBrakingFactor);
        _speedRight = (int) (_dir[1] * _baseSpeedRight * _cal[1] * _rightBrakingFactor);
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
      updateOdometry();
      updatePath();

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

          // _ble.send("X: " + String(getPosX()) +"\nY: " + String(getPosY()) + "\nR: " + String(getHeadingDeg()));
          // _ble.send("Diff: " + String(getWheelDifferenceCm()));
          
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


    void startPath(PathCommand* cmds, int length)
    {
        if (length <= 0) return;

        stopPath();

        _pathLength = min(length, MAX_PATH_CMDS);

        for (int i = 0; i < _pathLength; i++)
        {
            _path[i] = cmds[i];
        }

        _pathIndex = 0;
        _pathRunning = true;

        runNextPathCommand();
    }

    void runNextPathCommand()
    {
        if (!_pathRunning) return;

        if (_pathIndex >= _pathLength)
        {
            stopPath();
            
            uint8_t packet[1];
            packet[0] = 0x01;
            Serial.write(packet,1);
            Serial.println("(sent stop ack)");

            _ble.send("path complete");
            return;
        }

        PathCommand& cmd = _path[_pathIndex];

        if (cmd.type == PATH_MOVE)
        {
            move(cmd.value);
        }
        else if (cmd.type == PATH_ROTATE)
        {
            rot(cmd.value);
        }
    }

    void stopPath()
    {
        _pathRunning = false;

        _pathLength = 0;
        _pathIndex = 0;

        _waitingNextPathCmd = false;
        _nextPathCmdTime = 0;

        stopMotion();
    }

    void move(float centimeters)
    {
        if (_motionState != IDLE) return;

        _leftStart  = getLeftOdom();
        _rightStart = getRightOdom();

        _linearTarget = metersToTicks(centimeters / 100.0f);

        brakeTicks = metersToTicks(brakeDistance);

        setSpeed(MOVE_SPEED);

        _leftBrakingFactor = 1;
        _rightBrakingFactor = 1;

        if (centimeters > 0)
            setDirection(FORWARD);
        else
            setDirection(BACKWARD);

        _motionState = MOVING;

        delay(100);

        _ble.send("moving");
    }


    void rot(float degrees) {

        if (_motionState != IDLE) return;

        _leftStart  = getLeftOdom();
        _rightStart = getRightOdom();

        _leftBrakingFactor = 1;
        _rightBrakingFactor = 1;

        int32_t ticks = degreesToTurnTicks(degrees);

        brakeDistance = 0.5f;
        brakePercent = 0.25f;

        brakeTicks = metersToTicks(brakeDistance);

        _turnTarget = ticks;

        if(abs(degrees) >= 180)
        {
          setSpeed(ROTATE_SPEED_L);
        }
        else
        {
          setSpeed(ROTATE_SPEED_S);
        }

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
        
        _motionState = ROTATING;

        _ble.send("rotating");

        delay(100);
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

        _leftBrakingFactor = 1;
        _rightBrakingFactor = 1;

    }

    void updatePath()
    {
        if (!_pathRunning) return;

        if (_waitingNextPathCmd)
        {
            if (millis() >= _nextPathCmdTime)
            {
                _waitingNextPathCmd = false;
                runNextPathCommand();
            }
        }
    }
    
    void updateMotion()
    {

        // handleStall();

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
            // _moveRampDistance = max((int32_t)1,min(brakeTicks, (int32_t)(abs(_linearTarget) * brakePercent)));

            // // accelerating
            // if (progress >= 0 && progress < _moveRampDistance)
            // {
            //     float f = (float)progress / (float)_moveRampDistance * 0.5;
            //     _leftBrakingFactor = constrain(0.5f + ((f+0.5) * (_cal[0] - 0.5f)), 0.5f, _cal[0]);
            //     _rightBrakingFactor = constrain(f+0.5, 0.5f, 1.0f);

            //     setDirection(_dir);
            // }

            float f = (float)progress / (float)_moveRampDistance;

            float cal;

            // --- extended strong boost phase ---
            // if (f < 0.3f)
            // {
            //     leftLinearCal = _cal[0];   // full calibration boost at start
            // }
            // else
            // {
            //     float g = (f - 0.3f) / 0.7f;
            //     g = g * g;       // smooth nonlinear fade
            //     leftLinearCal = _cal[0] - (_cal[0] - 1.0f) * g;
            // }

            // braking
            if (remaining <= _moveRampDistance && remaining > 0)
            {
                float f = (float)remaining / (float)_moveRampDistance;
                _leftBrakingFactor = constrain(f * leftBrakingFactorConstant, 0.15f, 1.0f);
                _rightBrakingFactor = constrain(f, 0.15f, 1.0f);

                setDirection(_dir);
            }
            else
            {
              _leftBrakingFactor = 1.0f;
              _rightBrakingFactor = 1.0f;
            }

            if (remaining <= 0)
            {
                stopMotion();

                if (_pathRunning)
                {
                    _pathIndex++;

                    _waitingNextPathCmd = true;
                    _nextPathCmdTime = millis() + _pathCmdDelay;
                    return;
                }
                
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

            _moveRampDistance = max((int32_t)1,min(brakeTicks, (int32_t)(abs(_linearTarget) * brakePercent)));

            if (remaining <= _moveRampDistance && remaining > 0)
            {
                float f = (float)remaining / (float)_moveRampDistance * 0.5;
                _leftBrakingFactor = constrain((f + 0.5) * leftBrakingFactorConstant, 0.5f, 1.0f);
                _rightBrakingFactor = constrain(f + 0.5, 0.5f, 1.0f);

                setDirection(_dir);
            }

            if (remaining <= 0)
            {
              stopMotion();

              if (_pathRunning)
              {
                  _pathIndex++;

                  _waitingNextPathCmd = true;
                  _nextPathCmdTime = millis() + _pathCmdDelay;
                  return;
              }

              _ble.send("stop rotation");
              return;

            }

          
        }
    }

    void updateOdometry() {
        if (_lastAUpdate == 0 || _lastBUpdate == 0) return;

        int32_t curL = getLeftOdom();
        int32_t curR = getRightOdom();

        int32_t dTicksL = curL - _prevLeftTicks;
        int32_t dTicksR = curR - _prevRightTicks;

        _prevLeftTicks  = curL;
        _prevRightTicks = curR;

        float tpm = ticksPerMeter();
        float dL = dTicksL / tpm;
        float dR = dTicksR / tpm;

        float ds     = (dL + dR) * 0.5f;
        float dTheta = (dR - dL) / WHEEL_BASE;

        float midTheta = _heading + dTheta * 0.5f;

        _posX    += ds * sinf(midTheta);
        _posY    += ds * cosf(midTheta);
        _heading += dTheta;

        while (_heading >  M_PI) _heading -= 2.0f * M_PI;
        while (_heading < -M_PI) _heading += 2.0f * M_PI;

        _totalTicksL += dTicksL;
        _totalTicksR += dTicksR;
    }

    float getPosX()    const { return _posX; }
    float getPosY()    const { return _posY; }
    float getHeadingRad() const { return _heading; }
    float getHeadingDeg() const { return _heading * 180.0f / M_PI; }

    float getWheelDifferenceCm() {
        float tpm = ticksPerMeter();
        return ((_totalTicksR - _totalTicksL) / tpm) * 100.0f; // cm
    }

    void resetPose() {
        _posX = 0; _posY = 0; _heading = 0;
        _prevLeftTicks = getLeftOdom();
        _prevRightTicks = getRightOdom();

        _totalTicksL = 0;
        _totalTicksR = 0;

    }

    void setKP(float kpNew)
    {
      kP = kpNew;
    }

    void setKYaw(float kyNew)
    {
      kYaw  = kyNew;
    }

    void setIdle()
    {
      _motionState = IDLE;
    }

    void setLeftBrakingFactor(float factor)
    {
      leftBrakingFactorConstant = factor;
    }

    void setBrakeDistance(float bd)
    {
      brakeDistance = bd;
    }

    void setBrakePercent(float bp)
    {
      brakePercent = bp;
    }

    SerialHover2Server getA() const { return _feedbackA; }
    SerialHover2Server getB() const { return _feedbackB; }

    float getBattery() {
      return _feedbackA.iVolt / 100;
    }

    bool isIdle()
    {
      return _motionState == IDLE;
    }

    bool isDirection(const int* checkDir)
    {
      return _dir[0] == checkDir[0] && _dir[1] == checkDir[1];
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

    unsigned long _nextSend = 0;
    unsigned long _sendInterval = 20;

    unsigned long _lastBle = 0;
    const unsigned long _bleInterval = 200;

    unsigned long _lastAUpdate = 0;
    unsigned long _lastBUpdate = 0;

    float kP = 3.5f;

    int32_t _leftStart = 0;
    int32_t _rightStart = 0;

    int32_t _linearTarget;
    int32_t _turnTarget = 0;
    float _yawTarget = 0;
    int _turnDir = 1;

    float _leftBrakingFactor = 1.0f;
    float _rightBrakingFactor = 1.0f;

    uint32_t _leftStallStart = 0;
    uint32_t _rightStallStart = 0;

    unsigned long _motionStartTime = 0;
    unsigned long _lastProgressTime = 0;

    int32_t _lastMotionValue = 0;

    float brakeDistance = 0.3f; //meters
    float brakePercent = 0.25f; //percent

    int32_t _moveRampDistance = 0;

    int32_t brakeTicks = metersToTicks(brakeDistance);

    float leftBrakingFactorConstant = 0.75f;
    float leftLinearCal = 1.0f;

    int32_t _totalTicksL = 0;
    int32_t _totalTicksR = 0;

    // path variables

    static const int MAX_PATH_CMDS = 20;

    PathCommand _path[MAX_PATH_CMDS];

    int _pathLength = 0;
    int _pathIndex = 0;

    bool _pathRunning = false;

    bool _waitingNextPathCmd = false;

    unsigned long _nextPathCmdTime = 0;

    unsigned long _pathCmdDelay = 1000; // ms


    // position tracking variables
    // Odometry pose
    float _posX    = 0.0f;   // metres, east
    float _posY    = 0.0f;   // metres, north
    float _heading = 0.0f;   // radians, 0 = north (Y+)

    int32_t _prevLeftTicks  = 0;
    int32_t _prevRightTicks = 0;

    float _startYaw = 0.0f;
    float kYaw = 2.0f; // tune this

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

    // void handleStall()
    // {
    //   uint32_t now = millis();

    //   // LEFT MOTOR
    //   if (abs(_speedLeft) > MINIMUM_SPEED && abs(_feedbackA.iSpeed/10) < 50)
    //   {
    //       if (_leftStallStart == 0)
    //           _leftStallStart = now;

    //       if (now - _leftStallStart > STALL_TIME)
    //       {
    //           _ble.send("Left Stall");
    //           stopMotion();
    //       }
    //   }
    //   else
    //   {
    //       _leftStallStart = 0;
    //   }

    //   // RIGHT MOTOR
    //   if (abs(_speedRight) > MINIMUM_SPEED && abs(_feedbackB.iSpeed/10) < 50)
    //   {
    //       if (_rightStallStart == 0)
    //           _rightStallStart = now;

    //       if (now - _rightStallStart > STALL_TIME)
    //       {
    //           _ble.send("Right Stall");
    //           stopMotion();
    //       }
    //   }
    //   else
    //   {
    //       _rightStallStart = 0;
    //   }
    // }
};



