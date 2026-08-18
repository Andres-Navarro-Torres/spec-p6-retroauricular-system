# Synchronization and Latency Protocol

## Overview
Synchronizing wireless sensor networks with external "Gold Standard" Data Acquisition systems (e.g., BIOPAC) is critical for clinical validation. The SPEC-P6 platform implements a hardware-level digital trigger to guarantee temporal alignment between the wireless telemetry and external reference instruments.

## Hardware Synchronization (TTL Trigger)
The Coordinator firmware is designed to emit a discrete hardware signal marking the exact start of a recording session:
- **Pin Output:** Digital Pin 2 on the Coordinator ESP32.
- **Signal Logic:** 3.3V TTL (Active HIGH).
- **Mechanism:** When the Python GUI issues the Start Recording command, the Coordinator brings Pin 2 HIGH. This pulse is wired directly to a digital input channel on the external DAQ. By aligning the rising edge of the TTL pulse in the external DAQ with the first recorded packet in the SPEC-P6 CSV file, both systems share an absolute time zero ($t_0$).

## Software Synchronization (Grace Period)
To ensure all nodes begin streaming simultaneously:
1. The Coordinator broadcasts a Start command.
2. The network enters a `JOIN_GRACE_SECONDS` window.
3. Timestamps on all nodes are reset, ensuring the first recorded sample across the retroauricular, wrist, and finger nodes shares the exact same baseline.

---

## Validation: The "Tap Test" Protocol
To quantify the end-to-end latency (jitter and delay) of the ESP-NOW transmission, a physical "Tap Test" must be performed in the laboratory.

### Setup Requirements
1. **SPEC-P6 Node:** Powered on and communicating with the GUI.
2. **External DAQ (e.g., BIOPAC):** Equipped with a contact microphone or analog accelerometer, and connected to the Coordinator's TTL sync pin.
3. **Physical Alignment:** Secure the SPEC-P6 node and the DAQ analog sensor to the same rigid surface (e.g., a wooden desk).

### Execution Steps
1. Initiate recording on the external DAQ.
2. Click "Start Acquisition" on the SPEC-P6 Python GUI (This fires the TTL pulse, marking $t_0$ on the DAQ).
3. Using a rigid object (e.g., a pen), deliver three (3) sharp, distinct physical taps to the desk surface near the sensors, leaving approximately 2 seconds between each tap.
4. Stop both recordings.

### Analysis
By comparing the temporal distance between $t_0$ and the three acceleration spikes in the external DAQ software versus the SPEC-P6 CSV output, the absolute transmission latency can be calculated.
