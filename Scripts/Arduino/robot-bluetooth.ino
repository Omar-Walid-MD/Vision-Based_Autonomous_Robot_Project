#include <SoftwareSerial.h>

// Motor Driver Pins
#define in1 4
#define in2 5
#define ena 6
#define in3 7
#define in4 8
#define enb 9

// Encoder Pins
#define encoderLeft 2   // Interrupt 0
#define encoderRight 3  // Interrupt 1

// Motor Direction Values
int FORWARD[]  = {HIGH, LOW};
int BACKWARD[] = {LOW, HIGH};
int RELEASE[]  = {LOW, LOW};

// Encoder Counters
volatile long leftCount = 0;
volatile long rightCount = 0;

// Default speed
int maxMotorSpeed = 100;

// Encoder & wheel specs
const int PPR = 20;             // pulses per revolution (غير الرقم حسب الإنكودر)
const float wheelDiameter = 6.5; // cm
const float wheelCircumference = PI * wheelDiameter; // cm

// Timing for automatic logging
unsigned long lastTime = 0;
bool isMoving = false;

// Distance accumulators
float totalLeftDistance = 0;
float totalRightDistance = 0;
float totalAvgDistance = 0;

float targetDistance = 0;

float axle_length = 17.9;   //cm

String msg = "";
float sendOnce = false;

long stopLeftCount = 0;
long stopRightCount = 0;

#define sign(x) ((x) < 0 ? -1 : ((x) > 0 ? 1 : 0))

// Bluetooth Serial
SoftwareSerial bluetoothSerial(A1, A0); // RX, TX

// ISR for Encoders
void countLeft()  { leftCount++; }
void countRight() { rightCount++; }

void setup() {
  // Serial.begin(9600);
  bluetoothSerial.begin(9600);

  for (int i = 4; i <= 9; i++) pinMode(i, OUTPUT);

  pinMode(encoderLeft, INPUT);
  pinMode(encoderRight, INPUT);

  attachInterrupt(digitalPinToInterrupt(encoderLeft), countLeft, RISING);
  attachInterrupt(digitalPinToInterrupt(encoderRight), countRight, RISING);

  setMotorSpeeds(maxMotorSpeed, maxMotorSpeed);
  setMotorDirections(RELEASE, RELEASE);

  lastTime = millis();

  // Serial.println("Robot Ready!");
  bluetoothSerial.println("Robot Ready!");
}

void loop() {
  // استقبال أوامر البلوتوث
  if (bluetoothSerial.available() > 0) {
    char c = bluetoothSerial.read();

    if(c == '\0')
    {
  
      int value = msg.substring(1).toInt();
      if(msg[0] == 'f')
      {
        isMoving = true;
        targetDistance = value;
        setMotorSpeeds(maxMotorSpeed, maxMotorSpeed);
        setMotorDirections(FORWARD, FORWARD);
        bluetoothSerial.print("Move to: ");
        bluetoothSerial.println(targetDistance);
      }
      else if(msg[0] == 'r')
      {
        isMoving = true;
        targetDistance = getRotationDistance(value);
        int angleSign = sign(value);
        setMotorSpeeds(maxMotorSpeed, maxMotorSpeed);
        if(angleSign == 1) setMotorDirections(FORWARD, BACKWARD);
        else if(angleSign == -1) setMotorDirections(BACKWARD, FORWARD);
        else isMoving = false;
        bluetoothSerial.print("rotate to: ");
        bluetoothSerial.println(targetDistance);
        
      }
      else if(msg[0] == 'm')
      {
        setMotorSpeeds(value, value);
        bluetoothSerial.print("set speed to: ");
        bluetoothSerial.println(value);
      }
      else
      {
        setMotorSpeeds(maxMotorSpeed, maxMotorSpeed);
        switch (msg[0])
        {
          case 'F': setMotorDirections(FORWARD, FORWARD); break;
          case 'B': setMotorDirections(BACKWARD, BACKWARD); break;
          case 'L': setMotorDirections(BACKWARD, FORWARD); break;
          case 'R': setMotorDirections(FORWARD, BACKWARD); break;
          case 'S': setMotorDirections(RELEASE, RELEASE); break;

          default: break;
        }
      }

      

      msg = "";
    }
    else
    {
      msg += c;
    }

    
  }

  // حساب المسافة والسرعة أوتوماتيك كل ثانية
  if (millis() >= 10) {
    if(isMoving)
    {
      showDistanceAndSpeed();
    }
    else if(sendOnce) {
      delay(500); // wait a bit for coasting to finish
      long finalLeft = leftCount;
      long finalRight = rightCount;

      String message = "After Coasting:\nLeft: " + String(finalLeft) + 
                      "\tRight: " + String(finalRight) +
                      "\nExtra Movement = L:" + String(finalLeft - stopLeftCount) + 
                      "  R:" + String(finalRight - stopRightCount);
      bluetoothSerial.println(message);

      // Now safe to reset
      leftCount = 0;
      rightCount = 0;
      sendOnce = false;
    }
    lastTime = millis();
  }

}

