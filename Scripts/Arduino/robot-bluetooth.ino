#include <SoftwareSerial.h>

//Motor Driver Pins
#define in1 4
#define in2 5
#define ena 6
#define in3 7
#define in4 8
#define enb 9

//Motor Directon Values
int FORWARD[] = {HIGH,LOW};
int BACKWARD[] = {LOW,HIGH};
int RELEASE[] = {LOW,LOW};

int speeds[] = {125,150,175,200,225,255};
int speedIndex = 5;

// uncommit this in case we need to receive a string not character from bluetooth
//String msg = "";

//Bluetooth Serial
SoftwareSerial bluetoothSerial(A1,A0); //RX, TX (connect Arduino RX to Bluetooth TX, Arduino TX to Bluetooth RX )

void setup() 
{
  Serial.begin(9600);
  bluetoothSerial.begin(9600);

  for(int i = 4; i <= 9; i++) pinMode(i,OUTPUT);

  setMotorSpeeds(speeds[speedIndex],speeds[speedIndex]);
  setMotorDirections(RELEASE,RELEASE);
}


void loop()
{

  //if message sent through bluetooth
  if(bluetoothSerial.available() > 0)
  {

    //get character
    char c = bluetoothSerial.read();

    //in case we need to get a string instead,
    //1- must end the string with a certain character [end_character] such as \n or \0 to know it's the end of the string
    //2- uncomment this code and comment out switch statement:

    // if(c == [end_character])
    // {
    //   if(msg == "Case 1")
    //   {
    //     ...
    //   }
    //   else if(msg == "Case 2")
    //   {
    //     ...
    //   }
    //   else
    //   {
    //     ...
    //   }

    //   msg = "";
    // }
    // else msg += c;

    switch(c)
    {
      case 'M': //Increase Speed
        speedIndex = min(speedIndex+1,5);
        setMotorSpeeds(speeds[speedIndex],speeds[speedIndex]);
        break;

      case 'N': //Decrease Speed
        speedIndex = max(speedIndex-1,0);
        setMotorSpeeds(speeds[speedIndex],speeds[speedIndex]);
        break;

      case 'F': //Move Forward
        Serial.println("Forward");
        setMotorDirections(FORWARD,FORWARD);
        break;

      case 'B': //move Backward
        Serial.println("Backward");
        setMotorDirections(BACKWARD,BACKWARD);
        break;

      case 'L': //Rotate Left
        Serial.println("Left");
        setMotorDirections(BACKWARD,FORWARD);
        break;

      case 'R': //Rotate Right
        Serial.println("Right");
        setMotorDirections(FORWARD,BACKWARD);
        break;

      case '0': //Stop
        Serial.println("Release");
        setMotorDirections(RELEASE,RELEASE);
        break;
    }      

  }
}

void setMotorSpeeds(int speedA, int speedB)
{
  analogWrite(ena,speedA);
  analogWrite(enb,speedB);
}

void setMotorDirections(int leftDirection[], int rightDirection[])
{
  digitalWrite(in1, rightDirection[0]);
  digitalWrite(in2, rightDirection[1]);

  digitalWrite(in3, leftDirection[0]);
  digitalWrite(in4, leftDirection[1]);
}

