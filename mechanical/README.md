# Mechanical Enclosures

## Overview
This directory contains the 3D CAD files and ready-to-print STL files for the SPEC-P6 Sensor Node enclosures. The designs are optimized for fused deposition modeling (FDM) 3D printers and feature specific ergonomic curves for three anatomical sites:
1. Retroauricular (Behind the ear)
2. Wrist
3. Index Finger

## 3D Printing Parameters
To ensure structural integrity, a proper friction-fit for the internal electronics, and optimal sensor performance, the following printing parameters are recommended (tested on Bambu Lab printers):

- **Material:** The designs were originally optimized for **PLA (Polylactic Acid)**. However, if higher mechanical resistance, firmness, or thermal stability is required, materials like PETG or ABS can be used according to the researcher's preference.
- **Color (CRITICAL):** It is highly recommended to use **Black or very dark-colored filaments**. Light or translucent colors allow ambient light to penetrate the casing and refract inside, which causes severe optical interference with the MAX30102 PPG sensor. Dark materials effectively absorb ambient light, ensuring high signal quality.
- **Layer Height:** 0.12 mm or 0.16 mm (crucial for the snap-fit tolerances and smooth surface finish).
- **Infill:** 20% to 30% (Gyroid or Grid pattern).
- **Supports:** Required only for the overhanging clips on the index finger model. The wrist and retroauricular cases are designed to print flat without supports.
- **Wall Loops:** 3 (to protect the internal electronics and improve optical isolation).

## Files Included
- `/STL_Files/`: Exported mesh files, ready to be sliced in software like Bambu Studio or Ultimaker Cura.
- `/CAD_Source/`: Original parametric files (e.g., Fusion 360 .f3d or .step) to allow researchers to modify the enclosures for different battery sizes or anatomical variations.
