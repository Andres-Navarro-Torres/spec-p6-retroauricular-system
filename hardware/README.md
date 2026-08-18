# Hardware Design Files

## Overview
This directory contains all the electronic design automation (EDA) files required to manufacture the SPEC-P6 Sensor Node custom PCB. 

## PCB Specifications
- **Dimensions:** 22.07 mm x 27.54 mm
- **Layers:** 2-layer rigid FR4
- **Thickness:** 1.6 mm
- **Solder Mask:** Black

## Assembly Strategy (PCBA)
The PCB is designed for a hybrid assembly approach to drastically reduce automated manufacturing costs:
1. **Bottom Layer (SMT):** All surface-mount components (MAX30102, MPU6050, LDO regulators, and passives) are placed on the bottom layer. This layer is designed to be fully assembled by automated pick-and-place machines (e.g., JLCPCB SMT Service).
2. **Top Layer (Manual/THT):** The top layer is reserved for the Seeed Studio XIAO ESP32-C6 microcontroller, the battery slide switch, and the optional tactile button. These components are soldered manually via castellated holes or through-hole pads.

## Files Included
- `SPEC-P6_Schematic.pdf`: The electrical circuit diagram.
- `SPEC-P6_BOM.xlsx`: The Bill of Materials, including exact LCSC part numbers and cost breakdowns for single-node and full-system reproduction.
- `/Gerbers/`: The standard RS-274X Gerber zip file ready to be uploaded to any PCB manufacturer.
