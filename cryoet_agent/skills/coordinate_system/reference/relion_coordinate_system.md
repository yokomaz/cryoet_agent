# RELION-tomo Coordinate System

## Overview

RELION (REgularized LIkelihood OptimizatioN) has been extended to cryo-ET ("RELION-tomo"), handling everything from tilt series alignment to subtomogram averaging. Its coordinate system inherits from single-particle RELION but adds cryo-ET-specific conventions for handling tilt geometry and pseudo-subtomograms.

> **Key complexity**: RELION-tomo's coordinate system is split between the "tomogram reconstruction" representation (standard MRC) and the "pseudosubtomogram" representation (RELION's internal STAR-format coordinates).

---

## Source Code Analysis Points

| Source File (RELION 4.0/5.0+) | What to Look For |
|-------------------------------|-----------------|
| `src/tomogram.cpp` | Tomogram I/O, pixel-to-physical coordinate conversion |
| `src/tomogram.h` | Coordinate class definitions |
| `src/backprojector.cpp` | Back-projection kernel; reconstruction geometry |
| `src/tilt_series_alignment_runner.cpp` | Alignment pipeline and coordinate transforms |
| `src/metadata_table.h` | STAR file coordinate fields |
| `src/image.h` | Image and volume axis conventions |

---

## Coordinate Conventions

### Tomogram Volume Coordinates

RELION's reconstructed tomogram follows standard MRC conventions:

| RELION Internal | MRC Header | IMOD | Notes |
|----------------|------------|------|-------|
| X (fast axis) | `nx` | **X** | Maps directly in v5.0+ |
| Y (medium axis) | `ny` | **Y** | Maps directly in v5.0+ |
| Z (slow axis) | `nz` | **Z** | Maps directly |

> **Note**: RELION 4.0 had known issues with Y↔Z axis ordering in certain reconstruction paths. This was fixed in RELION 5.0.

### Physical Coordinates in STAR Files

RELION stores particle coordinates in a **physical coordinate system** (Angstroms) in STAR files:

```
# RELION STAR coordinate convention:
rlnCoordinateX = X_coordinate_in_angstroms
rlnCoordinateY = Y_coordinate_in_angstroms
rlnCoordinateZ = Z_coordinate_in_angstroms
```

The mapping from pixel to physical:

```
X_angstrom = (X_pixel - origin_x_pixel) * angpix_x
Y_angstrom = (Y_pixel - origin_y_pixel) * angpix_y
Z_angstrom = (Z_pixel - origin_z_pixel) * angpix_z
```

### Origin Convention

RELION defines the origin differently from IMOD in STAR files:

| Convention | IMOD | RELION (STAR) |
|-----------|------|---------------|
| Origin definition | Center of volume `(NX/2, NY/2, NZ/2)` | User-defined `rlnOriginX/Y/ZAngst` (or center by default) |
| Origin storage | MRC header `origin.x/y/z` | STAR file fields |
| Subvolume origin | `nxstart/nystart/nzstart` in MRC header | `rlnOriginXAngst` etc. |

### Pseudosubtomogram Coordinates

RELION's **pseudosubtomogram** extraction is where coordinate confusion most often occurs:

```
Pseudosubtomogram coordinate frame (RELION):
    For a particle at physical position P = (Px, Py, Pz):

    1. Extract subvolume centered at P
    2. Apply the CTF at the tilt angle of the tomogram
    3. The subvolume is stored in a RELION-specific orientation:
       - The Z axis of the subvolume aligns with the tilt axis of the original tomogram
       - The Y axis of the subvolume aligns with the beam direction

This is DIFFERENT from IMOD, where:
    - X: ⊥ tilt axis, in-plane
    - Y: tilt axis
    - Z: beam direction
```

> **This is the most common source of subtomogram orientation errors when mixing RELION with other tools.**

---

## Detection Patterns in Source Code

### Pattern 1: Pseudosubtomogram Extraction

```cpp
// In src/tomogram.cpp (conceptual):
void Tomogram::extractSubtomogram(
    RFLOAT x_angst, RFLOAT y_angst, RFLOAT z_angst,
    MultidimArray<RFLOAT>& subtomo, int box_size)
{
    // Look for the axis assignments here:
    int x_start = (int)( (x_angst / angpix) - box_size/2 );
    int y_start = (int)( (y_angst / angpix) - box_size/2 );
    int z_start = (int)( (z_angst / angpix) - box_size/2 );

    // Key check: which axis in the 3D volume is treated as "depth"?
    // If z_start maps to the MRC "sections" dimension and
    // the beam is along Z, then RELION uses IMOD convention
    // If z_start maps to Y (tilt axis), coordinates are rotated
}
```

### Pattern 2: Coordinate Transformation Matrix

```cpp
// In src/tomogram.h or similar:
// Look for hardcoded rotation/permutation matrices:
const Matrix<RFLOAT> tomogram_rotation = {
    1, 0, 0,
    0, 1, 0,
    0, 0, 1
};
// An identity matrix means RELION coordinates match IMOD directly.
// Any non-identity indicates a coordinate transformation.
```

