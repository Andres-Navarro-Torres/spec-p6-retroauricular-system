# SPEC-P6 Acquisition Software

## Overview

The SPEC-P6 Acquisition Software is a Python-based graphical interface developed for real-time monitoring, control, synchronization, and data acquisition from the SPEC-P6 wearable sensor network.

The software communicates with the SPEC-P6 Coordinator through a serial interface.

## Main functions

The application provides:

- Real-time visualization of PPG signals.
- Real-time visualization of inertial measurements.
- Monitoring of connected Sensor Nodes.
- Acquisition control.
- Sensor calibration control.
- Sampling-frequency estimation.
- Heart-rate estimation.
- Data recording.
- CSV data export.
- BIOPAC synchronization control.

## System communication

The communication architecture is:

PC → Serial → Coordinator → ESP-NOW → Sensor Nodes

The current implementation uses a serial communication rate of 921600 baud between the host computer and the Coordinator.

## Data acquisition

The software receives data from the Coordinator and maintains independent data buffers for each Sensor Node.

The target acquisition frequency is 50 Hz.

Each received measurement contains:

- Device timestamp.
- PPG red channel.
- PPG infrared channel.
- Accelerometer data (X, Y, Z).
- Gyroscope data (X, Y, Z).
- Instantaneous sampling-frequency estimate.
- Battery voltage.

## Calibration and synchronization

Before an acquisition, the software can initiate the Sensor Node calibration procedure through the Coordinator.

The acquisition sequence includes:

1. Sensor Node calibration.
2. Acquisition start command.
3. Detection of active Sensor Nodes.
4. Data reception and buffering.
5. BIOPAC synchronization trigger.
6. Data recording.
7. Acquisition termination.
8. CSV export.

## Data output

The software exports acquired data as CSV files.

The exported data include PPG, inertial, timing, sampling-frequency, and battery information for the detected Sensor Nodes.

## Requirements

The software requires Python and the packages listed in:

`requirements.txt`

The main dependencies include:

- PyQt6
- PyQtGraph
- NumPy
- SciPy

## Installation

Install the required Python packages with:

```bash
pip install -r requirements.txt
```
Execution

Run the acquisition software with:
python spec_p6_acquisition_suite.py

Hardware requirements

The software requires:

A SPEC-P6 Coordinator running the Coordinator firmware.
One or more SPEC-P6 Sensor Nodes.
A USB/serial connection between the Coordinator and the host computer.
Notes

The acquisition software is intended to operate together with the SPEC-P6 firmware and communication protocol.

See the following documentation:

/firmware/sensor_node/
/firmware/coordinator/
/protocols/communication/
/protocols/synchronization/

