#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>

#include "esp_timer.h"
#include "inttypes.h"

BLEAdvertising* pAdvertising;

#define INCREASE_PIN 12
#define DECREASE_PIN 22

volatile bool incr_pressed = false;
volatile bool decr_pressed = false;

uint8_t unique_id[2] = {0x12, 0x34};

volatile uint32_t last_incr_time = 0;
volatile uint32_t last_decr_time = 0;

void handle_incr() {
    uint32_t now = millis();
    if (now - last_incr_time > 250) {
        incr_pressed = true;
        last_incr_time = now;
    }
}

void handle_decr() {
    uint32_t now = millis();
    if (now - last_decr_time > 250) {
        decr_pressed = true;
        last_decr_time = now;
    }
}

void generate_unique_id() {
    uint16_t now_us = esp_timer_get_time() % 0x10000;
    unique_id[0] = (now_us >> 8) & 0xFF;
    unique_id[1] = now_us & 0xFF;
}

void send_BLE_message(bool increasing) {
    std::string message = {0xCA, 0xFE, unique_id[0], unique_id[1], (uint8_t)increasing + 1, '\0'};

    BLEAdvertisementData advData;
    advData.setManufacturerData(message.data());
    pAdvertising->setAdvertisementData(advData);

    pAdvertising->start();
    delay(200);
    pAdvertising->stop();
}

void setup() {
    pinMode(RGB_BUILTIN, OUTPUT);
    digitalWrite(RGB_BUILTIN, HIGH);
    pinMode(INCREASE_PIN, INPUT_PULLUP);
    pinMode(DECREASE_PIN, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(INCREASE_PIN), handle_incr, FALLING);
    attachInterrupt(digitalPinToInterrupt(DECREASE_PIN), handle_decr, FALLING);

    BLEDevice::init("ESP32-Broadcast");
    pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->setScanResponse(false);
    pAdvertising->setMinPreferred(0x06);  // for faster advertising
    pAdvertising->setMaxPreferred(0x12);

    BLEAdvertisementData advData;
    advData.setManufacturerData("__TESTING__");
    pAdvertising->setAdvertisementData(advData);
    BLEDevice::startAdvertising();
    delay(500);
    digitalWrite(RGB_BUILTIN, LOW);
}

void loop() {
    if (incr_pressed) {
        digitalWrite(RGB_BUILTIN, HIGH);
        incr_pressed = false;
        send_BLE_message(true);
    }

    if (decr_pressed) {
        digitalWrite(RGB_BUILTIN, LOW);
        decr_pressed = false;
        send_BLE_message(false);
    }
}