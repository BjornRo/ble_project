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
String default_key = "rl-default";
String remote_key = "";

// BLE objects
BLEServer* pServer;
BLECharacteristic* pairingChar;
BLECharacteristic* notifyChar;
BLEAdvertising* pAdvertising;

#define INCREASE_PIN 12
#define DECREASE_PIN 14

bool connected = false;
bool received = false;

volatile bool incr_pressed = false;
volatile bool decr_pressed = false;

class MyServerCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
        Serial.println("Connected");
        connected = true;
    };

    void onDisconnect(BLEServer* pServer) {
        connected = false;
    }
};
class PairingCallback : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* pChar) {
        String value = pChar->getValue();
        Serial.println();
        Serial.println(value);
        Serial.println();
        File f = SPIFFS.open(KEY_FILE, "w");
        if (!f) abort();
        f.write((const uint8_t*)value.c_str(), value.length());
        f.close();
        remote_key = value;
    }
};

class NotifyCallback : public BLEDescriptorCallbacks {
    void onNotify(BLECharacteristic* pChar) {
    }
};

void setup() {
    // pinMode(RGB_BUILTIN, OUTPUT);
    // digitalWrite(RGB_BUILTIN, HIGH);
    pinMode(INCREASE_PIN, INPUT_PULLUP);
    pinMode(DECREASE_PIN, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(INCREASE_PIN), NULL, FALLING);
    attachInterrupt(digitalPinToInterrupt(DECREASE_PIN), NULL, FALLING);

    Serial.begin(115200);
    delay(100);
    if (!SPIFFS.begin(true)) {
        Serial.println("Failed to mount SPIFFS");
        abort();
    }
    // digitalWrite(RGB_BUILTIN, LOW);
}

void ble_handler() {
    Serial.println(getDeviceName());
    BLEDevice::init(getDeviceName());

    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new MyServerCallbacks());
    BLEService* pService = pServer->createService(REMOTE_SERVICE_UUID);

    pairingChar = pService->createCharacteristic(
        REMOTE_PAIRING_CHAR_UUID,
        BLECharacteristic::PROPERTY_WRITE);
    pairingChar->setCallbacks(new PairingCallback());

    notifyChar = pService->createCharacteristic(
        REMOTE_NOTIFY_CHAR_UUID,
        BLECharacteristic::PROPERTY_NOTIFY | BLECharacteristic::PROPERTY_READ);
    notifyChar->addDescriptor(new BLE2902());

    pService->start();

    BLEAdvertising* pAdvertising = BLEDevice::getAdvertising();

    pAdvertising->addServiceUUID(REMOTE_SERVICE_UUID);
    pAdvertising->setMinPreferred(0x06);
    pAdvertising->setMaxPreferred(0x12);
    pAdvertising->start();
}

void loop() {
    if (esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_EXT1) {
        uint64_t wakePinMask = esp_sleep_get_ext1_wakeup_status();

        ble_handler();
        Serial.println("Button pressed, waiting for BLE connection...");
        while (!connected) delay(5);

        bool increase = (wakePinMask & (1ULL << INCREASE_PIN));
        String c = (increase) ? "1" : "0";
        delay(500);
        notifyChar->setValue(c);
        notifyChar->notify();
        delay(1500);
        delay(500);
        notifyChar->setValue(c);
        notifyChar->notify();
        delay(1500);
        Serial.println("BLE notification sent, going to deep sleep...");
    }
    esp_sleep_enable_ext1_wakeup(
        (1ULL << INCREASE_PIN) | (1ULL << DECREASE_PIN),
        ESP_EXT1_WAKEUP_ANY_LOW);
    esp_deep_sleep_start();
}

//    if (esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_EXT1) {
//         ;

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

String getDeviceName() {
    if (remote_key.length()) return remote_key;

    File f = SPIFFS.open(KEY_FILE, "r");
    if (!f || !f.available()) return default_key;

    size_t len = f.size();
    char buf[len + 1];
    f.readBytes(buf, len);
    buf[len] = '\0';
    f.close();

    remote_key = String(buf);
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