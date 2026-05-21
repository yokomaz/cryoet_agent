# IMOD Coordinate System (Reference)

## Overview

IMOD's coordinate system is the **de facto standard** for cryo-ET. This document provides a definitive specification derived from the IMOD source code (specifically `libcfpeba/` and `libiimod/`), MRC header conventions, and the IMOD user guide.

---

## 3D Volume Coordinate System

### Axis Definitions

```
IMOD 3D Volume (right-handed):

       Z (sections, beam direction)
       ↑
       │
       │  ┌──────────────────────→ X (in-plane, ⊥ tilt axis)
       │ /
       │/
       └────────────────────────→ Y (tilt axis)
```

In MRC/CCP4 header terms:

| Axis | MRC Dimension | MRC Label | Physical Meaning | Indexing (in memory) |
|------|--------------|-----------|-----------------|----------------------|
| **X** | `nx` | fast axis | In-plane, perpendicular to tilt axis | `vol[z][y][x]` in C, `vol(x,y,z)` in Fortran |
| **Y** | `ny` | medium axis | Tilt axis direction | `vol[z][y][x]` in C, `vol(x,y,z)` in Fortran |
| **Z** | `nz` | slow axis | Beam direction / section number | `vol[z][y][x]` in C, `vol(x,y,z)` in Fortran |

### MRC Header Origin Convention

IMOD sets the volume origin to the **center of the tomogram**:

```c
// Typical IMOD convention (from libiimod/imodtrans.c)
origin.x = nx * xVoxelSize / 2.0;  // Angstroms
origin.y = ny * yVoxelSize / 2.0;
origin.z = nz * zVoxelSize / 2.0;
```

The origin is stored in:
- MRC header fields `origin.x`, `origin.y`, `origin.z` (MRC 2014 extension header, word 50-52 from start of extended header)
- For subvolumes: `nxstart`, `nystart`, `nzstart` define the subvolume's offset within a larger volume

### Voxel Size

```c
// From MRC header:
voxelSizeX = cella.x / nx;  // cella is the cell dimensions in Angstroms
voxelSizeY = cella.y / ny;
voxelSizeZ = cella.z / nz;
```

### Handedness

IMOD uses a **right-handed** coordinate system:
- X × Y = Z (right-hand rule)
- This means if X points right and Y points into the screen, Z points up

---

## 2D Image Coordinate System (Tilt Series)

In 2D (individual tilt images), IMOD uses:

```
      Y (tilt axis)
      ↑
      │
      │
      │
      └──────────────→ X (⊥ tilt axis)
```

| Axis | MRC Dimension | Meaning |
|------|--------------|---------|
| **X** | `nx` | Perpendicular to tilt axis (horizontal in image) |
| **Y** | `ny` | Along tilt axis (vertical in image) |

The **tilt axis** is along Y. The tilt geometry:

```
Side view (looking along Y / tilt axis):

      Z (beam)
      ↑
      │
      │  tilted specimen
      │  /
      │ /
      │/
      └────────────→ X
     detector plane
```

The specimen is tilted around the Y axis. In IMOD's `.tlt` file, each angle represents a rotation around Y:
- Positive angle = specimen tilted in positive direction around Y
- Convention: `TiltAngle > 0` means the specimen is tilted so that X and Z rotate in the positive sense around Y

---

## Alignment File (.xf) Convention

IMOD's `.xf` format stores per-tilt alignment transformations:

```
Each line: A1 A2 A3 A4 A5 A6
  or:       A B C D X-shift Y-shift
```

The transformation applied to each 2D tilt image:

```
x' = A*x + B*y + X_offset
y' = C*x + D*y + Y_offset
```

| Coefficient | Meaning | Typical Value |
|-------------|---------|---------------|
| A | Scale & rotation (X from X) | ~1.0 |
| B | Shear (X from Y) | ~0.0 |
| C | Shear (Y from X) | ~0.0 |
| D | Scale & rotation (Y from Y) | ~1.0 |
| X_offset | Translation in X | Pixel shift |
| Y_offset | Translation in Y | Pixel shift |

For a pure rotation by angle θ (rotation in the image plane):

```
A = cos(θ), B = -sin(θ), C = sin(θ), D = cos(θ)
```

---

## Reconstruction Geometry

### Weighted Back-Projection (WBP)

IMOD's `tilt` and `tiltxcorr` use WBP reconstruction. The geometry is:

1. Each tilt image is a projection of the 3D volume along the beam direction at angle α
2. Back-projection smears each projection back along the beam direction at the same angle
3. The 3D reconstruction is the sum of all back-projections, weighted by the tilt angle step

### SIRT Reconstruction

IMOD's `sirt` uses Simultaneous Iterative Reconstruction Technique. The coordinate system is identical to WBP.

### The Reconstruction Equation

For a given tilt with angle α around the Y (tilt) axis:

```
Rotation matrix R(α):
    [ cos(α)   0   sin(α) ]
    [   0      1     0    ]
    [ -sin(α)  0   cos(α) ]

Projection plane at angle α:
    The 2D image lies in the (X, Y) plane
    The projection direction is along Z' = (sin(α), 0, cos(α)) in 3D
```

The reconstruction grid aligns with:
- X: perpendicular to tilt axis
- Y: along tilt axis (projection direction is always ⊥ to Y)
- Z: the sectioning direction

---

## Key Source Code References in IMOD

For detailed verification, the following IMOD source files define the coordinate system:

| File | What It Defines |
|------|-----------------|
| `libiimod/imodtrans.c` | Volume origin and transformation conventions |
| `libiimod/xfio.c` | `.xf` file read/write and transformation application |
| `libiimod/iimodp.h` | MRC header structure and origin fields |
| `libcfpeba/cfpeba.c` | Core reconstruction geometry |
| `mrc/mrcslice.c` | MRC volume I/O and axis mapping |
| `tilt/tilt.c` | Tilt series alignment geometry |

---

## Converting Other Software's Coordinates to IMOD

### General Approach

1. Identify the native axis ordering of the source software
2. Determine which flips (sign changes) are needed
3. Adjust the origin to match IMOD's center-of-volume convention
4. Update MRC header fields (`nx`, `ny`, `nz`, `cella`, `origin`, `nxstart/nystart/nzstart`)

### Common Transformation Chain

```
Source Volume
    → Axis Reorder (permute axes)        [e.g., (0,2,1) to swap Y↔Z]
    → Axis Flips (sign change)           [e.g., flip Z for Warp → IMOD]
    → Origin Shift                       [e.g., roll to center origin]
    → MRC Header Update                  [set cella, origin, dimension fields]
    → IMOD-format Volume
```

---

## Validation

To validate that a tomogram is in IMOD coordinates:

1. **Fiducial test**: Reconstruct a dataset containing gold fiducials with both IMOD and the target software
2. **Cross-correlation**: Compute the 3D cross-correlation; the peak should be at the center if both volumes are aligned
3. **FSC comparison**: The Fourier Shell Correlation between the two reconstructions should be independent of coordinate system if the data is the same
4. **Particle coordinates**: Known particle positions should map to the same 3D locations when viewed in 3dmod
