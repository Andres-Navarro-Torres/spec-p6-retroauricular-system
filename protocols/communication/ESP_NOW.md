# SPEC-P6 ESP-NOW Communication Protocol

## Overview

SPEC-P6 uses ESP-NOW as the wireless communication protocol between the Coordinator and multiple Sensor Nodes.

The communication architecture follows a star topology, with one Coordinator communicating with multiple Sensor Nodes.

```text
                    Coordinator
                         |
             +-----------+-----------+
             |           |           |
             v           v           v
          Node 1       Node 2       Node 3
```

Network roles
Coordinator

The Coordinator is responsible for managing communication with the Sensor Nodes.

Its main functions are:

Sending control commands to the Sensor Nodes.
Receiving measurement data from the Sensor Nodes.
Forwarding acquired data to the host computer through the serial interface.
Providing the synchronization interface for the BIOPAC system.

The Coordinator is a functional role and does not require a dedicated SPEC-P6 PCB. It can be implemented using a compatible ESP32 device with ESP-NOW support.

Sensor Nodes

Each Sensor Node is a custom-designed SPEC-P6 wearable acquisition device.

Each node integrates:

XIAO ESP32-C6
MAX30102 PPG sensor
MPU6050 IMU
Custom PCB
LiPo battery

The same Sensor Node hardware is used at the retroauricular region, wrist, and index finger.

Communication topology

The system uses a star topology:

```text
                 Coordinator
                  ESP32
                    |
          +---------+---------+
          |         |         |
          v         v         v
       Node 1     Node 2     Node 3
```

The Coordinator acts as the central communication point.

Sensor Nodes do not directly exchange measurement data with each other.

Communication directions
Coordinator to Sensor Nodes

The Coordinator transmits control commands to the Sensor Nodes.

These commands are used to control system operation, including acquisition and calibration procedures.

Sensor Nodes to Coordinator

The Sensor Nodes transmit measurement packets containing PPG, inertial, timing, and battery information to the Coordinator.

Acquisition rate

The target sampling frequency of the Sensor Nodes is 50 Hz.

Five consecutive samples are grouped into each data packet before wireless transmission.

Therefore, the nominal packet transmission rate per Sensor Node is:

50 samples/s ÷ 5