### Pattern 3: Back-projector Geometry

```cpp
// In src/backprojector.cpp:
// Look for how tilt angles are applied:
// IMOD:  R_y(tilt)  → rotates around Y
// RELION should be same if compatible

// If the rotation matrix is:
//   R_x(tilt)  → rotates around X (tilt axis is X) — NOT IMOD compatible
//   R_y(tilt)  → rotates around Y (tilt axis is Y) — IMOD compatible
```

---

## Transformation: RELION → IMOD

### For Reconstructed Tomograms (RELION 5.0+)

```python
import numpy as np

def relion_tomo_to_imod(vol_relion, relion_version="5.0"):
    """
    Convert RELION reconstructed tomogram to IMOD coordinates.

    For RELION 5.0+, the volume coordinates are directly compatible with IMOD.
    For RELION 4.0, Y↔Z swap may be needed.

    Args:
        vol_relion: 3D numpy array from RELION reconstruction
        relion_version: RELION version string

    Returns:
        vol_imod: 3D numpy array in IMOD coordinates
    """
    if relion_version.startswith("4"):
        # RELION 4.0: potential Y↔Z swap in reconstruction
        vol_imod = np.transpose(vol_relion, (0, 2, 1))
        # Verify this empirically — not all 4.0 builds had this issue
    else:
        # RELION 5.0+: coordinates match IMOD
        vol_imod = vol_relion.copy()

    return vol_imod
```

### For Particle Coordinates (STAR → IMOD)

```python
def relion_star_coords_to_imod(star_coords, tomo_header):
    """
    Convert RELION STAR-format particle coordinates to IMOD pixel coordinates.

    RELION stores coordinates in Angstroms in STAR files.
    IMOD uses pixel coordinates with origin at center.

    Args:
        star_coords: dict with rlnCoordinateX/Y/Z (in Angstroms)
        tomo_header: MRC header dict with nx, ny, nz, cella

    Returns:
        imod_coords: dict with x_pix, y_pix, z_pix (IMOD convention)
    """
    angpix_x = tomo_header['cella']['x'] / tomo_header['nx']
    angpix_y = tomo_header['cella']['y'] / tomo_header['ny']
    angpix_z = tomo_header['cella']['z'] / tomo_header['nz']

    # RELION Angstrom → IMOD pixel (center origin)
    x_pix = star_coords['rlnCoordinateX'] / angpix_x + tomo_header['nx'] / 2
    y_pix = star_coords['rlnCoordinateY'] / angpix_y + tomo_header['ny'] / 2
    z_pix = star_coords['rlnCoordinateZ'] / angpix_z + tomo_header['nz'] / 2

    return {'x': int(x_pix), 'y': int(y_pix), 'z': int(z_pix)}
```

### For Pseudosubtomograms

```python
def relion_pseudosubtomo_to_imod(subtomo_vol, tilt_geometry):
    """
    Convert RELION pseudosubtomogram to IMOD-compatible orientation.

    RELION pseudosubtomograms may have Z → tilt axis, Y → beam,
    while IMOD has Y → tilt axis, Z → beam.

    Args:
        subtomo_vol: 3D subvolume from RELION pseudosubtomo extraction
        tilt_geometry: tilt geometry dict (tilt_axis, beam_direction)

    Returns:
        imod_subtomo: Reoriented 3D subvolume
    """
    # RELION pseudosubtomo: [tilt_axis, beam, other] (Z=tilt, Y=beam)
    # IMOD subtomo:          [X, tilt_axis, beam]      (Z=beam, Y=tilt)

    # Swap Y ↔ Z to bring beam direction to Z and tilt axis to Y
    vol_imod = np.transpose(subtomo_vol, (0, 2, 1))
    return vol_imod
```

---

## Common Coordinate-Related Issues in RELION

| Issue | Symptom | Cause | Fix |
|-------|---------|-------|-----|
| Pseudosubtomo orientation | Subtomograms rotated 90° in YZ plane | RELION uses different orientation convention for pseudosubtomos | Apply Y↔Z transpose |
| Coordinate offset in IMOD | Particles shifted in 3dmod view | Angstrom-to-pixel conversion used wrong origin | Verify angpix and origin from MRC header |
| Wrong handedness in STA | Averaging produces mirrored structure | RELION pseudosubtomo handedness differs from IMOD | Flip X (or Y) axis on pseudosubtomos before averaging |
| Version mismatch 4→5 | Old STAR files incompatible with new RELION | STAR coordinate conventions changed | Upgrade scripts: use `relion_convert_star` |

---

## Version History

| Version | Volume Convention | Pseudsubtomogram Convention | STAR Coordinates |
|---------|------------------|----------------------------|-----------------|
| RELION 3.1-tomo | Followed IMOD (Y=tilt, Z=beam) | Experimental, not standardized | Angstroms, origin=center |
| RELION 4.0 | Some Y↔Z swaps possible | Tilt axis in Z, beam in Y | Angstroms; `rlnOriginX/Y/ZAngst` added |
| RELION 5.0+ | IMOD-compatible | Configurable; defaults improved | Same; documentation clarifies convention |
