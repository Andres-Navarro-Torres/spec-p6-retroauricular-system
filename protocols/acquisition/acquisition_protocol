
# Acquisition Protocol

## Overview
This document details the data acquisition methodology implemented in the SPEC-P6 Sensor Nodes. The firmware is designed to capture high-fidelity physiological and inertial data using a deterministic, FreeRTOS-based architecture on the XIAO ESP32-C6 microcontroller.

## Sensor Interfaces
The SPEC-P6 node interfaces with two primary sensors over the I2C bus:
1. **MAX30102 (Photoplethysmography - PPG):** Configured to acquire RED and IR optical absorption signals.
2. **MPU-6050 (Inertial Measurement Unit - IMU):** Configured to acquire 3-axis acceleration and 3-axis angular velocity.

Both sensors operate on the same I2C bus, managed through the ESP32-C6 I2C peripheral. A PCA9306 logic level translator ensures safe communication between the 3.3V logic of the MCU/IMU and the 1.8V bus requirement of the MAX30102.

## Sampling Rate and Timing
- **Target Sampling Frequency (Fs):** 50 Hz.
- **Timing Mechanism:** High-resolution device timestamps (`DeviceTimestamp_us`) are generated using native FreeRTOS timer ticks. This ensures that every sample is logged with precise temporal spacing, completely independent of wireless transmission delays.

## FreeRTOS Task Architecture
To prevent I2C bus collisions and maintain a strict 50 Hz sampling rate, the firmware utilizes isolated FreeRTOS tasks:
- **Acquisition Task:** Runs with high priority. It polls the MPU-6050 registers and reads the MAX30102 FIFO buffer exactly every 20 milliseconds.
- **System Task:** Runs with lower priority. It monitors battery voltage via the internal ADC and manages LED state indications.

## Data Structure
A single data frame acquired at each 20 ms tick contains:
- 1x 32-bit Timestamp (Microseconds)
- 1x 32-bit PPG RED value
- 1x 32-bit PPG IR value
- 3x 16-bit Accelerometer values (X, Y, Z)
- 3x 16-bit Gyroscope values (X, Y, Z)
- 1x 16-bit Battery measurement
