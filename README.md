# SPEC-P6: An Open-Source, Modular, and Synchronized Wearable Sensor Platform for Physiological and Movement Acquisition

## Overview

SPEC-P6 is an open-source, reproducible, and modular wearable platform designed for simultaneous, multi-site acquisition of photoplethysmography (PPG) and inertial measurement unit (IMU) data. The system enables synchronized telemetry across multiple anatomical locations (specifically configured for the retroauricular region, wrist, and index finger) using a wireless star network architecture.

## System Architecture

The platform operates under a star network topology where a central Coordinator gathers data packets from multiple wearable Sensor Nodes via ESP-NOW and forwards them to a host computer through a high-speed serial link:

PC (Python GUI) <-> Serial (921,600 baud) <-> Coordinator (ESP32) <-> ESP-NOW <-> Sensor Nodes (XIAO ESP32-C6)

- **Sensor Node (Custom Hardware):** A custom-designed compact PCB integrating a Seeed Studio XIAO ESP32-C6, a MAX30102 PPG sensor, an MPU6050 6-axis IMU, LDO voltage regulators, a 3.7V 100 mAh LiPo battery, and power/user management switches.
- **Coordinator (Functional Role):** A standard COTS ESP32 development board running firmware that bridges wireless ESP-NOW telemetry to a serial stream, while also providing a hardware digital/TTL synchronization trigger (Pin 2) for external DAQ systems (e.g., BIOPAC).

## Repository Structure

The repository is organized into the following directories:

- `/Hardware/`: Contains custom PCB Gerber files, schematic diagrams, source files, and the bill of materials (BOM).
- `/Mechanical/`: Includes 3D printable STL files and editable CAD source files for the wearable enclosures across all anatomical sites.
- `/Firmware/`: Houses the source code for both the Sensor Nodes (`sensor_node.ino`) and the Coordinator (`coordinator.ino`), alongside shared definitions (`common_definitions.h`).
- `/Software/`: Contains the Python-based graphical acquisition suite (`spec_p6_acquisition_suite.py`), battery logging utilities, and package dependencies (`requirements.txt`).
- `/Validation_Data/`: Includes experimental telemetry datasets, battery discharge logs, and characterization scripts.

## Key Technical Specifications

- **Target Sampling Rate:** 50 Hz for both PPG and IMU streams.
- **Wireless Protocol:** ESP-NOW (packaged in batches of 5 samples per transmission to optimize network bandwidth).
- **Concurrency:** FreeRTOS-based multitasking on the ESP32-C6 core for robust sensor polling and transmission.
- **Battery Life:** ~58 hours / minutes of continuous multi-sensor operation on a 100 mAh LiPo cell.
- **Timing Performance:** Low jitter (< 0.6 ms) and zero packet loss under standard laboratory testing conditions.

## Quick Start & Reproduction Guide

To deploy and operate the SPEC-P6 platform:

1. **Hardware Fabrication:** Order the PCB using the Gerber files in `/Hardware/` and assemble following the BOM guidelines.
2. **Firmware Flashing:** 
   - Flash `coordinator.ino` onto your Coordinator ESP32 device.
   - Flash `sensor_node.ino` onto your XIAO ESP32-C6 nodes, ensuring MAC addresses are correctly mapped in `common_definitions.h`.
3. **Mechanical Enclosures:** Print the 3D cases located in `/Mechanical/STL_Files/` (recommended in TPU/PETG).
4. **Software Execution:** 
   - Install Python dependencies via `pip install -r Software/requirements.txt`.
   - Run the acquisition suite using `python Software/spec_p6_acquisition_suite.py`.

## License

To effectively cover both the software and physical hardware designs, this project employs a dual-licensing strategy:

- **Software and Firmware:** Licensed under the [MIT License](LICENSE).
- **Hardware and Mechanical Designs:** Licensed under the CERN Open Hardware Licence Version 2 - Permissive (CERN-OHL-P). You may redistribute and modify the hardware documentation and make products using it under the terms of the CERN-OHL-P v2 (https://ohwr.org/cernohl).
