/*
 * TÍTULO: common_definitions.h
 * PROPÓSITO: Definiciones compartidas (RISC-V a Xtensa) para el sistema ESP-NOW.
 * VERSIÓN: Optimización 50 Hz, Batching 5 muestras, TX Power 12 dBm,
 *          Ahorro de energía en polling PPG, medición de batería.
 */

#ifndef COMMON_DEFINITIONS_H
#define COMMON_DEFINITIONS_H

#include <stdint.h>

// ===== Ajustes de radio =====
#define ESPNOW_CHANNEL   1
// Potencia a 12 dBm (48 * 0.25) para asegurar alcance sin devorar la batería
#define ESPNOW_TX_POWER  48       

// ===== Ajustes de ahorro de energía (esclavo) =====
// Antes se sondeaba la FIFO del MAX30102 cada 1 ms (1000 veces/seg).
// La FIFO del MAX30102 tiene 32 posiciones; a 50 Hz efectivos eso son
// ~640 ms de margen antes de perder una muestra. 15 ms de sondeo deja
// un margen de seguridad de ~40x y reduce ~15x los despertares de CPU
// y transacciones I2C respecto al valor anterior.
#define PPG_POLL_INTERVAL_MS       15

// ===== Medición de batería (esclavo) =====
// XIAO ESP32-C6: A0 = GPIO0. A diferencia del XIAO BLE, el C6 NO trae
// divisor resistivo de fábrica en el pin de batería: hay que soldar un
// divisor 1:2 (p.ej. 200k + 200k) entre BAT+ y GND, con el punto medio a A0.
#define BATTERY_ADC_PIN            A0
#define BATTERY_DIVIDER_RATIO      2.0f
// La lectura del ADC se refresca cada 15 s (bajísimo costo energético);
// el valor se cachea y se envía en cada paquete para que el CSV lo
// muestre a la misma Fs que el resto de los datos.
#define BATTERY_UPDATE_INTERVAL_MS 15000UL

// ===== 1. DIRECCIONES MAC (VERIFICADAS) =====
// Maestro (ESP32 DevKit v1) - Derivada de BT MAC (-2 hex)
uint8_t masterAddress[] = {0x10, 0x51, 0xDB, 0x1A, 0x30, 0xF4};

// Esclavos (XIAO ESP32-C6)
uint8_t slave1Address[] = {0xE4, 0xB3, 0x23, 0xB5, 0xAE, 0xD0}; // MUÑECA
uint8_t slave2Address[] = {0xE4, 0xB3, 0x23, 0xB4, 0x8C, 0xAC}; // RETROAURICULAR
uint8_t slave3Address[] = {0xE4, 0xB3, 0x23, 0xB5, 0x82, 0xB8}; // DEDO ÍNDICE

uint8_t* slaveAddresses[] = { slave1Address, slave2Address, slave3Address };
const int numSlaves = sizeof(slaveAddresses) / sizeof(slaveAddresses[0]);

// ===== 2. ESTRUCTURAS DE DATOS (ALINEACIÓN ESTRICTA CRUZADA) =====

// Estructura de COMANDO (PC -> Maestro -> Esclavo)
typedef struct __attribute__((packed)) struct_cmd_packet {
  char command; // '0', '1', '3'
} struct_cmd_packet;

// ==========================================================
// --- ESTRUCTURA DE EMPAQUETAMIENTO (BATCHING) ---
// ==========================================================
#define SAMPLES_PER_PACKET 5 // A 50Hz, enviamos paquetes de 5 muestras (Radio a 10Hz)

// 1. Estructura de una muestra individual
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

// 2. Estructura de DATOS empaquetada (Esclavo -> Maestro)
typedef struct __attribute__((packed)) struct_data_packet {
  uint8_t sample_count; 
  uint16_t battery_mv;   // Voltaje de batería en mV, cacheado (ver batteryTask en el esclavo)
  struct_single_sample samples[SAMPLES_PER_PACKET];
} struct_data_packet;


// Estructura de ESTADO (Esclavo -> Maestro -> PC)
typedef struct __attribute__((packed)) struct_status_packet {
  char message[16]; 
} struct_status_packet;

#endif // COMMON_DEFINITIONS_H
