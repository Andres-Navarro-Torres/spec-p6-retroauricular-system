# SPEC-P6: Wearable Retroauricular PPG Monitoring System

![SPEC-P6 System](docs/photo_devices.jpg) 
*(Note: Replace this image with a high-quality photo of your assembled devices)*

## Overview
The **SPEC-P6** is a custom-engineered, multi-device wearable system designed for continuous retroauricular photoplethysmography (PPG) acquisition under movement dynamics. 

This repository contains the complete "full-stack" bioengineering development, integrating parametric 3D-printed hardware, microcontroller firmware (Master/Slave architecture), and a Python-based Graphical User Interface (GUI) for real-time visualization and data logging.

This project is part of the research framework submitted to the **EMBC IEEE 2026 (Toronto)**.

## System Architecture
The system operates on a distributed architecture to ensure low latency and high signal fidelity during physical movement:
1. **Slave Devices (Sensor Nodes):** Acquire raw PPG signals from the retroauricular region and transmit them reliably to the central hub.
2. **Master Device (Central Hub):** Synchronizes and gathers data from the slave nodes, handling preprocessing and serial communication to the PC.
3. **Python GUI (Desktop Station):** Receives the real-time serial stream, processes the data, displays live waveforms, and logs the session for offline analysis.

## Repository Structure
* `/firmware`: Arduino `.ino` source code for both the Master hub and Slave sensor nodes.
* `/software`: Python source code for the real-time GUI (Built with [Tkinter / PyQt / CustomTkinter]).
* `/hardware`: Autodesk Fusion 360 source files and `.stl` meshes optimized for Bambu Lab 3D printers.
* `/docs`: System block diagrams and hardware photographs.

## Hardware & Manufacturing
The enclosures were parametrically designed to be lightweight, ergonomic, and resistant to mechanical artifacts during movement.
* **CAD Software:** Autodesk Fusion 360
* **3D Printer:** Bambu Lab [Your Printer Model, e.g., P1P or X1 Carbon]
* **Material:** [PLA / PETG / TPU]
* **Slicer Settings:** [e.g., 15% Gyroid infill, no supports needed]

## Firmware Setup (Microcontrollers)
The microcontrollers were programmed using the Arduino IDE. 
1. Open `firmware/slave_device/slave_device.ino` and upload to the sensor nodes.
2. Open `firmware/master_device/master_device.ino` and upload to the central hub.
*Dependencies:* [List any specific Arduino libraries you used, e.g., Wire.h, specific PPG sensor libraries].

## Software Installation (Python GUI)
The desktop application requires Python 3.8+. To install the required dependencies and run the interface:

```bash
# 1. Install requirements
pip install -r requirements.txt

# 2. Run the application
python software/main.py
