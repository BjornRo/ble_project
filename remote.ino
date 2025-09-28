#include <Arduino.h>
#include <BLE2902.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <FS.h>
#include <SPIFFS.h>

#include <string>

#include "esp_timer.h"
#include "inttypes.h"

#define REMOTE_SERVICE_UUID "A9DCFE62-41AF-49E3-ADC0-000000000000"
#define REMOTE_PAIRING_CHAR_UUID "A9DCFE62-41AF-49E3-ADC0-000000000001"
#define REMOTE_NOTIFY_CHAR_UUID "A9DCFE62-41AF-49E3-ADC0-000000000002"

#define KEY_FILE "/key"

// Default pairing key -- includes manufacturer-data
// const uint8_t _DEFAULT_KEY[4] = {0xCA, 0xFE, 0x13, 0x37};
// std::string default_key((char*)_DEFAULT_KEY, sizeof(_DEFAULT_KEY));

std::string default_key("\xCA\xFE\x13\x37", 4);
std::string remote_key;

// BLE objects
BLEServer* pServer;
BLECharacteristic* pairingChar;
BLECharacteristic* notifyChar;
BLE2902* pBLE2902;
BLEAdvertising* pAdvertising;

#define INCREASE_PIN 12
#define DECREASE_PIN 22

bool connected = false;

volatile bool incr_pressed = false;
volatile bool decr_pressed = false;

// volatile uint32_t last_incr_time = 0;
// volatile uint32_t last_decr_time = 0;

void IRAM_ATTR handle_incr() {
    // uint32_t now = millis();
    // if (now - last_incr_time > 250) {
    incr_pressed = true;
    //     last_incr_time = now;
    // }
}

void IRAM_ATTR handle_decr() {
    // uint32_t now = millis();
    // if (now - last_decr_time > 250) {
    decr_pressed = true;
    //     last_decr_time = now;
    // }
    // ble_handler();
    // while (true) {
    //     if (connected) {
    //         notifyChar->setValue("\x00");
    //         notifyChar->notify();
    //     }
    // }
}

class MyServerCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
        connected = true;
    };

    void onDisconnect(BLEServer* pServer) {
        connected = false;
    }
};
class PairingCallback : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* pChar) {
        remote_key = pChar->getValue();
        File f = SPIFFS.open(KEY_FILE, "w");
        if (!f) abort();
        f.write(remote_key.data(), remote_key.size());
        f.close();
    }
};

class NotifyCallback : public BLEDescriptorCallbacks {
    void onNotify(BLECharacteristic* pChar) {
    }
};

void setup() {
    pinMode(RGB_BUILTIN, OUTPUT);
    digitalWrite(RGB_BUILTIN, HIGH);
    pinMode(INCREASE_PIN, INPUT_PULLUP);
    pinMode(DECREASE_PIN, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(INCREASE_PIN), handle_incr, FALLING);
    attachInterrupt(digitalPinToInterrupt(DECREASE_PIN), handle_decr, FALLING);

    Serial.begin(115200);
    delay(200);
    if (!SPIFFS.begin(true)) {
        Serial.println("Failed to mount SPIFFS");
        abort();
    }
    digitalWrite(RGB_BUILTIN, LOW);
}

void ble_handler() {
    BLEDevice::init("MyRemote");

    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new MyServerCallbacks());
    BLEService* pService = pServer->createService(REMOTE_SERVICE_UUID);

    pairingChar = pService->createCharacteristic(
        REMOTE_PAIRING_CHAR_UUID,
        BLECharacteristic::PROPERTY_WRITE);
    // pairingChar->setCallbacks(new PairingCallback());

    notifyChar = pService->createCharacteristic(
        REMOTE_NOTIFY_CHAR_UUID,
        BLECharacteristic::PROPERTY_NOTIFY);

    pBLE2902->setNotifications(true);
    notifyChar->addDescriptor(pBLE2902);

    pService->start();

    BLEAdvertising* pAdvertising = BLEDevice::getAdvertising();

    pAdvertising->setManufacturerData(genManufacturerData());

    pAdvertising->addServiceUUID(REMOTE_SERVICE_UUID);
    pAdvertising->setMinPreferred(0x06);
    pAdvertising->setMaxPreferred(0x12);
    pAdvertising->start();
}

void loop() {
    if (incr_pressed || decr_pressed) {
        ble_handler();
        Serial.println("Button pressed, waiting for BLE connection...");
        while (!connected) delay(5);

        if (incr_pressed) {
            notifyChar->setValue("\x01");
        } else {
            notifyChar->setValue("\x00");
        }
        notifyChar->notify();
        Serial.println("BLE notification sent, going to deep sleep...");

        delay(100);
    }
    esp_sleep_enable_ext1_wakeup(
        (1ULL << INCREASE_PIN) | (1ULL << DECREASE_PIN),
        ESP_EXT1_WAKEUP_ANY_HIGH);
    // esp_sleep_enable_ext0_wakeup(INCREASE_PIN, 0);
    // esp_sleep_enable_ext0_wakeup(DECREASE_PIN, 0);
    esp_deep_sleep_start();
}

//    if (esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_EXT1) {
//         uint64_t wakePinMask = esp_sleep_get_ext1_wakeup_status();

//         ble_handler(); // start BLE server
//         while (!connected) delay(5);

//         // Decide which button triggered the wakeup
//         if (wakePinMask & (1ULL << INCREASE_PIN)) {
//             notifyChar->setValue("\x01");
//         }
//         else if (wakePinMask & (1ULL << DECREASE_PIN)) {
//             notifyChar->setValue("\x00");
//         }

//         notifyChar->notify();
//         Serial.println("BLE notification sent, going back to deep sleep...");
//         delay(100); // allow BLE notification to be sent
//     }

std::string genManufacturerData() {
    if (!remote_key.empty()) return remote_key;

    File f = SPIFFS.open(KEY_FILE, "r");
    if (!f) return default_key;

    size_t len = f.size();
    remote_key.resize(len);
    f.readBytes(remote_key.data(), len);
    f.close();
    return remote_key;
}

// void send_BLE_message(bool increasing) {
//     std::string message = {0xCA, 0xFE, unique_id[0], unique_id[1], (uint8_t)increasing + 1, '\0'};

//     BLEAdvertisementData advData;
//     advData.setManufacturerData(message.data());
//     pAdvertising->setAdvertisementData(advData);

//     pAdvertising->start();
//     delay(200);
//     pAdvertising->stop();
// }