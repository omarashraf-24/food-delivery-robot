#include <Arduino.h>
#include <HardwareSerial.h>

// PIN CONFIGURATION
const int MOTOR_LEFT_PWM = 32;
const int MOTOR_RIGHT_PWM = 33;
const int MOTOR_LEFT_DIR = 25;
const int MOTOR_RIGHT_DIR = 26;
const int HALL_LEFT = 34;
const int HALL_RIGHT = 35;

// MOTOR CONSTANTS
const float MAX_SPEED = 1.5;
const float WHEEL_DIAMETER = 0.165;
const float WHEEL_CIRCUMFERENCE = 3.14159 * WHEEL_DIAMETER;
const int POLES = 15;

// PWM settings
const int PWM_FREQ = 20000;
const int PWM_RES = 8;
const int PWM_MAX = 255;

// STATE
volatile long hallCounterLeft = 0;
volatile long hallCounterRight = 0;
float rpmLeft = 0;
float rpmRight = 0;
unsigned long lastCalcTime = 0;
const unsigned long CALC_INTERVAL = 100;

// ISR
void IRAM_ATTR hallISRLeft() { hallCounterLeft++; }
void IRAM_ATTR hallISRRight() { hallCounterRight++; }

void updateRPM() {
    unsigned long currentTime = millis();
    unsigned long deltaTime = currentTime - lastCalcTime;
    
    if (deltaTime > 0) {
        float rotationsLeft = (float)hallCounterLeft / POLES;
        float rotationsRight = (float)hallCounterRight / POLES;
        
        rpmLeft = (rotationsLeft / deltaTime) * 60000;
        rpmRight = (rotationsRight / deltaTime) * 60000;
        
        hallCounterLeft = 0;
        hallCounterRight = 0;
    }
}

float ms_to_rpm(float speed_ms) {
    if (speed_ms == 0) return 0;
    return (speed_ms / WHEEL_CIRCUMFERENCE) * 60.0;
}

void setMotorSpeed(float leftSpeed, float rightSpeed) {
    leftSpeed = constrain(leftSpeed, -MAX_SPEED, MAX_SPEED);
    rightSpeed = constrain(rightSpeed, -MAX_SPEED, MAX_SPEED);
    
    float rpmTargetLeft = ms_to_rpm(leftSpeed);
    float rpmTargetRight = ms_to_rpm(rightSpeed);
    
    int pwmLeft = (int)map(abs(rpmTargetLeft), 0, 300, 0, PWM_MAX);
    int pwmRight = (int)map(abs(rpmTargetRight), 0, 300, 0, PWM_MAX);
    
    digitalWrite(MOTOR_LEFT_DIR, (leftSpeed >= 0) ? HIGH : LOW);
    digitalWrite(MOTOR_RIGHT_DIR, (rightSpeed >= 0) ? HIGH : LOW);
    
    ledcWrite(0, pwmLeft);
    ledcWrite(1, pwmRight);
}

void processSerial() {
    if (Serial.available()) {
        String command = Serial.readStringUntil('\n');
        command.trim();
        
        int commaIdx = command.indexOf(',');
        if (commaIdx != -1) {
            float speedL = command.substring(0, commaIdx).toFloat();
            float speedR = command.substring(commaIdx + 1).toFloat();
            setMotorSpeed(speedL, speedR);
        }
    }
}

void setup() {
    Serial.begin(115200);
    
    ledcSetup(0, PWM_FREQ, PWM_RES);
    ledcSetup(1, PWM_FREQ, PWM_RES);
    
    ledcAttachPin(MOTOR_LEFT_PWM, 0);
    ledcAttachPin(MOTOR_RIGHT_PWM, 1);
    
    pinMode(MOTOR_LEFT_DIR, OUTPUT);
    pinMode(MOTOR_RIGHT_DIR, OUTPUT);
    pinMode(HALL_LEFT, INPUT_PULLUP);
    pinMode(HALL_RIGHT, INPUT_PULLUP);
    
    attachInterrupt(digitalPinToInterrupt(HALL_LEFT), hallISRLeft, CHANGE);
    attachInterrupt(digitalPinToInterrupt(HALL_RIGHT), hallISRRight, CHANGE);
    
    setMotorSpeed(0, 0);
    
    Serial.println("ESP32 Motor Controller Ready!");
}

void loop() {
    processSerial();
    
    if (millis() - lastCalcTime >= CALC_INTERVAL) {
        updateRPM();
        lastCalcTime = millis();
        
        Serial.print(rpmLeft);
        Serial.print(",");
        Serial.print(rpmRight);
        Serial.print(",");
        Serial.println(40);
    }
    
    delay(10);
}
