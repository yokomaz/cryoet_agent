# AreTomo Coordinate System

## Overview

AreTomo (Accelerated Reconstruction and Alignment for Electron Tomography) is a GPU-accelerated tool for tilt series alignment and tomogram reconstruction. Its coordinate system is influenced by GPU memory layout optimization, particularly the use of **cuFFT** and custom CUDA kernels.

> **Critical**: AreTomo's coordinate conventions can vary between major versions. Always verify the specific version you are using. This document primarily covers AreTomo ≥ 1.3.x.

---

## Source Code Analysis Points

The following source locations are key to understanding AreTomo's coordinate system:

| Source File (v1.3+) | What to Look For |
|---------------------|-----------------|
| `core/aretomo.cu` | Main reconstruction loop; array dimension assignment |
| `Aln/AlnAP.cpp` | Alignment module; rotation convention |
| `Rec/RecAP.cu` | GPU back-projection kernel; coordinate mapping |
| `common/volume_io.cu` | MRC read/write; axis-to-dimension mapping |
| `common/transformations.cu` | Rotation matrix generation from alignment parameters |

---

## Coordinate Convention (Typical for AreTomo ≥ 1.3)

### Memory Layout on GPU

AreTomo uses a **3D CUDA array** with the following layout (in CUDA terms):

```
cudaPitchedPtr / cudaArray:
  Width  (x dimension in CUDA) → IMOD Y (tilt axis)
  Height (y dimension in CUDA) → IMOD X (perpendicular to tilt axis)
  Depth  (z dimension in CUDA) → IMOD Z (beam / sections)
```

This means in the GPU kernel:

```cuda
// In AreTomo's CUDA kernel:
int idx = blockIdx.x * blockDim.x + threadIdx.x;  // Fast → IMOD Y
int idy = blockIdx.y * blockDim.y + threadIdx.y;  // Medium → IMOD X
int idz = blockIdx.z * blockDim.z + threadIdx.z;  // Slow → IMOD Z

// Access: volume[idz * pitch + idy * width + idx]
//     or: volume[idz][idy][idx] in logical terms
```

### Axis Mapping to IMOD

| AreTomo Internal | CUDA Dimension | IMOD Axis | Notes |
|-----------------|----------------|-----------|-------|
| `iX` (fast index) | Width | **Y** (tilt axis) | GPU X-thread maps to IMOD Y |
| `iY` (medium index) | Height | **X** (⊥ tilt) | GPU Y-thread maps to IMOD X |
| `iZ` (slow index) | Depth | **Z** (sections) | GPU Z-thread maps to IMOD Z |

> **This means the X and Y axes are swapped relative to IMOD in GPU memory.** However, the exact mapping depends on how `CudaFFT` is configured and which version of the code.

### Reconstruction Geometry

AreTomo's back-projection kernel uses a rotation model that is equivalent to IMOD's:

```
Rotation around the tilt axis (IMOD Y) by tilt angle α:

In AreTomo's coordinate frame (swapped X↔Y from IMOD):
  Rotation is around AreTomo's X-axis (which is IMOD Y)
```

The actual rotation matrix applied:

```
R_Aretomo(α) for back-projection:
    [ 1     0        0    ]   (AreTomo X / IMOD Y = tilt axis, invariant)
    [ 0   cos(α)  -sin(α) ]   (AreTomo Y / IMOD X)
    [ 0   sin(α)   cos(α) ]   (AreTomo Z / IMOD Z)
```

### Alignment Input

AreTomo accepts IMOD-style `.xf` alignment files, and internally converts to its own representation:

```cpp
// From Aln/ReadAlnFile.cpp (conceptual):
// IMOD .xf provides: (A, B, X_offset, C, D, Y_offset)
// AreTomo converts these to its internal rotation+translation model
// The conversion respects the X↔Y axis swap
```

---

## Detecting Axis Conventions from AreTomo Source Code

### Pattern 1: FFT Plan Creation