float getRotationDistance(int rotation_angle)
{
  float errorOffset = 20;
  float angle_rad = (abs(rotation_angle) - errorOffset) * (PI / 180.0);
  float distance_per_wheel = (axle_length * angle_rad) / 2.0;
  return distance_per_wheel;
}

void setMotorSpeeds(int speedA, int speedB) {
  analogWrite(ena, speedA);
  analogWrite(enb, speedB);
}

void setMotorDirections(int leftDirection[], int rightDirection[]) {
  digitalWrite(in1, rightDirection[0]);
  digitalWrite(in2, rightDirection[1]);

  digitalWrite(in3, leftDirection[0]);
  digitalWrite(in4, leftDirection[1]);
}

void showDistanceAndSpeed() {
  // Revolutions
  float leftRevolutions  = (float)leftCount / PPR;
  float rightRevolutions = (float)rightCount / PPR;

  // Distances in this interval
  float leftDistance  = leftRevolutions * wheelCircumference;
  float rightDistance = rightRevolutions * wheelCircumference;
  float avgDistance   = (leftDistance + rightDistance) / 2.0;

  // Update total distances
  totalLeftDistance  = leftDistance;
  totalRightDistance = rightDistance;
  totalAvgDistance   = avgDistance;

  // Speed (cm/s) = distance in last second
  // float leftSpeed  = leftDistance;
  // float rightSpeed = rightDistance;
  // float avgSpeed   = avgDistance;

  // float remaining = targetDistance - totalAvgDistance;
  // if (remaining < 8.0) {   // last 5 cm
  //   setMotorSpeeds(100, 100); // slow down
  //   bluetoothSerial.println("Slowing down...");

  // }

  if(totalAvgDistance >= targetDistance)
  {
    isMoving = false;

    stopLeftCount = leftCount;
    stopRightCount = rightCount;


    setMotorDirections(BACKWARD, BACKWARD);
    delay(50); // tweak experimentally (e.g., 20–80 ms)
    setMotorDirections(RELEASE, RELEASE);

    String message = "";
    message += "Left Dist: " + String(totalLeftDistance, 1) + " cm, ";
    message += "Right Dist: " + String(totalRightDistance, 1) + " cm, ";
    message += "Avg Dist: " + String(totalAvgDistance, 1) + " cm | ";
    // message += "Speed: " + String(avgSpeed, 1) + " cm/s";

    // Print to Serial Monitor
    // Serial.println(message);

    // Record counts at the instant of stopping

    message += "\nLeft: " + String(stopLeftCount) + "\tRight: " + String(stopRightCount);

    // Send via Bluetooth
    bluetoothSerial.println(message);

    totalLeftDistance  = 0;
    totalRightDistance = 0;
    totalAvgDistance = 0;

    sendOnce = true;
  }

  
}