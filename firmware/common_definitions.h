/**
 * @file common_definitions.h
 * @author Andrés Navarro
 * @brief Shared definitions and data structures for the SPEC-P6 ESP-NOW system.
 * @institution Universidad de Guadalajara (UdeG) - CUCEI
 * @date 2026
 */

#ifndef COMMON_DEFINITIONS_H
#define COMMON_DEFINITIONS_H

#include <stdint.h>

#define ESPNOW_CHANNEL 1
#define ESPNOW_TX_POWER 48

#define PPG_POLL_INTERVAL_MS 15

#define BATTERY_ADC_PIN A0
#define BATTERY_DIVIDER_RATIO 2.0f
#define BATTERY_UPDATE_INTERVAL_MS 15000UL

uint8_t masterAddress[] = {0x10, 0x51, 0xDB, 0x1A, 0x30, 0xF4};

uint8_t slave1Address[] = {0xE4, 0xB3, 0x23, 0xB5, 0xAE, 0xD0};
uint8_t slave2Address[] = {0xE4, 0xB3, 0x23, 0xB4, 0x8C, 0xAC};
uint8_t slave3Address[] = {0xE4, 0xB3, 0x23, 0xB5, 0x82, 0xB8};

uint8_t* slaveAddresses[] = { slave1Address, slave2Address, slave3Address };
const int numSlaves = sizeof(slaveAddresses) / sizeof(slaveAddresses[0]);

typedef struct __attribute__((packed)) struct_cmd_packet {
    char command;
} struct_cmd_packet;

#define SAMPLES_PER_PACKET 5

typedef struct __attribute__((packed)) struct_single_sample {
    uint64_t timestamp_us;
    uint32_t red;
    uint32_t ir;
    int16_t ax;
    int16_t ay;
    int16_t az;
    int16_t gx;
    int16_t gy;
    int16_t gz;
    float instantaneousFs;
} struct_single_sample;

typedef struct __attribute__((packed)) struct_data_packet {
    uint8_t sample_count;
    uint16_t battery_mv;
    struct_single_sample samples[SAMPLES_PER_PACKET];
} struct_data_packet;

typedef struct __attribute__((packed)) struct_status_packet {
    char message[16];
} struct_status_packet;

#endif