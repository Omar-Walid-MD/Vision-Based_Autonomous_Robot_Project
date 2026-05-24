#pragma once
#include <ble.h>

#define OBS_BLE_INTERVAL_MS  200   // send BLE update every 1000 ms

// ─── External BLE instance (defined in main .ino) ────────────────────────────
extern BLEModule ble;


// ─── Pin Definitions ──────────────────────────────────────────────────────────
#define SONAR_L_TRIG    39
#define SONAR_L_ECHO    40
#define SONAR_M_TRIG    37
#define SONAR_M_ECHO    38
#define SONAR_R_TRIG    7
#define SONAR_R_ECHO    6

// ─── Thresholds (cm) ─────────────────────────────────────────────────────────
#define DIST_STOP        15.0f
#define DIST_WARN        50.0f
#define DIST_MAX           150.0f
#define SONAR_TIMEOUT_US   8741UL

// ─── Filter Settings ─────────────────────────────────────────────────────────
#define OBS_FILTER_SAMPLES     5      // number of readings to average
#define OBS_CONFIRM_FRAMES     3      // consecutive filtered readings before triggering

// ─── Obstacle location bitmask ───────────────────────────────────────────────
typedef enum : uint8_t {
    OBS_NONE        = 0b000,
    OBS_RIGHT       = 0b001,
    OBS_MIDDLE      = 0b010,
    OBS_LEFT        = 0b100,
    OBS_RIGHT_MID   = 0b011,
    OBS_LEFT_MID    = 0b110,
    OBS_LEFT_RIGHT  = 0b101,
    OBS_WALL        = 0b111,
} ObstacleLocation;

// ─── Shared sensor state ─────────────────────────────────────────────────────
struct SensorReading {
    float            distL;
    float            distM;
    float            distR;
    ObstacleLocation location;
    bool             hardStop;
    bool             warn;
    uint32_t         timestamp;
};

// ─── Internal state (inline to avoid multiple definition errors) ──────────────
static SemaphoreHandle_t  s_mutex       = nullptr;
static SensorReading      s_reading     = {};
static void             (*s_motorStop)() = nullptr;
static void             (*s_motorResume)()  = nullptr;   // add alongside s_motorStop
static bool               s_wasInStop        = false;     // tracks previous hardStop state


// ─── Filter state ─────────────────────────────────────────────────────────────
static float    s_filterBufL[OBS_FILTER_SAMPLES] = {};
static float    s_filterBufM[OBS_FILTER_SAMPLES] = {};
static float    s_filterBufR[OBS_FILTER_SAMPLES] = {};
static uint8_t  s_filterIdx       = 0;
static uint8_t  s_stopFrameCount  = 0;   // consecutive frames in STOP zone
static uint8_t  s_clearFrameCount = 0;   // consecutive frames outside STOP zone

// ─── Median of 3 (spike rejection) ───────────────────────────────────────────
// Removes single outlier spikes before they enter the rolling average.
static inline float medianOf3(float a, float b, float c) {
    if (a > b) { float t = a; a = b; b = t; }
    if (b > c) { float t = b; b = c; c = t; }
    if (a > b) { float t = a; a = b; b = t; }
    return b;  // middle value
}

// ─── Rolling average over ring buffer ────────────────────────────────────────
static inline float rollingAvg(float* buf, uint8_t newVal) {
    buf[s_filterIdx] = newVal;
    float sum = 0;
    for (int i = 0; i < OBS_FILTER_SAMPLES; i++) sum += buf[i];
    return sum / OBS_FILTER_SAMPLES;
}


// ─── HC-SR04 single measurement ──────────────────────────────────────────────
static inline float readSonar(uint8_t trigPin, uint8_t echoPin) {
    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);
    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin, LOW);

    unsigned long duration = pulseIn(echoPin, HIGH, SONAR_TIMEOUT_US);
    if (duration == 0) return DIST_MAX;
    float cm = (duration * 0.0343f) / 2.0f;
    return (cm > DIST_MAX) ? DIST_MAX : cm;
}


// ─── Obstacle classifier ─────────────────────────────────────────────────────
static inline ObstacleLocation classifyObstacle(float dL, float dM, float dR) {
    constexpr float COS30 = 0.866f;
    float fwdL = dL * COS30;
    float fwdM = dM;
    float fwdR = dR * COS30;

    uint8_t bits = OBS_NONE;
    if (fwdL < DIST_STOP * 0.7f) bits |= OBS_LEFT;
    if (fwdM < DIST_STOP) bits |= OBS_MIDDLE;
    if (fwdR < DIST_STOP * 0.7f) bits |= OBS_RIGHT;

    return static_cast<ObstacleLocation>(bits);
}

