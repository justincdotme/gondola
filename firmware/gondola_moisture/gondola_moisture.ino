// Gondola Moisture: Capacitive soil moisture sensor to BLE manufacturer data
// Reads raw ADC, broadcasts via BLE, enters deep sleep for configurable duration
//
// Required Libraries:
//   ESP32 BLE Arduino (included with ESP32 board package)
//
// Arduino IDE Board Settings:
//   Board: ESP32C3 Dev Module
//   USB CDC On Boot: Enabled (for serial debug output)
//   CPU Frequency: 80MHz
//   Flash Size: 4MB
//
// Wiring:
//   ESP32-C3 GPIO0  -->  Moisture sensor AOUT
//   ESP32-C3 GPIO3  -->  Moisture sensor VCC
//   ESP32-C3 GND    -->  Moisture sensor GND
//
// BLE Manufacturer Data (Company ID 0x02E5, Espressif):
//   Byte 0:     Version (0x01)
//   Bytes 1-2:  Moisture raw ADC (uint16_t big-endian, 0-4095)
//   Bytes 3-4:  Battery millivolts (uint16_t big-endian, 0xFFFF = unavailable)
//
// Configuration:
//   SLEEP_MINUTES: Deep sleep duration in minutes (default 60)
//   DEBUG: Uncomment the #define to enable serial logging

#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEAdvertising.h>
#include <esp_sleep.h>

#define DEVICE_NAME "Gondola-Moisture-01"
#define SENSOR_ADC_PIN 0
#define SENSOR_POWER_PIN 3
#define SLEEP_MINUTES 60
#define STABILIZATION_MS 200
#define ADVERTISE_SECONDS 5
#define ESPRESSIF_COMPANY_ID 0x02E5

// #define DEBUG

#ifdef DEBUG
  #define DBG_BEGIN(baud) Serial.begin(baud)
  #define DBG_PRINT(...) Serial.printf(__VA_ARGS__)
  #define DBG_PRINTLN(msg) Serial.println(msg)
  #define DBG_DELAY(ms) delay(ms)
#else
  #define DBG_BEGIN(baud)
  #define DBG_PRINT(...)
  #define DBG_PRINTLN(msg)
  #define DBG_DELAY(ms)
#endif

void setup() {
  DBG_BEGIN(115200);
  DBG_DELAY(100);
  DBG_PRINTLN("Gondola Moisture: waking up");

  pinMode(SENSOR_POWER_PIN, OUTPUT);
  digitalWrite(SENSOR_POWER_PIN, HIGH);
  delay(STABILIZATION_MS);

  int moisture = analogRead(SENSOR_ADC_PIN);

  digitalWrite(SENSOR_POWER_PIN, LOW);
  DBG_PRINT("Moisture ADC: %d\n", moisture);

  uint8_t payload[5];
  payload[0] = 0x01;
  payload[1] = (moisture >> 8) & 0xFF;
  payload[2] = moisture & 0xFF;
  payload[3] = 0xFF;
  payload[4] = 0xFF;

  BLEDevice::init(DEVICE_NAME);
  BLEAdvertising* advertising = BLEDevice::getAdvertising();

  uint8_t mfgRaw[7];
  mfgRaw[0] = ESPRESSIF_COMPANY_ID & 0xFF;
  mfgRaw[1] = (ESPRESSIF_COMPANY_ID >> 8) & 0xFF;
  memcpy(&mfgRaw[2], payload, 5);

  String mfgData;
  mfgData.concat((char*)mfgRaw, 7);

  BLEAdvertisementData advData;
  advData.setManufacturerData(mfgData);

  BLEAdvertisementData scanResp;
  scanResp.setName(DEVICE_NAME);

  advertising->setAdvertisementData(advData);
  advertising->setScanResponseData(scanResp);
  advertising->start();

  DBG_PRINT("Advertising for %d seconds\n", ADVERTISE_SECONDS);
  delay(ADVERTISE_SECONDS * 1000);

  advertising->stop();
  BLEDevice::deinit(true);
  DBG_PRINTLN("Entering deep sleep");

  esp_sleep_enable_timer_wakeup((uint64_t)SLEEP_MINUTES * 60ULL * 1000000ULL);
  esp_deep_sleep_start();
}

void loop() {
  esp_deep_sleep_start();
}
