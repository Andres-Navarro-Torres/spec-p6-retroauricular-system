# ESP-NOW Communication Protocol

## Overview
To achieve high-speed, low-latency, and connectionless data transfer, the SPEC-P6 platform utilizes the Espressif ESP-NOW protocol. This protocol operates over the 2.4 GHz Wi-Fi spectrum but strips away the overhead of standard TCP/IP connections, making it ideal for real-time wearable sensor networks.

## Network Topology
The system employs a deterministic **Star Topology**:
- **Hub (Receiver):** The Coordinator (ESP32) acts as the central receiver, listening for incoming data on a specific Wi-Fi channel.
- **Spokes (Transmitters):** Up to three Sensor Nodes (XIAO ESP32-C6) act as the transmitters, located at the retroauricular region, wrist, and index finger.

## Configuration and Addressing
Unlike standard Wi-Fi that uses IP addresses, ESP-NOW routes packets using hardware MAC addresses.
- **Station Mode:** All devices (Coordinator and Nodes) must be configured in Wi-Fi Station (`WIFI_STA`) mode.
- **MAC Pairing:** The MAC address of the Coordinator is hardcoded into the Sensor Nodes' firmware via `common_definitions.h` to ensure packets are routed strictly to the host receiver.
- **Channel Synchronization:** Both the sender and receiver must operate on the exact same Wi-Fi channel (default is Channel 1).

## Advantages for SPEC-P6
- **Reduced Power Consumption:** Nodes wake up, transmit the payload, and return to sensor polling immediately without waiting for complex TCP handshakes.
- **Low Latency:** Data reaches the Coordinator in fractions of a millisecond.
- **Scalability:** Additional nodes can be added to the network simply by pointing their transmission logic to the Coordinator's MAC address.
