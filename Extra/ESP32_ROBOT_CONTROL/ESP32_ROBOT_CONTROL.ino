#include "globals.h"
#include <ble.h>
#include "HoverboardController.h"
// #include "ObstacleDetection.h"

bool canMoveForward = true;
bool piActive = false;


int batSendInterval =  5 * 1000;
unsigned long batSendLast = 0;

// -------- PIN CONFIG --------

#define VBAT 4
#define LATCH 14
#define SWITCH_IN 10

// Serial1 → Board A + shared TX
#define RX1_PIN 18
#define TX_SHARED_PIN 17

// Serial2 → Board B RX only
#define RX2_PIN 16
#define TX2_UNUSED -1


BLEModule ble;

HoverboardController hover(Serial1, Serial2, ble);

volatile bool shutdownRequested = false;

void ICACHE_RAM_ATTR buttonISR() {
  shutdownRequested = true;
}

void onObstacleStop() {
   
    return;
    if(canMoveForward)
    {
      canMoveForward = false;
    }

    if(hover.isDirection(FORWARD)) hover.stopMotion();
}

void onObstacleClear() {
    canMoveForward = true;
}


void handleBluetoothInput(String cmd) {
    if (cmd.length() == 0) return;

    cmd.toLowerCase();


    // commands
    if(cmd == "on")
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

    else if(cmd == "rh")
    {
      hover.reset();
    }

    else if(cmd == "rp")
    {
      hover.resetPose();
    }

    // movement commands

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

    else if (cmd.startsWith("path:"))
    {
        String data = cmd.substring(5);

        PathCommand cmds[20];

        int cmdCount = 0;

        while (data.length() > 0 && cmdCount < 20)
        {
            int sep = data.indexOf(';');

            String token;

            if (sep >= 0)
            {
                token = data.substring(0, sep);
                data = data.substring(sep + 1);
            }
            else
            {
                token = data;
                data = "";
            }

            int comma = token.indexOf(',');

            if (comma < 0) continue;

            String typeStr = token.substring(0, comma);

            float value =
                token.substring(comma + 1).toFloat();

            if (typeStr == "m")
            {
                cmds[cmdCount++] =
                {
                    PATH_MOVE,
                    value
                };
            }
            else if (typeStr == "r")
            {
                cmds[cmdCount++] =
                {
                    PATH_ROTATE,
                    value
                };
            }
        }

        hover.startPath(cmds, cmdCount);
    }

    // parameter setting commands

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

    else if(cmd.startsWith("bd"))
    {
      float val = cmd.substring(2).toFloat();
      hover.setBrakeDistance(val);
    }

    else if(cmd.startsWith("bp"))
    {
      float val = cmd.substring(2).toFloat();
      hover.setBrakePercent(val);
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
      if(canMoveForward)
      {
        hover.setDirection(FORWARD);
        hover.setIdle();
        // ble.send("for");
      }
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
      hover.stopPath();
      // ble.send("stop");
  }
  else {
      ble.send("Unknown command");
  }
}

void handleSerialInput(String cmd) {
    if (cmd.length() == 0) return;

    cmd.toLowerCase();

    if(cmd == "pi-active")
    {
      piActive = true;
    }

    // if(!piActive) return;

    else if(cmd == "spin")
    {
      hover.rot(360.0f);
    }

    else if (cmd.startsWith("path:"))
    {
        String data = cmd.substring(5);

        PathCommand cmds[20];

        int cmdCount = 0;

        while (data.length() > 0 && cmdCount < 20)
        {
            int sep = data.indexOf(';');

            String token;

            if (sep >= 0)
            {
                token = data.substring(0, sep);
                data = data.substring(sep + 1);
            }
            else
            {
                token = data;
                data = "";
            }

            int comma = token.indexOf(',');

            if (comma < 0) continue;

            String typeStr = token.substring(0, comma);

            float value =
                token.substring(comma + 1).toFloat();

            if (typeStr == "m")
            {
                cmds[cmdCount++] =
                {
                    PATH_MOVE,
                    value
                };
            }
            else if (typeStr == "r")
            {
                cmds[cmdCount++] =
                {
                    PATH_ROTATE,
                    value
                };
            }
        }

        hover.startPath(cmds, cmdCount);
    }

}

void setup() {

    // set latch to high
    pinMode(LATCH, OUTPUT);
    digitalWrite(LATCH, HIGH);

    pinMode(SWITCH_IN, INPUT_PULLUP);

    attachInterrupt(
      digitalPinToInterrupt(SWITCH_IN),
      buttonISR,
      FALLING
    );

    Serial.begin(115200); // debug / Pi

    // Serial1: TX + RX
    Serial1.begin(19200, SERIAL_8N1, RX1_PIN, TX_SHARED_PIN);

    // Serial2: RX only
    Serial2.begin(19200, SERIAL_8N1, RX2_PIN, TX2_UNUSED);

    hover.loadCalibration();

    // obstacleDetection_init(onObstacleStop,onObstacleClear);

    neopixelWrite(RGB_BUILTIN, RGB_BRIGHTNESS, 0, 0);  // Red
    
    // Your existing motor + LED + BLE setup...
    ble.begin("ESP32_BLE");
    ble.onReceive = handleBluetoothInput;

    batSendLast = millis() - batSendInterval;

    neopixelWrite(RGB_BUILTIN, 0, RGB_BRIGHTNESS, 0);  // Green

}

void loop() {

    unsigned long now = millis();

    // update hover
    hover.update();

    // update battery
    if(now - batSendLast >= batSendInterval)
    {
      float batVoltage = hover.getBattery();
      
      if(batVoltage > 0)
      {
        ble.send("Bat: "+String(batVoltage)+"V");
        batSendLast = now;
      }
      
    }

    if (shutdownRequested) {
      Serial.println("Shutdown requested");

      delay(100);

      digitalWrite(LATCH, LOW);

      while (true) {
        delay(1000);
      }
    }

    // obstacleDetection_update();
}