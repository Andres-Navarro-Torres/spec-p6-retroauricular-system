# SPEC-P6 Coordinator

## Description

The SPEC-P6 Coordinator is the ESP32-based communication and acquisition gateway responsible for coordinating multiple Sensor Nodes.

The Coordinator is a functional role rather than a dedicated SPEC-P6 PCB. It can be implemented using a compatible ESP32 device with ESP-NOW support.

## Main functions

The Coordinator:

1. Communicates with multiple SPEC-P6 Sensor Nodes using ESP-NOW.
2. Sends control commands to the Sensor Nodes.
3. Receives measurement packets from the Sensor Nodes.
4. Forwards acquired data to the host computer through a serial interface.
5. Provides the interface between the wireless sensor network and the acquisition software.
6. Generates the synchronization trigger used for integration with external DAQ systems (e.g., BIOPAC).

## Network architecture

The system uses a star topology:

Coordinator
- Sensor Node 1
- Sensor Node 2
- Sensor Node 3

Sensor Nodes transmit measurement data to the Coordinator.

The Coordinator can transmit control commands to the Sensor Nodes.

## Hardware

The Coordinator does not require a dedicated SPEC-P6 PCB.

Any compatible ESP32 platform capable of ESP-NOW communication may be used, provided that the required firmware interfaces and synchronization output are available.

## Communication

Wireless communication is performed using ESP-NOW.

The host computer communicates with the Coordinator through a serial connection.

## Serial interface

The current acquisition system uses a serial communication rate of 921,600 baud.

## Synchronization

The Coordinator provides the hardware synchronization interface (Pin 2 digital output) used to generate the external synchronization trigger.

## Configuration

ESP-NOW network parameters and device addresses are defined in:

/firmware/common/common_definitions.h

## Reproduction

To reproduce the Coordinator:

1. Select a compatible ESP32 device with ESP-NOW support.
2. Configure the network parameters in common_definitions.h.
3. Upload the Coordinator firmware (coordinator.ino).
4. Configure the Sensor Node MAC addresses.
5. Connect the Coordinator to the host computer via USB (921,600 baud).
6. Verify wireless communication with the Sensor Nodes.
7. Verify the synchronization output before experimental acquisition.
