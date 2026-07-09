// Gondola Lux: VEML7700 light sensor to BLE manufacturer data
// Reads ambient light and broadcasts via BLE every 2 minutes

#include <Wire.h>
#include <Adafruit_VEML7700.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEAdvertising.h>

#define DEVICE_NAME "Gondola-Lux-01"
#define SDA_PIN 8
#define SCL_PIN 9
#define BROADCAST_INTERVAL_MS 120000
#define ESPRESSIF_COMPANY_ID 0x02E5

Adafruit_VEML7700 veml7700;
BLEAdvertising* advertising = nullptr;

void setup() {
  Serial.begin(115200);
  delay(100);

  Wire.begin(SDA_PIN, SCL_PIN);
  delay(100);

  if (!veml7700.begin()) {
    Serial.println("VEML7700 sensor not found");
    while (1);
  }

  veml7700.setGain(VEML7700_GAIN_1);
  veml7700.setIntegrationTime(VEML7700_IT_100MS);
  Serial.println("VEML7700 initialized");

  BLEDevice::init(DEVICE_NAME);
  advertising = BLEDevice::getAdvertising();
  Serial.println("BLE initialized");
}

void loop() {
  float lux = veml7700.readLux();
  uint16_t white = veml7700.readWhite();
  uint16_t als = veml7700.readALS();
  uint32_t centilux = (uint32_t)(lux * 100.0f);

  // Payload: version(1) | centilux(4 BE) | white(2 BE) | als(2 BE) | battery(1)
  uint8_t payload[10];
  payload[0] = 0x01;
  payload[1] = (centilux >> 24) & 0xFF;
  payload[2] = (centilux >> 16) & 0xFF;
  payload[3] = (centilux >> 8) & 0xFF;
  payload[4] = centilux & 0xFF;
  payload[5] = (white >> 8) & 0xFF;
  payload[6] = white & 0xFF;
  payload[7] = (als >> 8) & 0xFF;
  payload[8] = als & 0xFF;
  payload[9] = 0xFF;

  // Company ID is little-endian per BLE spec, payload is big-endian per our protocol
  uint8_t mfgRaw[12];
  mfgRaw[0] = ESPRESSIF_COMPANY_ID & 0xFF;
  mfgRaw[1] = (ESPRESSIF_COMPANY_ID >> 8) & 0xFF;
  memcpy(&mfgRaw[2], payload, 10);

  String mfgData;
  mfgData.concat((char*)mfgRaw, 12);

  BLEAdvertisementData advData;
  advData.setManufacturerData(mfgData);

  // Name goes in scan response; it won't fit in the advertisement alongside manufacturer data
  BLEAdvertisementData scanResp;
  scanResp.setName(DEVICE_NAME);

  advertising->setAdvertisementData(advData);
  advertising->setScanResponseData(scanResp);
  advertising->start();

  Serial.printf("Lux: %.2f  White: %u  ALS: %u\n", lux, white, als);

  delay(BROADCAST_INTERVAL_MS);
  advertising->stop();
}
