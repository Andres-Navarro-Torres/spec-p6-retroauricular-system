# Mechanical Enclosures

## Overview
This directory contains the 3D CAD files and ready-to-print STL files for the SPEC-P6 Sensor Node enclosures. The designs are optimized for fused deposition modeling (FDM) 3D printers and feature specific ergonomic curves for three anatomical sites:
1. Retroauricular (Behind the ear)
2. Wrist
3. Index Finger

## 3D Printing Parameters
To ensure structural integrity and a proper friction-fit for the PCB and battery, the following printing parameters are recommended (tested on Bambu Lab printers):

- **Material:** TPU (Thermoplastic Polyurethane) is highly recommended for the wrist and retroauricular cases to maximize patient comfort and skin compliance. PLA or PETG can be used for the rigid finger enclosure.
- **Layer Height:** 0.12 mm or 0.16 mm (crucial for the snap-fit tolerances).
- **Infill:** 20% to 30% (Gyroid or Grid pattern).
- **Supports:** Required only for the overhanging clips on the index finger model. The wrist and retroauricular cases are designed to print flat without supports.
- **Wall Loops:** 3 (to protect the internal electronics).

## Files Included
- `/STL_Files/`: Exported mesh files, ready to be sliced in software like Bambu Studio or Ultimaker Cura.
- `/CAD_Source/`: Original parametric files (e.g., Fusion 360 .f3d or .step) to allow researchers to modify the enclosures for different battery sizes or anatomical variations.