```cuda
// In Rec/RecAP.cu or similar:
cufftPlan3d(&plan, nz, ny, nx, CUFFT_R2C);
//                    ↑   ↑   ↑
// If nx = IMOD_NY, this confirms X↔Y swap
```

If the FFT plan dimensions are `(NZ, NX_recon, NY_recon)` instead of `(NZ, NY_recon, NX_recon)`, the X↔Y swap is confirmed.

### Pattern 2: Volume Iteration Order

```cuda
// Look for triply-nested loops:
for (iz = 0; iz < nz; iz++)      // Outermost: Z sections
    for (iy = 0; iy < ny; iy++)   // Middle
        for (ix = 0; ix < nx; ix++)  // Innermost (fast)
```

If the innermost loop iterates over `ny` (tilt axis dimension) rather than `nx`, the axes are swapped.

### Pattern 3: MRC Write Function

```c
// In common/mrcio.cpp or volume_io.cu:
// Look for the argument order when writing MRC slices:
for (z = 0; z < mrcHeader.nz; z++) {
    // The slicing direction: which axis is extracted per section?
    mrc_write_slice(&volume[z * nx * ny], ...);  // Z = depth
    // If data layout is [Z][X][Y] (IMOD X, IMOD Y swapped),
    // the slice writing will be: &volume[z * NX_imod * NY_imod]
}
```

### Pattern 4: Header Dimension Mapping

```c
// In the MRC header setup:
header.nx = dimX_recon;  // IMOD X?
header.ny = dimY_recon;  // IMOD Y?
header.nz = dimZ_recon;  // IMOD Z?

// Check if AreTomo sets:
// header.nx = CropSizeX (which might actually be IMOD Y dimension)
// header.ny = CropSizeY (which might actually be IMOD X dimension)
```

---

## Transformation: AreTomo → IMOD

### Known Transformation (AreTomo ≥ 1.3, Standard Build)

```python
import numpy as np
from scipy.ndimage import affine_transform

def aretomo_to_imod(vol_aretomo, header_aretomo=None):
    """
    Convert AreTomo volume to IMOD coordinate system.

    Args:
        vol_aretomo: 3D numpy array from AreTomo (shape: [NZ, NX_imod, NY_imod])
        header_aretomo: MRC header dict (optional, for metadata update)

    Returns:
        vol_imod: 3D numpy array in IMOD coordinates
    """
    # Step 1: Swap X↔Y (AreTomo's fast axis is IMOD Y)
    # AreTomo memory: [Z, X_imod, Y_imod] → swap to IMOD [Z, Y_imod, X_imod]
    vol_imod = np.transpose(vol_aretomo, (0, 2, 1))

    # Step 2: Check Z direction (may need flip in some versions)
    # If images appear "upside down", uncomment:
    # vol_imod = np.flip(vol_imod, axis=0)

    # Step 3: Correct origin
    # AreTomo sets origin to center; verify this matches IMOD convention
    # If not, apply shift

    return vol_imod
```

### Version-Specific Notes

| Version | X↔Y Swap? | Z Flip? | Origin Behavior |
|---------|-----------|---------|-----------------|
| 1.3.4 | Yes | No (tested) | Center of volume |
| 1.4.x | Check FFT plan | Check MRC header | May change |
| 2.0+ | Changed (reworked GPU memory) | No | Center |

> **Always verify with `scripts/validate_coordinate_system.py` for your specific version.**

---

## Common Issues

| Issue | Symptom | Check |
|-------|---------|-------|
| X↔Y not swapped | Particles appear in wrong X/Y positions | Verify GPU kernel dimension mapping |
| Z-axis inversion | Tomogram appears mirrored in depth | Check sign of back-projection direction |
| Wrong origin | Subtomograms shifted by N/2 | Compare MRC origin fields between AreTomo and IMOD output |
| pitch/padding issues | Striped artifacts after transformation | Check `CudaPitchedPtr` row pitch vs logical dimensions |
