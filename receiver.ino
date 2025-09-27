#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>

const char* TARGET_MAC = "74:4d:bd:60:36:31";

BLEScan* pScan;

class MyAdvertisedDeviceCallbacks : public BLEAdvertisedDeviceCallbacks {
    void onResult(BLEAdvertisedDevice dev) override {
        BLEAddress addr = dev.getAddress();

        // // filter by target MAC
        // if (addr.toString() != TARGET_MAC) return;

        String data = dev.getManufacturerData();
        if (data.length() < 2) return;

        if ((uint8_t)data[0] == 0xCA && (uint8_t)data[1] == 0xFE) {
            Serial.print("Received from target MAC: ");
            Serial.println(addr.toString().c_str());

            Serial.print("Payload: ");
            for (size_t i = 0; i < data.length(); i++) {
                Serial.print("0x");
                if ((uint8_t)data[i] < 0x10) Serial.print("0");
                Serial.print((uint8_t)data[i], HEX);
                Serial.print(" ");
            }
            Serial.println();
        }
    }
};

void setup() {
    Serial.begin(115200);
    BLEDevice::init("");

    pScan = BLEDevice::getScan();
    pScan->setAdvertisedDeviceCallbacks(new MyAdvertisedDeviceCallbacks());
    pScan->setActiveScan(false);   // request more data
    pScan->start(0, nullptr, false); // 0 = continuous scanning, non-blocking
}

void loop() {
    // nothing needed here, callback handles everything
    // delay(1000); // optional, or leave empty
    // pScan->start(1, false); // 0 = continuous scanning, non-blocking
    // pScan->clearResults();   // free memory
}
