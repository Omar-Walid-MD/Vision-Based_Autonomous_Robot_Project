#include "RotationSensor.h"
#include <ble.h>
#include "HoverboardController.h"
#include "globals.h"


bool startIMU = false;

int batSendInterval =  10 * 1000;
unsigned long batSendLast = 0;

#define PWM_FREQ 5000      // 5 kHz is good for LEDs
#define PWM_RESOLUTION 8         // 8-bit (0–255)

// -------- PIN CONFIG --------

// Serial1 → Board A + shared TX
#define RX1_PIN 18
#define TX_SHARED_PIN 17

// Serial2 → Board B RX only
#define RX2_PIN 16
#define TX2_UNUSED -1

#define IMU_TOGGLE 19

#define LED_R_PIN  37
#define LED_G_PIN  36
#define LED_B_PIN  35

BLEModule ble;

RotationSensor imu(ble);
HoverboardController hover(Serial1, Serial2, ble, imu);

void setRGB(uint8_t r, uint8_t g, uint8_t b) {
  ledcWrite(LED_R_PIN, r);
  ledcWrite(LED_G_PIN, g);
  ledcWrite(LED_B_PIN, b);
}

void updateBatLed() {
    float bat = hover.getBattery(); // assume 0–100 %

    bat = clampf(bat, 0.0f, 100.0f);

    RGB color;

    if (bat < 25.0f) {
        // Red → Orange
        float t = bat / 25.0f;
        color.r = 255;
        color.g = lerp(0, 165, t);
        color.b = 0;

    } else if (bat < 50.0f) {
        // Orange → Yellow
        float t = (bat - 25.0f) / 25.0f;
        color.r = 255;
        color.g = lerp(165, 255, t);
        color.b = 0;

    } else if (bat < 75.0f) {
        // Yellow → Green (lighter green transition)
        float t = (bat - 50.0f) / 25.0f;
        color.r = lerp(255, 0, t);
        color.g = 255;
        color.b = 0;

    } else {
        // Full Green
        color.r = 0;
        color.g = 255;
        color.b = 0;
    }

    setRGB(color.r, color.g, color.b);
}


