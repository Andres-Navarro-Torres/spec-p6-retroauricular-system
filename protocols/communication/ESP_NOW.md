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
