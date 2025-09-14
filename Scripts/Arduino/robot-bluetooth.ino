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
int motorSpeed = 180;

// Encoder & wheel specs
const int PPR = 20;             // pulses per revolution (غير الرقم حسب الإنكودر)
const float wheelDiameter = 6.5; // cm
const float wheelCircumference = PI * wheelDiameter; // cm
float axleLength = 18.25;   //distance between the wheels cm

// Timing for automatic logging
unsigned long lastTime = 0;
bool isMoving = false;

// Distance accumulators
float totalLeftDistance = 0;
float totalRightDistance = 0;
float totalAvgDistance = 0;

float targetDistance = 0;


String msg = "";

// Bluetooth Serial
SoftwareSerial bluetoothSerial(A1, A0); // RX, TX

// ISR for Encoders
void countLeft()  { leftCount++; }
void countRight() { rightCount++; }

void setup() {
  Serial.begin(9600);
  bluetoothSerial.begin(9600);

  for (int i = 4; i <= 9; i++) pinMode(i, OUTPUT);

  pinMode(encoderLeft, INPUT);
  pinMode(encoderRight, INPUT);

  attachInterrupt(digitalPinToInterrupt(encoderLeft), countLeft, RISING);
  attachInterrupt(digitalPinToInterrupt(encoderRight), countRight, RISING);

  setMotorSpeeds(motorSpeed, motorSpeed);
  setMotorDirections(RELEASE, RELEASE);

  lastTime = millis();

  Serial.println("Robot Ready!");
  bluetoothSerial.println("Robot Ready!");
}

void loop() {
  // استقبال أوامر البلوتوث
  if (bluetoothSerial.available() > 0) {
    char c = bluetoothSerial.read();

    if(c == '\0')
    {
      totalLeftDistance  = 0;
      totalRightDistance = 0;
      totalAvgDistance = 0;

      int value = msg.substring(1).toInt();
      if(msg[0] == 'f')
      {
        targetDistance = value;
        setMotorDirections(FORWARD, FORWARD);
        bluetoothSerial.print("Move to: ");
        bluetoothSerial.println(targetDistance);
      }
      else if(msg[0] == 'r')
      {
        targetDistance = getRotationDistance(value);
        setMotorDirections(FORWARD, BACKWARD);
        bluetoothSerial.print("rotate to: ");
        bluetoothSerial.println(targetDistance);
      }


      
      isMoving = true;

      msg = "";
    }
    else
    {
      msg += c;
    }

    // switch (c) {
    //   case 'F': setMotorDirections(FORWARD, FORWARD); isMoving = true; break;
    //   case 'B': setMotorDirections(BACKWARD, BACKWARD); isMoving = true; break;
    //   case 'L': setMotorDirections(BACKWARD, FORWARD); isMoving = true; break;
    //   case 'R': setMotorDirections(FORWARD, BACKWARD); isMoving = true; break;
    //   case 'S': setMotorDirections(RELEASE, RELEASE); isMoving = false; break;

    //   default:
    //     if (isDigit(c)) {
    //       motorSpeed = map(c - '0', 0, 9, 100, 255);
    //       setMotorSpeeds(motorSpeed, motorSpeed);
    //       Serial.print("Speed set: ");
    //       Serial.println(motorSpeed);
    //       bluetoothSerial.print("Speed set: ");
    //       bluetoothSerial.println(motorSpeed);
    //     }
    //     break;
    // }
  }

  // حساب المسافة والسرعة أوتوماتيك كل ثانية
  if (isMoving && millis() - lastTime >= 10) {
    showDistanceAndSpeed();
    lastTime = millis();
  }
}

//Calculate wheel rotation for full 360° turn
float getRotationDistance(int rotation_angle)
{
    float angle_rad = rotation_angle * (PI / 180);

    float distance_per_wheel = (axleLength * angle_rad) / 2;
    return distance_per_wheel / (wheelDiameter/4);

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
  totalLeftDistance  += leftDistance;
  totalRightDistance += rightDistance;
  totalAvgDistance   += avgDistance;

  // Speed (cm/s) = distance in last second
  float leftSpeed  = leftDistance;
  float rightSpeed = rightDistance;
  float avgSpeed   = avgDistance;

  if(totalAvgDistance >= targetDistance)
  {
    setMotorDirections(RELEASE, RELEASE);
    isMoving = false;

    String message = "";
    message += "Left Dist: " + String(totalLeftDistance, 1) + " cm, ";
    message += "Right Dist: " + String(totalRightDistance, 1) + " cm, ";
    message += "Avg Dist: " + String(totalAvgDistance, 1) + " cm | ";
    message += "Speed: " + String(avgSpeed, 1) + " cm/s";

    // Print to Serial Monitor
    Serial.println(message);

    // Send via Bluetooth
    bluetoothSerial.println(message);
  }

  // Message string

  // Reset counters after each interval
  leftCount = 0;
  rightCount = 0;
}