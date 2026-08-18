# SPEC-P6 Acquisition Software

## Overview

The SPEC-P6 Acquisition Software is a high-performance Python-based graphical user interface developed for real-time monitoring, visualization, synchronization, and data logging from the SPEC-P6 wearable sensor network.

The software interfaces directly with the SPEC-P6 Coordinator via a high-speed serial link.

## Main functions

The application provides:

- Real-time multi-channel visualization of photoplethysmography (PPG) signals (IR and RED channels) with optional bandpass filtering and moving-window display.
- Real-time visualization of 6-axis inertial measurement unit (IMU) data (accelerometer and gyroscope).
- Live monitoring of connected Sensor Nodes, packet health, and battery voltage status.
- Centralized acquisition control (Start, Stop, and Calibration commands).
- Automated sensor calibration and signal quality index (SQI) evaluation.
- Instantaneous and moving-average sampling-frequency estimation (Fs).
- Heart-rate (HR) estimation via Welch's method and spectral power density (PSD) monitoring.
- Synchronized multi-node data recording and structured CSV data export.
- Universal hardware synchronization via an external digital/TTL trigger output (compatible with standard DAQ systems or reference instruments).

## System communication

The communication architecture follows a star topology where the host computer links to a central Coordinator, which in turn communicates wirelessly with multiple Sensor Nodes via ESP-NOW:

PC (Python GUI) <-> Serial (921,600 baud) <-> Coordinator (ESP32) <-> ESP-NOW <-> Sensor Nodes (XIAO ESP32-C6)

The current implementation utilizes a high-speed serial communication rate of 921,600 baud between the host computer and the Coordinator.

## Data acquisition and packet structure

The software receives aggregated data packets from the Coordinator and maintains independent ring buffers (RingBuffer) for each active Sensor Node. 

The target acquisition frequency is 50 Hz. Each received measurement sample contains:

- High-resolution device timestamp (DeviceTimestamp_us).
- PPG Red channel intensity.
- PPG Infrared (IR) channel intensity.
- Accelerometer data (Ax, Ay, Az).
- Gyroscope data (Gx, Gy, Gz).
- Instantaneous sampling frequency estimate (Instant_Fs_Hz).
- Node battery voltage (Battery_mV and estimated percentage).

## Calibration and synchronization protocol

Before starting an official recording session, the software manages an automated protocol:

1. Calibration Trigger: The interface sends a calibration command (3) to the nodes via the Coordinator.
2. Sensor Check: Verifies optical coupling (finger/skin detection threshold) and adjusts LED power dynamically.
3. Grace Period & Alignment: Listens for incoming nodes during a grace period (JOIN_GRACE_SECONDS) and synchronizes timestamps across all active devices.
4. TTL Trigger Activation: Automatically fires a digital TTL pulse (setting Coordinator Pin 2 HIGH) to trigger external DAQ equipment at the exact start of valid data recording.
5. Continuous Logging & Preview: Buffers data, displays a real-time preview upon completion, and allows final export to structured CSV files.

## Data output

The software exports synchronized data as structured CSV files containing multi-column telemetry for all connected nodes, including precise timing, physiological signals, inertial dynamics, and system metadata.

## Requirements

The software requires Python 3.x and the dependency packages listed in requirements.txt:

- PyQt6 (Graphical interface framework)
- pyqtgraph (High-performance real-time plotting)
- numpy (Numerical computations and buffer management)
- scipy (Signal processing, filtering, and Welch PSD estimation)
- pyserial (Serial port communication handling)
- openpyxl (Spreadsheet and Excel file management)

## Installation

Install the required Python dependencies by running:

    pip install -r requirements.txt

## Execution

Run the acquisition software suite with:

    python spec_p6_acquisition_suite.py

## Hardware requirements

Running this software requires:

- A SPEC-P6 Coordinator (standard ESP32 development board running coordinator.ino).
- One or more SPEC-P6 Sensor Nodes (custom PCB based on Seeed Studio XIAO ESP32-C6 running sensor_node.ino).
- A USB-C to USB-A cable connecting the Coordinator to the host PC (operating at 921,600 baud).
- Optional: An external DAQ system connected via a digital TTL cable to the Coordinator’s sync pin (Pin 2).

## Notes

This software is designed to operate seamlessly alongside the SPEC-P6 firmware and communication protocol framework. 

For hardware schematics, PCB files, mechanical CAD/STL enclosures, and firmware sources, refer to the root repository documentation.