void handleSerialInput(String cmd) {
    if (cmd.length() == 0) return;

    cmd.toLowerCase();

    if (cmd == "cc") {
      if(startIMU) imu.calibrateCompass(true);
    }
    else if (cmd == "cg") {
      if(startIMU) imu.calibrateGyro(true);
    }
    else if (cmd == "z") {
      if(startIMU)
      {
        imu.setZeroHeading();
        ble.send("Zero heading set! Current direction is now 0°.");
      }
    }

    else if(cmd == "on")
    {
      hover.on();
    }

    else if(cmd == "off")
    {
      hover.off();
    }

    else if(cmd == "reset")
    {
      ESP.restart();
    }

    else if(cmd == "resethover")
    {
      hover.reset();
    }

    else if (cmd.startsWith("move"))
    {
      float val = cmd.substring(4).toFloat();
      ble.send("moving");
      hover.move(val);
    }
    
    else if (cmd.startsWith("rot"))
    {
      float val = cmd.substring(3).toFloat();
      hover.rot(val);
    }

    else if(cmd.startsWith("kp"))
    {
      float val = cmd.substring(2).toFloat();
      hover.setKP(val);
    }

    else if(cmd.startsWith("lb"))
    {
      float val = cmd.substring(2).toFloat();
      hover.setLeftBrakingFactor(val);
    }

    // ---- CHANGE MODES ----
    else if (cmd == "mode2") {
      hover.setMode2();
      ble.send("Sent mode-2");
    }
    else if (cmd == "mode3") {
      hover.setMode3();
      ble.send("Sent mode-3");
    }

    else if (cmd.startsWith("cv"))
    {
        String payload = cmd.substring(2); // remove "cv"
        payload.trim();

        // ---- CHECK FOR SAVE FLAG ----
        bool save = false;
        if (payload.endsWith("s")) {
            save = true;
            payload = payload.substring(0, payload.length() - 1); // remove 's'
            payload.trim();
        }

        int dashIndex = payload.indexOf('-');
        if (dashIndex == -1) {
            Serial.println("Invalid format. Use: cv<left>-<right>[s]");
            return;
        }

        String leftStr  = payload.substring(0, dashIndex);
        String rightStr = payload.substring(dashIndex + 1);

        leftStr.trim();
        rightStr.trim();

        float calL = leftStr.toFloat();
        float calR = rightStr.toFloat();

        // Basic validation
        if (calL <= 0 || calR <= 0) {
            ble.send("Invalid calibration values");
            return;
        }

        hover.setCalibration(calL, calR);


        if (save) {
            hover.saveCalibration();
            ble.send("saved calibration");
        } else {
            Serial.println();
        }
    }

    else if (cmd.startsWith("e")) {
      int val = cmd.substring(1).toInt();
      if (val >= 0 && val <= 1000) hover.setSpeedRight(val);
    }

    else if (cmd.startsWith("q")) {
      int val = cmd.substring(1).toInt();
      if (val >= 0 && val <= 1000) hover.setSpeedLeft(val);
    }

    // ---- SPEED SET ----
    else if (cmd.startsWith("sp")) {
      int val = cmd.substring(2).toInt();
      if (val >= 0 && val <= 1000) hover.setSpeed(val);
    }

    else if (cmd.startsWith("x")) {
      cmd.remove(0, 1); // remove 'x'

      const int MAX_BYTES = 32;
      uint8_t buffer[MAX_BYTES];
      int count = 0;

      int start = 0;

      while (start < cmd.length() && count < MAX_BYTES) {
          int dashIndex = cmd.indexOf('-', start);

          String byteStr;
          if (dashIndex == -1) {
              byteStr = cmd.substring(start);
              start = cmd.length();
          } else {
              byteStr = cmd.substring(start, dashIndex);
              start = dashIndex + 1;
          }

          byteStr.trim();

          if (byteStr.length() == 0) continue;

          // Convert hex string to byte
          char* endptr;
          uint8_t value = (uint8_t) strtol(byteStr.c_str(), &endptr, 16);

          // Validate conversion
          if (*endptr != '\0') {
              Serial.print("Invalid hex: ");
              Serial.println(byteStr);
              return;
          }

          buffer[count++] = value;
      }

      // ---- DEBUG PRINT ----
      Serial.print("Parsed bytes: ");
      for (int i = 0; i < count; i++) {
          if (buffer[i] < 16) Serial.print("0");
          Serial.print(buffer[i], HEX);
          Serial.print(" ");
      }
      Serial.println();

      // ---- SEND ----
      HoverSendBytes(Serial1, buffer, count);
  }

  


  // ---- MOVEMENT COMMANDS ----
  else if (cmd == "f") {
      hover.setDirection(FORWARD);
      hover.setIdle();
      // ble.send("for");
  }
  else if (cmd == "b") {
      hover.setDirection(BACKWARD);
      hover.setIdle();
      // ble.send("back");
  }
  else if (cmd == "r") {
      hover.setDirection(RIGHT);
      hover.setIdle();
      // ble.send("right");
  }
  else if (cmd == "l") {
      hover.setDirection(LEFT);
      hover.setIdle();
      // ble.send("left");
  }
  else if (cmd == "s") {
      hover.setDirection(STOP);
      hover.setIdle();
      hover.stopMotion();
      // ble.send("stop");
  }
  else {
      ble.send("Unknown command");
  }
}

void setup() {

    Serial.begin(115200); // debug / Pi

    // Serial1: TX + RX
    Serial1.begin(19200, SERIAL_8N1, RX1_PIN, TX_SHARED_PIN);

    // Serial2: RX only
    Serial2.begin(19200, SERIAL_8N1, RX2_PIN, TX2_UNUSED);

    hover.loadCalibration();

    neopixelWrite(RGB_BUILTIN, RGB_BRIGHTNESS, 0, 0);  // Red
    
    // Your existing motor + LED + BLE setup...
    ble.begin("ESP32_BLE");
    ble.onReceive = handleSerialInput;

    pinMode(IMU_TOGGLE,INPUT_PULLUP);

    if(!digitalRead(IMU_TOGGLE)) 
    startIMU = true;

    // Initialize rotation sensors
    if(startIMU)
    {
      if (!imu.begin()) {
        while(1)
        {
          ble.send("IMU initialization failed!");
          delay(500);
        }
      }

      ble.send("Rotation sensors ready.");
      imu.printCalibration();

    }

    ledcAttach(LED_R_PIN, PWM_FREQ, PWM_RESOLUTION);
    ledcAttach(LED_G_PIN, PWM_FREQ, PWM_RESOLUTION);
    ledcAttach(LED_B_PIN, PWM_FREQ, PWM_RESOLUTION);


    batSendLast = millis() - batSendInterval;


    neopixelWrite(RGB_BUILTIN, 0, RGB_BRIGHTNESS, 0);  // Green

}

void loop() {

    if(startIMU)
    {
      imu.update();
    }

    hover.update();

    unsigned long now = millis();

    if(now - batSendLast >= batSendInterval)
    {
      float batVoltage = hover.getBattery();
      
      if(batVoltage > 0)
      {
        updateBatLed();
        ble.send("Bat: "+String(batVoltage)+"V");
        batSendLast = now;
      }
      
    }

}