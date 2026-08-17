# SPEC-P6: Open-Source Wearable Retroauricular PPG System

![SPEC-P6 System](docs/photo_devices.jpg)

## Overview
The **SPEC-P6** is an open-source, multi-device wearable system engineered for the continuous acquisition of retroauricular photoplethysmography (PPG) signals under movement dynamics. 

This repository serves as the official companion for our hardware submission, providing all necessary mechanical CAD files, electronics schematics, firmware, and software to fully replicate the system.

* **Target Discipline:** Biomedical Engineering, Human-Computer Interaction
* **Hardware Type:** Wearable Biosensor System
* **Cost to Build:** ~$ [XX.XX] USD *(Replace with total from BOM)*

## Repository Contents
To comply with Open Source Hardware standards, this repository is organized to facilitate full replication:

* `BOM.csv`: Complete Bill of Materials including component costs, sourcing links, and quantities.
* `/hardware`: Contains all parametric 3D models (Autodesk Fusion 360 `.step` and `.f3d`), `.stl` meshes ready for FDM printing, and electronics wiring diagrams.
* `/build_instructions`: A step-by-step visual `assembly_guide.md` detailing the soldering, hardware integration, and enclosure assembly.
* `/firmware`: Microcontroller code for the distributed Master/Slave architecture (Arduino IDE).
* `/software`: Python-based Graphical User Interface for real-time visualization and data logging.

## Replication & Assembly
To build your own SPEC-P6 system, please refer to the following documents in order:
1. Purchase components listed in the [BOM.csv](BOM.csv).
2. Print the enclosures and assemble the electronics following the [Assembly Guide](build_instructions/assembly_guide.md).
3. Flash the [Firmware](firmware/) to the sensor nodes and central hub.
4. Install and run the [Python GUI](software/) to begin data acquisition.

## Open Source Licenses
This project is certified Open Source Hardware and utilizes the following licenses:
* **Hardware (Mechanical & Electronics):** CERN Open Hardware Licence v1.2 (CERN-OHL-W)
* **Software & Firmware:** MIT License
* **Documentation:** Creative Commons Attribution 4.0 International (CC BY 4.0)

## Contact & Citation
If you build upon this hardware design, please cite our corresponding *HardwareX* manuscript:
> Navarro, A., et al. (2026). "[Your Exact Paper Title]". *HardwareX* (Submitted/Under Review).

**Andrés Navarro**  
M.Sc. Candidate in Bioengineering and Intelligent Computing  
[Your LinkedIn URL]
