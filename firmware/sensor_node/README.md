# SPEC-P6 Sensor Node

## Description

The SPEC-P6 Sensor Node is the wearable multisensor acquisition unit developed for simultaneous photoplethysmographic (PPG) and inertial measurement.

Each Sensor Node integrates:

- XIAO ESP32-C6 microcontroller
- MAX30102 photoplethysmography sensor
- MPU6050 inertial measurement unit (IMU)
- Custom-designed PCB
- 3.7 V, 100 mAh LiPo battery

The same Sensor Node hardware is used for the three anatomical measurement sites: retroauricular region, wrist, and index finger.

## Main functions

The Sensor Node:

1. Acquires PPG data from the MAX30102.
2. Acquires inertial data from the MPU6050.
3. Generates device timestamps.
4. Packages multiple samples into ESP-NOW data packets.
5. Transmits data wirelessly to the Coordinator.
6. Receives control commands from the Coordinator.
7. Reports battery voltage.

## Firmware

The firmware uses FreeRTOS-based concurrent tasks for sensor acquisition and system management.

## Sampling

The target acquisition rate is 50 Hz for PPG and inertial data.

Five samples are grouped into each data packet before wireless transmission.

## Communication

Communication with the Coordinator is performed using ESP-NOW.

The Sensor Node transmits measurement data to the Coordinator and receives control commands from it.

## Hardware documentation

The complete hardware design, including PCB files, schematic, Gerber files, and bill of materials, is available in:

`/hardware/sensor_node/`

## Configuration

Network configuration parameters are currently defined in the shared firmware definitions.

See:

`/firmware/common/common_definitions.h`

## Reproduction

To reproduce a Sensor Node:

1. Manufacture the PCB.
2. Assemble the listed components.
3. Program the XIAO ESP32-C6 with the Sensor Node firmware.
4. Configure the ESP-NOW network parameters.
5. Verify communication with the Coordinator.
6. Verify PPG and IMU acquisition before deployment.
