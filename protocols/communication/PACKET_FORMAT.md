# Packet Format and Data Batching

## Overview
Transmitting a wireless packet for every single sensor reading (50 times per second) is highly inefficient and severely degrades battery life due to radio overhead. To solve this, the SPEC-P6 Sensor Nodes implement a data batching strategy before transmitting the ESP-NOW payload.

## Batching Strategy
- **Target Sampling Rate:** 50 Hz (1 sample every 20 ms).
- **Batch Size:** 5 samples per wireless packet.
- **Transmission Rate:** 10 packets per second (10 Hz).

By grouping 5 samples into a single payload, the radio transmitter is active only 10 times per second, significantly reducing power consumption while maintaining the high-resolution 50 Hz temporal data string.

## ESP-NOW Payload Structure
The maximum payload size for ESP-NOW is 250 bytes. The SPEC-P6 data packet is designed to fit comfortably within this limit.

### 1. Packet Header
Every transmitted packet begins with metadata for network management:
- `Node_ID` (uint8_t): Identifies the anatomical source (e.g., 1=Finger, 2=Wrist, 3=Retroauricular).
- `Packet_Counter` (uint32_t): An incrementing integer to track packet loss or out-of-order deliveries.
- `Battery_Level` (uint16_t): The current battery voltage in millivolts.

### 2. Data Frames (Array of 5)
Following the header, the packet contains an array of 5 `SensorFrame` structures. Each frame represents a single 20 ms snapshot containing:
- `DeviceTimestamp_us` (uint32_t): Microsecond precision FreeRTOS tick.
- `PPG_Red` (uint32_t): MAX30102 Red channel intensity.
- `PPG_IR` (uint32_t): MAX30102 Infrared channel intensity.
- `Accel_X, Accel_Y, Accel_Z` (int16_t x 3): MPU-6050 Acceleration vectors.
- `Gyro_X, Gyro_Y, Gyro_Z` (int16_t x 3): MPU-6050 Angular velocity vectors.

Upon receiving this structured payload, the Coordinator unpacks the 5 frames and streams them individually over the serial port to the Python interface, reconstructing the continuous 50 Hz signal.
