/**
 * @file slave_node.ino
 * @author Andrés Navarro
 * @brief Slave Node Firmware - SPEC-P6 System
 * @details Firmware for the ESP32-C6 slave node. Responsible for sampling 
 *          retroauricular photoplethysmography (MAX30102) and inertial 
 *          data (MPU6050) under movement dynamics, utilizing FreeRTOS 
 *          tasks and ESP-NOW communication.
 * @institution Universidad de Guadalajara (UdeG) - CUCEI
 * @date 2026
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include "esp_bt.h" 
#include "common_definitions.h" 
#include <Wire.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

#define MAX30102_ADDRESS        0x57
#define MAX_REG_MODE_CONFIG     0x09
#define MAX_REG_SPO2_CONFIG     0x0A
#define MAX_REG_FIFO_CONFIG     0x08
#define MAX_REG_PART_ID         0xFF
#define MAX_REG_FIFO_WR_PTR     0x04
#define MAX_REG_FIFO_RD_PTR     0x06
#define MAX_REG_FIFO_DATA       0x07
#define MAX_REG_LED1_PA         0x0C 
#define MAX_REG_LED2_PA         0x0D 

#define MPU6050_ADDRESS         0x68
#define MPU_REG_SMPLRT_DIV      0x19
#define MPU_REG_CONFIG          0x1A 
#define MPU_REG_GYRO_CONFIG     0x1B
#define MPU_REG_ACCEL_CONFIG    0x1C
#define MPU_REG_ACCEL_XOUT_H    0x3B
#define MPU_REG_PWR_MGMT_1      0x6B
#define MPU_REG_WHO_AM_I        0x75

#ifndef LED_BUILTIN
#define LED_BUILTIN 21
#endif

struct PpgData { int64_t timestamp; long red; long ir; };
struct MpuData { int16_t ax; int16_t ay; int16_t az; int16_t gx; int16_t gy; int16_t gz; };

MpuData mpuDataGlobal;

QueueHandle_t ppgQueue;
TaskHandle_t ppgTaskHandle;
TaskHandle_t mpuTaskHandle;
TaskHandle_t batteryTaskHandle;
SemaphoreHandle_t serialMutex;
SemaphoreHandle_t i2cMutex;
SemaphoreHandle_t mpuMutex;

volatile bool systemRunning = false;
volatile bool sensorsActive = false;
volatile int64_t timeOffset_us = 0;
volatile uint16_t batteryVoltage_mv = 0;

volatile uint8_t ledBrightness = 0x24; 
const long FINGER_DETECT_THRESH         = 20000;
const long BRIGHTNESS_ADJUST_LOW_THRESH  = 60000;
const long BRIGHTNESS_ADJUST_HIGH_THRESH = 150000;

struct_data_packet dataBatch; 
int64_t lastSampleTime = 0;
unsigned long ledTimer = 0; 
bool ledState = false;

bool writeRegister8(uint8_t address, uint8_t reg, uint8_t val) {
  Wire.beginTransmission(address); Wire.write(reg); Wire.write(val);
  return (Wire.endTransmission() == 0);
}

uint8_t readRegister8(uint8_t address, uint8_t reg, bool* success) {
  Wire.beginTransmission(address); Wire.write(reg);
  if (Wire.endTransmission(false) != 0) { *success = false; return 0; }
  if (Wire.requestFrom(address, (uint8_t)1) != 1) { *success = false; return 0; }
  *success = true; return Wire.read();
}

bool readBurst(uint8_t address, uint8_t reg, uint8_t* buffer, uint8_t count) {
  Wire.beginTransmission(address); Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(address, count) != count) return false;
  for (int i = 0; i < count; i++) buffer[i] = Wire.read();
  return true;
}

void errorBlink() {
  pinMode(LED_BUILTIN, OUTPUT);
  while (1) {
    for (int i = 0; i < 3; i++) { digitalWrite(LED_BUILTIN, HIGH); delay(100); digitalWrite(LED_BUILTIN, LOW); delay(100); }
    delay(700);
  }
}

void mpuTask(void * pv) {
  uint8_t buf[14];
  for(;;) {
    if (sensorsActive) {
      if (xSemaphoreTake(i2cMutex, pdMS_TO_TICKS(50))) {
        if (readBurst(MPU6050_ADDRESS, MPU_REG_ACCEL_XOUT_H, buf, 14)) {
          xSemaphoreGive(i2cMutex);
          MpuData tmp;
          tmp.ax = (int16_t)(buf[0]  << 8 | buf[1]);
          tmp.ay = (int16_t)(buf[2]  << 8 | buf[3]);
          tmp.az = (int16_t)(buf[4]  << 8 | buf[5]);
          tmp.gx = (int16_t)(buf[8]  << 8 | buf[9]);
          tmp.gy = (int16_t)(buf[10] << 8 | buf[11]);
          tmp.gz = (int16_t)(buf[12] << 8 | buf[13]);
          xSemaphoreTake(mpuMutex, portMAX_DELAY);
          mpuDataGlobal = tmp;
          xSemaphoreGive(mpuMutex);
        } else {
          xSemaphoreGive(i2cMutex);
        }
      }
    }
    vTaskDelay(pdMS_TO_TICKS(20));
  }
}

void ppgTask(void * pv) {
  int64_t lastFifoReadTime = 0;
  bool haveReference = false;

  for (;;) {
    if (sensorsActive) {
      bool ok;
      if (xSemaphoreTake(i2cMutex, pdMS_TO_TICKS(5))) {
        uint8_t wr = readRegister8(MAX30102_ADDRESS, MAX_REG_FIFO_WR_PTR, &ok);
        uint8_t rd = readRegister8(MAX30102_ADDRESS, MAX_REG_FIFO_RD_PTR, &ok);
        int num = (int)wr - (int)rd; if (num < 0) num += 32;

        if (num > 0) {
          uint8_t b[6 * 32];
          if (readBurst(MAX30102_ADDRESS, MAX_REG_FIFO_DATA, b, num * 6)) {
            int64_t now = esp_timer_get_time() - timeOffset_us;
            int64_t spacing = haveReference ? (now - lastFifoReadTime) / num : 0;

            for (int i = 0; i < num; i++) {
              PpgData d;
              d.timestamp = haveReference ? (lastFifoReadTime + spacing * (i + 1)) : now;
              d.red = ((long)b[i*6+0] << 16 | (long)b[i*6+1] << 8 | (long)b[i*6+2]) & 0x03FFFF;
              d.ir  = ((long)b[i*6+3] << 16 | (long)b[i*6+4] << 8 | (long)b[i*6+5]) & 0x03FFFF;
              xQueueSend(ppgQueue, &d, 0);
            }
            lastFifoReadTime = now;
            haveReference = true;
          }
        }
        xSemaphoreGive(i2cMutex);
      }
    } else {
      haveReference = false;
    }
    vTaskDelay(pdMS_TO_TICKS(PPG_POLL_INTERVAL_MS));
  }
}

void batteryTask(void * pv) {
  pinMode(BATTERY_ADC_PIN, INPUT);
  for (;;) {
    uint32_t acc = 0;
    const int N = 16;
    for (int i = 0; i < N; i++) {
      acc += analogReadMilliVolts(BATTERY_ADC_PIN);
      delayMicroseconds(200);
    }
    uint16_t mv = (uint16_t)((acc / N) * BATTERY_DIVIDER_RATIO);
    batteryVoltage_mv = mv;
    vTaskDelay(pdMS_TO_TICKS(BATTERY_UPDATE_INTERVAL_MS));
  }
}

void runCalibration() {
  if (!xSemaphoreTake(serialMutex, portMAX_DELAY)) return;
  if (!xSemaphoreTake(i2cMutex, portMAX_DELAY)) { xSemaphoreGive(serialMutex); return; }

  writeRegister8(MAX30102_ADDRESS, MAX_REG_MODE_CONFIG, 0x03); 
  writeRegister8(MAX30102_ADDRESS, MAX_REG_LED1_PA, ledBrightness);
  writeRegister8(MAX30102_ADDRESS, MAX_REG_LED2_PA, ledBrightness);
  writeRegister8(MAX30102_ADDRESS, MAX_REG_FIFO_WR_PTR, 0x00);
  writeRegister8(MAX30102_ADDRESS, MAX_REG_FIFO_RD_PTR, 0x00);

  long irValue = 0;
  bool success;
  unsigned long startTime = millis();
  while (irValue < FINGER_DETECT_THRESH) {
    if (millis() - startTime > 10000) break; 
    uint8_t wr = readRegister8(MAX30102_ADDRESS, MAX_REG_FIFO_WR_PTR, &success);
    uint8_t rd = readRegister8(MAX30102_ADDRESS, MAX_REG_FIFO_RD_PTR, &success);
    int num = (int)wr - (int)rd; if (num < 0) num += 32;
    if (num > 0) {
      uint8_t buffer[6];
      readBurst(MAX30102_ADDRESS, MAX_REG_FIFO_DATA, buffer, 6);
      irValue = (long)buffer[3] << 16 | (long)buffer[4] << 8 | (long)buffer[5];
      irValue &= 0x03FFFF;
    }
    delay(100);
  }

  if (irValue >= FINGER_DETECT_THRESH) {
    bool brightnessOK = false;
    uint8_t currentBrightness = ledBrightness;
    if (currentBrightness < 0x10) currentBrightness = 0x10;
    for (int i = 0; i < 20 && !brightnessOK; i++) {
      writeRegister8(MAX30102_ADDRESS, MAX_REG_LED1_PA, currentBrightness);
      writeRegister8(MAX30102_ADDRESS, MAX_REG_LED2_PA, currentBrightness);
      writeRegister8(MAX30102_ADDRESS, MAX_REG_FIFO_WR_PTR, 0x00);
      writeRegister8(MAX30102_ADDRESS, MAX_REG_FIFO_RD_PTR, 0x00);
      delay(200);

      long totalIR = 0; int samplesRead = 0;
      startTime = millis();
      while(samplesRead < 5 && (millis() - startTime < 500)) {
        uint8_t wr = readRegister8(MAX30102_ADDRESS, MAX_REG_FIFO_WR_PTR, &success);
        uint8_t rd = readRegister8(MAX30102_ADDRESS, MAX_REG_FIFO_RD_PTR, &success);
        int num = (int)wr - (int)rd; if (num < 0) num += 32;
        if (num > 0) {
          uint8_t buffer[6];
          readBurst(MAX30102_ADDRESS, MAX_REG_FIFO_DATA, buffer, 6);
          long irVal = (long)buffer[3] << 16 | (long)buffer[4] << 8 | (long)buffer[5];
          totalIR += (irVal & 0x03FFFF);
          samplesRead++;
        }
      }

      if (samplesRead > 0) {
        irValue = totalIR / samplesRead;
        if (irValue < BRIGHTNESS_ADJUST_LOW_THRESH && currentBrightness <= (0xFF - 5)) {
          currentBrightness += 5;
        } else if (irValue > BRIGHTNESS_ADJUST_HIGH_THRESH && currentBrightness >= (0x00 + 5)) {
          currentBrightness -= 5;
        } else {
          brightnessOK = true;
        }
      } else {
        currentBrightness += 5;
      }
    }
    ledBrightness = currentBrightness;
    
    struct_status_packet statusPkt;
    strcpy(statusPkt.message, "CAL_OK");
    esp_now_send(masterAddress, (uint8_t*)&statusPkt, sizeof(struct_status_packet));
  }

  writeRegister8(MAX30102_ADDRESS, MAX_REG_MODE_CONFIG, 0x80); 
  xSemaphoreGive(i2cMutex);
  xSemaphoreGive(serialMutex);
}

void setSensorState(bool state) {
  if (state == sensorsActive) return;
  if (state) {
    if (xSemaphoreTake(i2cMutex, portMAX_DELAY)) {
      writeRegister8(MPU6050_ADDRESS, MPU_REG_PWR_MGMT_1, 0x00);
      delay(5);
      writeRegister8(MAX30102_ADDRESS, MAX_REG_MODE_CONFIG, 0x03);
      writeRegister8(MAX30102_ADDRESS, MAX_REG_LED1_PA, ledBrightness);
      writeRegister8(MAX30102_ADDRESS, MAX_REG_LED2_PA, ledBrightness);
      writeRegister8(MAX30102_ADDRESS, MAX_REG_FIFO_WR_PTR, 0x00);
      writeRegister8(MAX30102_ADDRESS, MAX_REG_FIFO_RD_PTR, 0x00);
      xSemaphoreGive(i2cMutex);
    }
    xQueueReset(ppgQueue);
    timeOffset_us = esp_timer_get_time();
    lastSampleTime = 0;
    dataBatch.sample_count = 0; 
    sensorsActive = true;

  } else {
    sensorsActive = false;
    if (dataBatch.sample_count > 0) {
        dataBatch.battery_mv = batteryVoltage_mv;
        esp_now_send(masterAddress, (uint8_t*)&dataBatch, sizeof(dataBatch));
        dataBatch.sample_count = 0;
    }
    if (xSemaphoreTake(i2cMutex, portMAX_DELAY)) {
      writeRegister8(MPU6050_ADDRESS, MPU_REG_PWR_MGMT_1, 0x40);
      writeRegister8(MAX30102_ADDRESS, MAX_REG_MODE_CONFIG, 0x80);
      xSemaphoreGive(i2cMutex);
    }
  }
}

void OnDataRecv(const esp_now_recv_info_t * info, const uint8_t *incomingData, int len) {
  if (memcmp(info->src_addr, masterAddress, 6) != 0) return;
  if (len == sizeof(struct_cmd_packet)) {
    struct_cmd_packet cmd;
    memcpy(&cmd, incomingData, sizeof(cmd));

    if (cmd.command == '1') { setSensorState(true); lastSampleTime = 0; }
    else if (cmd.command == '0') { setSensorState(false); }
    else if (cmd.command == '3') { 
      setSensorState(false);
      runCalibration();
    }
  }
}

void OnDataSent(const wifi_tx_info_t* tx_info, esp_now_send_status_t status) {}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  Serial.begin(921600);
  
  setCpuFrequencyMhz(80); 
  btStop();                

  serialMutex = xSemaphoreCreateMutex();
  i2cMutex    = xSemaphoreCreateMutex();
  mpuMutex    = xSemaphoreCreateMutex();
  ppgQueue    = xQueueCreate(32, sizeof(PpgData));

  Wire.begin();
  Wire.setClock(400000);

  if (xSemaphoreTake(i2cMutex, portMAX_DELAY)) {
    digitalWrite(LED_BUILTIN, LOW); delay(250); digitalWrite(LED_BUILTIN, HIGH); delay(250);
    writeRegister8(MAX30102_ADDRESS, MAX_REG_MODE_CONFIG, 0x40);
    delay(100);
    writeRegister8(MAX30102_ADDRESS, MAX_REG_FIFO_WR_PTR, 0x00);
    writeRegister8(MAX30102_ADDRESS, MAX_REG_FIFO_RD_PTR, 0x00);
    
    writeRegister8(MAX30102_ADDRESS, MAX_REG_SPO2_CONFIG, 0x27);
    writeRegister8(MAX30102_ADDRESS, MAX_REG_FIFO_CONFIG, 0x3F);
    writeRegister8(MAX30102_ADDRESS, MAX_REG_LED1_PA, ledBrightness);
    writeRegister8(MAX30102_ADDRESS, MAX_REG_LED2_PA, ledBrightness);
    writeRegister8(MAX30102_ADDRESS, MAX_REG_MODE_CONFIG, 0x03);
    xSemaphoreGive(i2cMutex);
  }

  if (xSemaphoreTake(i2cMutex, portMAX_DELAY)) {
    digitalWrite(LED_BUILTIN, LOW); delay(250); digitalWrite(LED_BUILTIN, HIGH); delay(250);
    writeRegister8(MPU6050_ADDRESS, MPU_REG_PWR_MGMT_1, 0x00); delay(100);
    writeRegister8(MPU6050_ADDRESS, MPU_REG_CONFIG, 0x03);
    writeRegister8(MPU6050_ADDRESS, MPU_REG_SMPLRT_DIV, 0x13);
    writeRegister8(MPU6050_ADDRESS, MPU_REG_GYRO_CONFIG, 0x00);
    writeRegister8(MPU6050_ADDRESS, MPU_REG_ACCEL_CONFIG, 0x00);
    xSemaphoreGive(i2cMutex);
  }

  if (xSemaphoreTake(i2cMutex, portMAX_DELAY)) {
    writeRegister8(MPU6050_ADDRESS, MPU_REG_PWR_MGMT_1, 0x40);
    writeRegister8(MAX30102_ADDRESS, MAX_REG_MODE_CONFIG, 0x80);
    xSemaphoreGive(i2cMutex);
  }

  WiFi.mode(WIFI_STA);
  esp_wifi_set_channel(ESPNOW_CHANNEL, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_max_tx_power(ESPNOW_TX_POWER);
  esp_wifi_set_ps(WIFI_PS_NONE); 

  if (esp_now_init() != ESP_OK) { errorBlink(); }
  esp_now_register_send_cb(OnDataSent);
  esp_now_register_recv_cb(OnDataRecv);

  esp_now_peer_info_t peer{};
  memcpy(peer.peer_addr, masterAddress, 6);
  peer.channel = ESPNOW_CHANNEL;
  peer.encrypt = false;
  esp_now_add_peer(&peer);

  dataBatch.sample_count = 0; 
  dataBatch.battery_mv = 0;

  #if (portNUM_PROCESSORS > 1)
    xTaskCreatePinnedToCore(mpuTask, "MpuTask", 4096, NULL, 2, &mpuTaskHandle, 1);
    xTaskCreatePinnedToCore(ppgTask, "PpgTask", 4096, NULL, 3, &ppgTaskHandle, 1);
    xTaskCreatePinnedToCore(batteryTask, "BattTask", 2048, NULL, 1, &batteryTaskHandle, 0);
  #else
    xTaskCreate(mpuTask, "MpuTask", 4096, NULL, 2, &mpuTaskHandle);
    xTaskCreate(ppgTask, "PpgTask", 4096, NULL, 3, &ppgTaskHandle);
    xTaskCreate(batteryTask, "BattTask", 2048, NULL, 1, &batteryTaskHandle);
  #endif

  systemRunning = true;
  digitalWrite(LED_BUILTIN, LOW);
}

void loop() {
  if (systemRunning && (millis() - ledTimer > (ledState ? 150 : 1000))) {
    ledState = !ledState;
    digitalWrite(LED_BUILTIN, ledState);
    ledTimer = millis();
  }

  if (sensorsActive) {
    PpgData p;
    if (xQueueReceive(ppgQueue, &p, 0)) {
      
      float instantaneousFs = 0.0f;
      if (lastSampleTime > 0) {
        int64_t dt = p.timestamp - lastSampleTime;
        if (dt > 0) instantaneousFs = 1000000.0f / (float)dt;
      }
      lastSampleTime = p.timestamp;

      MpuData m;
      xSemaphoreTake(mpuMutex, portMAX_DELAY);
      m = mpuDataGlobal;
      xSemaphoreGive(mpuMutex);

      int idx = dataBatch.sample_count;
      dataBatch.samples[idx].timestamp_us = p.timestamp;
      dataBatch.samples[idx].red = (uint32_t)p.red;
      dataBatch.samples[idx].ir  = (uint32_t)p.ir;
      dataBatch.samples[idx].ax = m.ax; 
      dataBatch.samples[idx].ay = m.ay; 
      dataBatch.samples[idx].az = m.az;
      dataBatch.samples[idx].gx = m.gx;
      dataBatch.samples[idx].gy = m.gy; 
      dataBatch.samples[idx].gz = m.gz;
      dataBatch.samples[idx].instantaneousFs = instantaneousFs;
      
      dataBatch.sample_count++;

      if (dataBatch.sample_count >= SAMPLES_PER_PACKET) {
        dataBatch.battery_mv = batteryVoltage_mv;
        esp_now_send(masterAddress, (uint8_t*)&dataBatch, sizeof(dataBatch));
        dataBatch.sample_count = 0; 
      }
      
    } else {
      delay(2);
    }
  } else {
    lastSampleTime = 0;
    delay(10);
  }
}