// ─── FreeRTOS sensor task ─────────────────────────────────────────────────────
static void sensorTask(void* pvParams) {
    const uint8_t trigPins[] = { SONAR_L_TRIG, SONAR_M_TRIG, SONAR_R_TRIG };
    const uint8_t echoPins[] = { SONAR_L_ECHO, SONAR_M_ECHO, SONAR_R_ECHO };

    for (int i = 0; i < 3; i++) {
        pinMode(trigPins[i], OUTPUT);
        pinMode(echoPins[i], INPUT);
        digitalWrite(trigPins[i], LOW);
    }

    // Pre-fill rolling average buffers with DIST_MAX so the robot
    // doesn't false-trigger on startup before buffers are populated
    for (int i = 0; i < OBS_FILTER_SAMPLES; i++) {
        s_filterBufL[i] = DIST_MAX;
        s_filterBufM[i] = DIST_MAX;
        s_filterBufR[i] = DIST_MAX;
    }

    for (;;) {
        // ─── Stage 1: 3 reads per sensor for median spike rejection ──────────
        float rawL = readSonar(SONAR_L_TRIG, SONAR_L_ECHO); vTaskDelay(pdMS_TO_TICKS(10));
        float rawM = readSonar(SONAR_M_TRIG, SONAR_M_ECHO); vTaskDelay(pdMS_TO_TICKS(10));
        float rawR = readSonar(SONAR_R_TRIG, SONAR_R_ECHO); vTaskDelay(pdMS_TO_TICKS(10));

  

        // ─── Stage 3: confirmation frames ────────────────────────────────────
        ObstacleLocation loc = classifyObstacle(rawL, rawM, rawR);
        bool hardStop = (loc != OBS_NONE);


        // ─── Warn zone (only meaningful when not in hard stop) ────────────────
        bool warn = false;
        if (!hardStop) {
            constexpr float COS30 = 0.866f;
            warn = (rawL * COS30 < DIST_WARN) ||
                   (rawM        < DIST_WARN) ||
                   (rawR * COS30 < DIST_WARN);
        }

        // ─── Edge-triggered callbacks ─────────────────────────────────────────
        if (hardStop && !s_wasInStop) {
            if (s_motorStop != nullptr) s_motorStop();
        } else if (!hardStop && s_wasInStop) {
            if (s_motorResume != nullptr) s_motorResume();
        }
        s_wasInStop = hardStop;

        // ─── Update shared state ──────────────────────────────────────────────
        if (xSemaphoreTake(s_mutex, pdMS_TO_TICKS(5)) == pdTRUE) {
            s_reading.distL     = rawL;
            s_reading.distM     = rawM;
            s_reading.distR     = rawR;
            s_reading.location  = loc;
            s_reading.hardStop  = hardStop;
            s_reading.warn      = warn;
            s_reading.timestamp = millis();
            xSemaphoreGive(s_mutex);
        }
    }
}

// ─── Public API ───────────────────────────────────────────────────────────────
static inline void obstacleDetection_init(void (*motorStopCallback)(), void (*motorResumeCallback)()) {
    s_motorStop   = motorStopCallback;
    s_motorResume = motorResumeCallback;
    s_mutex       = xSemaphoreCreateMutex();

    xTaskCreatePinnedToCore(
        sensorTask,
        "SonarTask",
        4096,
        nullptr,
        2,
        nullptr,
        0
    );
}

static inline SensorReading obstacleDetection_getReading() {
    SensorReading snap = {};
    if (xSemaphoreTake(s_mutex, pdMS_TO_TICKS(5)) == pdTRUE) {
        snap = s_reading;
        xSemaphoreGive(s_mutex);
    }
    return snap;
}

static inline const char* obstacleLocation_toString(ObstacleLocation loc) {
    switch (loc) {
        case OBS_NONE:       return "Clear";
        case OBS_LEFT:       return "Left";
        case OBS_MIDDLE:     return "Middle";
        case OBS_RIGHT:      return "Right";
        case OBS_LEFT_MID:   return "Left+Middle";
        case OBS_RIGHT_MID:  return "Middle+Right";
        case OBS_LEFT_RIGHT: return "Left+Right (gap)";
        case OBS_WALL:       return "WALL (all)";
        default:             return "Unknown";
    }
}

static inline void obstacleDetection_update() {
    static uint32_t lastSent = 0;
    uint32_t now = millis();

    if (now - lastSent < OBS_BLE_INTERVAL_MS) return;
    lastSent = now;

    SensorReading r = obstacleDetection_getReading();

    ble.send("M:"+String(r.distM));

    // "OBS|L:24.3|M:310.0|R:18.7|STOP:1"
    // char buf[48];
    // snprintf(buf, sizeof(buf),
    //     "OBS|L:%.1f|M:%.1f|R:%.1f|STOP:%d",
    //     r.distL,
    //     r.distM,
    //     r.distR,
    //     r.hardStop ? 1 : 0
    // );

    // ble.send(buf);
}
