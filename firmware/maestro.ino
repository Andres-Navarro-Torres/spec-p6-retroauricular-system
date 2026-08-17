/**
 * @file master_node.ino
 * @author Andrés Navarro
 * @brief Master Node Firmware (Bridge) - SPEC-P6 System
 * @details Firmware for the ESP32 master node. It acts as a bridge, receiving 
 *          packed sensor data from the slave nodes via ESP-NOW and forwarding 
 *          it through serial communication to the Python interface. It also 
 *          handles broadcast commands and BIOPAC synchronization triggers.
 * @institution Universidad de Guadalajara (UdeG) - CUCEI
 * @date 2026
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include "common_definitions.h"

uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
#define BIOPAC_PIN 2 
#define BAUD_RATE 921600

void OnDataSent(const wifi_tx_info_t* tx_info, esp_now_send_status_t status) {
  if (status != ESP_NOW_SEND_SUCCESS) {
    Serial.println("[ERROR] Fallo al enviar comando Broadcast.");
  }
}

void OnDataRecv(const esp_now_recv_info_t * info, const uint8_t *incomingData, int len) {
  char* slaveID = "Unknown";
  if (memcmp(info->src_addr, slave1Address, 6) == 0) slaveID = "Slave1";
  else if (memcmp(info->src_addr, slave2Address, 6) == 0) slaveID = "Slave2";
  else if (memcmp(info->src_addr, slave3Address, 6) == 0) slaveID = "Slave3";

  if (len == sizeof(struct_data_packet)) {
    struct_data_packet batchData;
    memcpy(&batchData, incomingData, sizeof(batchData));

    for (int i = 0; i < batchData.sample_count; i++) {
        struct_single_sample s = batchData.samples[i];
        Serial.printf("%s,%llu,%u,%u,%d,%d,%d,%d,%d,%d,%.6f,%u\n",
                      slaveID, s.timestamp_us, s.red, s.ir,
                      s.ax, s.ay, s.az, s.gx, s.gy, s.gz, s.instantaneousFs,
                      batchData.battery_mv);
    }
  }
  else if (len == sizeof(struct_status_packet)) {
    struct_status_packet status;
    memcpy(&status, incomingData, sizeof(status));
    if (strcmp(status.message, "CAL_OK") == 0) {
      Serial.printf("CAL_OK,%s\n", slaveID);
    }
  }
}

void broadcastCommand(char cmd) {
  struct_cmd_packet cmdPkt;
  cmdPkt.command = cmd;
  esp_now_send(broadcastAddress, (uint8_t *) &cmdPkt, sizeof(cmdPkt));
}

void setup() {
  Serial.begin(BAUD_RATE);
  pinMode(BIOPAC_PIN, OUTPUT);
  digitalWrite(BIOPAC_PIN, LOW); 

  WiFi.mode(WIFI_STA);
  esp_wifi_set_channel(ESPNOW_CHANNEL, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_max_tx_power(ESPNOW_TX_POWER);
  esp_wifi_set_ps(WIFI_PS_NONE);

  if (esp_now_init() != ESP_OK) return;

  esp_now_register_send_cb(OnDataSent);
  esp_now_register_recv_cb(OnDataRecv);

  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, broadcastAddress, 6);
  peerInfo.channel = ESPNOW_CHANNEL;
  peerInfo.encrypt = false; 
  esp_now_add_peer(&peerInfo);
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = (char)Serial.read();
    if (cmd == '0' || cmd == '1' || cmd == '3') broadcastCommand(cmd);
    else if (cmd == 'B') digitalWrite(BIOPAC_PIN, HIGH);
    else if (cmd == 'b') digitalWrite(BIOPAC_PIN, LOW);
  }
}