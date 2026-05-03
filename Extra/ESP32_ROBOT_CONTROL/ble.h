#ifndef BLE_MODULE_H
#define BLE_MODULE_H

#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <BLE2902.h>
#include <Arduino.h>
#include "globals.h"


// ===========================
// BLE UUIDs (Nordic UART)
// ===========================
#define SERVICE_UUID           "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHARACTERISTIC_UUID_RX "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHARACTERISTIC_UUID_TX "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

// ===========================
// BLE Class
// ===========================
class BLEModule {
  public:
    BLEModule() : deviceConnected(false) {}


    void begin(const char* deviceName) {
        BLEDevice::init(deviceName);
        BLEDevice::setMTU(247);

        pServer = BLEDevice::createServer();
        pServer->setCallbacks(new MyServerCallbacks(this));

        BLEService *svc = pServer->createService(SERVICE_UUID);

        // TX characteristic (notify)
        pTxCharacteristic = svc->createCharacteristic(
            CHARACTERISTIC_UUID_TX,
            BLECharacteristic::PROPERTY_NOTIFY
        );
        pTxCharacteristic->addDescriptor(new BLE2902());

        // RX characteristic (write)
        BLECharacteristic *rxChar = svc->createCharacteristic(
            CHARACTERISTIC_UUID_RX,
            BLECharacteristic::PROPERTY_WRITE_NR
        );
        rxChar->setCallbacks(new MyCallbacks(this));

        svc->start();
        pServer->getAdvertising()->start();
        Serial.println("BLE UART ready");
    }

    void send(String str) {
        if (deviceConnected && pTxCharacteristic) {
            pTxCharacteristic->setValue(str.c_str());
            pTxCharacteristic->notify();
        }
    }

    void sendRaw(const uint8_t* data, size_t len) {
        if (!deviceConnected || !pTxCharacteristic) return;

        last_send = millis();

        pTxCharacteristic->setValue((uint8_t*)data, len);
        pTxCharacteristic->notify();
    }

    bool isConnected() { return deviceConnected; }

    // Function pointer to handle incoming BLE commands
    void (*onReceive)(String) = nullptr;

  private:
    BLEServer* pServer;
    BLECharacteristic* pTxCharacteristic;
    bool deviceConnected;
    unsigned long last_send = 0;

    // ===========================
    // Callbacks
    // ===========================
    class MyServerCallbacks : public BLEServerCallbacks {
      public:
        MyServerCallbacks(BLEModule* parent) : parent(parent) {}
        void onConnect(BLEServer* pServer) {
            parent->deviceConnected = true;
            Serial.println("Device Connected");
            
        }
        void onDisconnect(BLEServer* pServer) {
            parent->deviceConnected = false;
            Serial.println("Device disconnected");
            delay(1000);
            BLEDevice::startAdvertising();
        }
      private:
        BLEModule* parent;
    };

    class MyCallbacks : public BLECharacteristicCallbacks {
      public:
        MyCallbacks(BLEModule* parent) : parent(parent) {}
        void onWrite(BLECharacteristic *pChar) {
            String rx = pChar->getValue().c_str();
            if (rx.length() == 0) return;

            // Call the assigned handler in main code
            if (parent->onReceive) parent->onReceive(rx);

            // Optional ACK
            // if (parent->deviceConnected) {
            //     String ack = "ACK:" + rx;
            //     parent->pTxCharacteristic->setValue(ack.c_str());
            //     parent->pTxCharacteristic->notify();
            // }
        }
      private:
        BLEModule* parent;
    };
};

#endif
