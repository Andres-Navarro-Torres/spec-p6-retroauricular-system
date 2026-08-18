# SPEC-P6 Sensor Node

## Description

The SPEC-P6 Sensor Node is the wearable multisensor acquisition unit developed for simultaneous photoplethysmographic (PPG) and inertial measurement.

Each Sensor Node integrates:

- XIAO ESP32-C6 microcontroller
- MAX30102 photoplethysmography sensor
- MPU6050 inertial measurement unit (IMU)
- Custom-designed PCB (2-layer, 1.6 mm thickness)
- 3.7 V, 100 mAh LiPo battery
- Power slide switch and user tactile push-button

The same Sensor Node hardware is used for the three anatomical measurement sites: retroauricular region, wrist, and index finger.

## Main functions

The Sensor Node:

1. Acquires PPG data from the MAX30102 sensor via I2C.
2. Acquires inertial data (accelerometer and gyroscope) from the MPU6050 via I2C.
3. Generates high-resolution device timestamps using FreeRTOS timer ticks.
4. Packages five samples into structured ESP-NOW data packets to optimize wireless bandwidth.
5. Transmits data wirelessly to the Coordinator using ESP-NOW in a star network topology.
6. Receives control commands from the Coordinator (Start, Stop, and Calibration routines).
7. Monitors and reports battery voltage through an integrated ADC voltage divider.

## Firmware & FreeRTOS Architecture

The firmware is built on FreeRTOS for concurrent multitasking and real-time management:

- Dedicated task handling inertial data acquisition.
- Dedicated task handling PPG FIFO reading and polling.
- Dedicated task monitoring battery voltage status.
- Hardware abstraction and shared protocol definitions managed through common_definitions.h.

## Sampling

The target acquisition rate is 50 Hz for PPG and inertial measurements.

Five samples are grouped into each data packet before wireless transmission.

## Communication

Communication with the Coordinator is performed using ESP-NOW over Wi-Fi STA mode (channel configured via common definitions).

The Sensor Node transmits structured data packets to the Coordinator and listens for incoming control packets.

## Hardware documentation

The complete hardware design, including PCB files, schematic, Gerber files, and bill of materials, is available in:

/hardware/sensor_node/

## Configuration

Network configuration parameters, device MAC addresses, and operational constants are defined in the shared firmware definitions file:

/firmware/common/common_definitions.h

## Reproduction

To reproduce a Sensor Node:

1. Manufacture the custom FR4 PCB using the provided Gerber files.
2. Solder the surface-mount components (bottom layer SMT assembly) and assemble the XIAO ESP32-C6 microcontroller and auxiliary switches (top layer).
3. Connect the 3.7V 100 mAh LiPo battery and power switch.
4. Program the XIAO ESP32-C6 with the Sensor Node firmware (sensor_node.ino).
5. Configure the ESP-NOW network parameters and MAC addresses in common_definitions.h.
6. Verify wireless communication and calibration with the Coordinator.
7. Verify PPG and IMU acquisition before final mechanical casing integration.
