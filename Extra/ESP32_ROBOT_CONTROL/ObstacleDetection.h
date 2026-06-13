#pragma once
#include <ble.h>

#define OBS_BLE_INTERVAL_MS  200   // send BLE update every 200 ms

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
#define DIST_STOP          15.0f
#define DIST_WARN          50.0f
#define DIST_MAX           150.0f
#define SONAR_TIMEOUT_US   8741UL

// ─── Filter Settings ─────────────────────────────────────────────────────────
// Must be ODD for a clean median (no averaging of two middle elements)
#define OBS_FILTER_SAMPLES     5      // number of past readings kept per sensor
#define OBS_CONFIRM_FRAMES     3      // consecutive filtered readings before state change

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

// ─── Internal state ────────────────────────────────────────────────────────────
static SemaphoreHandle_t  s_mutex          = nullptr;
static SensorReading      s_reading        = {};
static void              (*s_motorStop)()  = nullptr;
static void              (*s_motorResume)()= nullptr;
static bool                s_wasInStop     = false;

// ─── Filter ring buffers (one slot per sensor, shared index) ─────────────────
static float    s_bufL[OBS_FILTER_SAMPLES] = {};
static float    s_bufM[OBS_FILTER_SAMPLES] = {};
static float    s_bufR[OBS_FILTER_SAMPLES] = {};
static uint8_t  s_bufIdx          = 0;
static uint8_t  s_stopFrameCount  = 0;
static uint8_t  s_clearFrameCount = 0;

// ─── Median over a fixed-size buffer ─────────────────────────────────────────
// Copies into a scratch array and insertion-sorts (cheap for N=5).
static inline float medianOfN(const float* buf) {
    float tmp[OBS_FILTER_SAMPLES];
    memcpy(tmp, buf, sizeof(tmp));

    for (int i = 1; i < OBS_FILTER_SAMPLES; i++) {
        float key = tmp[i];
        int j = i - 1;
        while (j >= 0 && tmp[j] > key) {
            tmp[j + 1] = tmp[j];
            j--;
        }
        tmp[j + 1] = key;
    }
    return tmp[OBS_FILTER_SAMPLES / 2];
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
    if (fwdM < DIST_STOP)        bits |= OBS_MIDDLE;
    if (fwdR < DIST_STOP * 0.7f) bits |= OBS_RIGHT;

    return static_cast<ObstacleLocation>(bits);
}

// ─── FreeRTOS sensor task ─────────────────────────────────────────────────────
static void sensorTask(void* pvParams) {
    pinMode(SONAR_L_TRIG, OUTPUT); digitalWrite(SONAR_L_TRIG, LOW);
    pinMode(SONAR_M_TRIG, OUTPUT); digitalWrite(SONAR_M_TRIG, LOW);
    pinMode(SONAR_R_TRIG, OUTPUT); digitalWrite(SONAR_R_TRIG, LOW);

    pinMode(SONAR_L_ECHO, INPUT);
    pinMode(SONAR_M_ECHO, INPUT);
    pinMode(SONAR_R_ECHO, INPUT);

    // Pre-fill buffers with DIST_MAX so the robot starts in a "clear" state
    for (int i = 0; i < OBS_FILTER_SAMPLES; i++) {
        s_bufL[i] = DIST_MAX;
        s_bufM[i] = DIST_MAX;
        s_bufR[i] = DIST_MAX;
    }

    for (;;) {
        // ─── One read per sensor per iteration ────────────────────────────────
        float rawL = readSonar(SONAR_L_TRIG, SONAR_L_ECHO);
        vTaskDelay(pdMS_TO_TICKS(10));   // gap to avoid cross-talk
        float rawM = readSonar(SONAR_M_TRIG, SONAR_M_ECHO);
        vTaskDelay(pdMS_TO_TICKS(10));
        float rawR = readSonar(SONAR_R_TRIG, SONAR_R_ECHO);
        vTaskDelay(pdMS_TO_TICKS(10));

        // ─── Push into ring buffers ────────────────────────────────────────────
        s_bufL[s_bufIdx] = rawL;
        s_bufM[s_bufIdx] = rawM;
        s_bufR[s_bufIdx] = rawR;
        s_bufIdx = (s_bufIdx + 1) % OBS_FILTER_SAMPLES;

        // ─── Filter: median over the last OBS_FILTER_SAMPLES readings ─────────
        float dL = medianOfN(s_bufL);
        float dM = medianOfN(s_bufM);
        float dR = medianOfN(s_bufR);

        // ─── Confirmation frames (debounce state transitions) ─────────────────
        ObstacleLocation loc = classifyObstacle(dL, dM, dR);
        bool rawHardStop = (loc != OBS_NONE);

        bool hardStop;
        if (rawHardStop) {
            s_stopFrameCount  = min((int)s_stopFrameCount  + 1, (int)OBS_CONFIRM_FRAMES);
            s_clearFrameCount = 0;
            hardStop = (s_stopFrameCount >= OBS_CONFIRM_FRAMES);
        } else {
            s_clearFrameCount = min((int)s_clearFrameCount + 1, (int)OBS_CONFIRM_FRAMES);
            s_stopFrameCount  = 0;
            hardStop = !(s_clearFrameCount >= OBS_CONFIRM_FRAMES);
        }

        // ─── Warn zone (only meaningful when not in hard stop) ────────────────
        bool warn = false;
        if (!hardStop) {
            constexpr float COS30 = 0.866f;
            warn = (dL * COS30 < DIST_WARN) ||
                   (dM        < DIST_WARN) ||
                   (dR * COS30 < DIST_WARN);
        }

        // ─── Edge-triggered callbacks ───────────────────────────────────────────
        if (hardStop && !s_wasInStop) {
            if (s_motorStop != nullptr) s_motorStop();
        } else if (!hardStop && s_wasInStop) {
            if (s_motorResume != nullptr) s_motorResume();
        }
        s_wasInStop = hardStop;

        // ─── Update shared state ────────────────────────────────────────────────
        if (xSemaphoreTake(s_mutex, pdMS_TO_TICKS(5)) == pdTRUE) {
            s_reading.distL     = dL;
            s_reading.distM     = dM;
            s_reading.distR     = dR;
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

    // "OBS|L:24.3|M:310.0|R:18.7|STOP:1"
    char buf[48];
    snprintf(buf, sizeof(buf),
        "OBS|L:%.1f|M:%.1f|R:%.1f|STOP:%d",
        r.distL,
        r.distM,
        r.distR,
        r.hardStop ? 1 : 0
    );

    ble.send(buf);
}