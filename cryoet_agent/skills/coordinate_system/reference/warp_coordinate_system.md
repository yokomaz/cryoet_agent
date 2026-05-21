# Warp Coordinate System

## Overview

Warp is a real-time processing framework for cryo-EM and cryo-ET that includes integrated tilt series alignment and tomogram reconstruction. Its coordinate system is influenced by its internal rendering engine (based on DirectX/Vulkan-style graphics conventions) and its multi-GPU batch processing architecture.

> **Key difference from IMOD**: Warp typically **inverts the Z-axis** direction relative to IMOD. This stems from how the rendering pipeline handles the depth buffer.

---

## Source Code Analysis Points

Warp is primarily written in **C#** and **CUDA**. The following locations are key:

| Source File (Warp distribution) | What to Look For |
|--------------------------------|-------------------|
| `WarpLib/Reconstruction/Reconstruction.cs` | Volume reconstruction pipeline |
| `WarpLib/Reconstruction/Backprojection.cs` | Back-projection kernel and geometry |
| `WarpLib/ImageFormats/MRC.cs` | MRC header read/write |
| `WarpLib/Processing/GPU/ReconstructionGPU.cu` | CUDA kernel coordinate mapping |
| `WarpLib/Geometry/View.cs` or similar | Camera/projection matrix definitions |

---

## Coordinate Convention

### Volume Coordinate System

Warp's internal coordinate system (from the rendering/graphics convention):

```
Warp Volume:
       Y (up)
       ↑
       │
       │
       └──────────────→ X (right)
      /
     /
    ↙
   Z (depth, into screen)
```

| Warp Axis | IMOD Equivalent | Notes |
|-----------|----------------|-------|
| **X** | **X** | Maps directly — perpendicular to tilt axis |
| **Y** | **Y** | Maps directly — tilt axis |
| **Z** | **-Z** | **Inverted** — Warp uses "depth into screen" convention |

### Why Z is Flipped

Warp's reconstruction uses a **graphics-style projection model** where:

1. The 3D volume is rendered from the perspective of the electron beam
2. The camera looks along the **negative Z direction** (standard in graphics APIs like OpenGL/DirectX)
3. Tilt angles rotate the camera/projection matrix, not the volume
4. As a result, the "depth" axis points **opposite** to IMOD's beam-direction Z

In code:

```csharp
// WarpLib/Geometry/CameraMatrix.cs (conceptual):
Matrix4x4 viewMatrix = Matrix4x4.CreateLookAt(
    cameraPosition,                // Electron source position
    targetPosition,                // Center of volume
    Vector3.UnitY                  // Up vector (tilt axis)
);

// This creates a view matrix looking along -Z (graphics convention)
// IMOD's equivalent would look along +Z (beam direction)
```

### Reconstruction Geometry

Warp applies tilt rotations to the **projection matrix**, not the volume:

```
Projection at tilt angle α:
    P_α = K * [R(α) | t]

Where:
    R(α) rotates around Y axis (tilt axis)
    K is the projection matrix (orthographic for cryo-ET)
    t is the translation (alignment)

Because the view matrix looks along -Z:
    A positive tilt in Warp produces a rotation in the opposite sense
    of IMOD's positive tilt direction
```

---

## Detecting Z-Flip from Source Code

### Pattern 1: LookAt / View Matrix

```csharp
// Search for CreateLookAt, CreatePerspective, or similar:
var view = Matrix.LookAtLH(origin, target, up);
// "LH" (Left-Handed) → Z likely flipped vs IMOD (Right-Handed)
// "RH" (Right-Handed) → Same as IMOD

var view = Matrix.LookAtRH(origin, target, up);
// Right-Handed → Z convention matches IMOD
```

### Pattern 2: Back-Projection CUDA Kernel

```cuda
// In Warp's backprojection CUDA kernel:
// Look for the 3D coordinate computation:
float z_world = z_section * voxel_size_z;
float x_world = x_voxel * voxel_size_x;
float y_world = y_voxel * voxel_size_y;

// If the ray direction is computed as:
float3 ray_dir = make_float3(
    sin(tilt_angle) * cos(rotation),   // X component
    sin(rotation),                      // Y component
    -cos(tilt_angle) * cos(rotation)   // Z component ← NEGATIVE!
);
// The negative Z component indicates a flipped Z axis
```

### Pattern 3: MRC Write Order

```csharp
// In WarpLib/ImageFormats/MRC.cs:
// Look for the slice writing loop:
for (int z = 0; z < dimZ; z++) {
    // If WriteSlice starts from dimZ-1 and goes to 0, or
    // if data[z] is written as data[dimZ - 1 - z],
    // this confirms the Z flip
}
```

---

## Transformation: Warp → IMOD

```python
import numpy as np

def warp_to_imod(vol_warp):
    """
    Convert Warp volume to IMOD coordinate system.

    Warp uses a left-handed Z (depth into screen).
    IMOD uses a right-handed Z (beam direction).

    Args:
        vol_warp: 3D numpy array from Warp reconstruction

    Returns:
        vol_imod: 3D numpy array in IMOD coordinates
    """
    # Step 1: Flip Z axis
    vol_imod = np.flip(vol_warp, axis=0)
    # axis=0 because MRC stores sections in the first dimension

    # Step 2: X and Y map directly — no transformation needed
    # (Verify this: in some Warp versions, X may also need attention)

    return vol_imod
```

### Full Transformation Including Metadata

```python
def warp_to_imod_with_metadata(input_path, output_path):
    """
    Convert Warp .mrc to IMOD coordinates, updating header.
    """
    import mrcfile
    import numpy as np

    with mrcfile.open(input_path, mode='r', permissive=True) as mrc:
        vol = mrc.data.copy()
        header = mrc.header

    # Flip Z
    vol = np.flip(vol, axis=0)

    # Write with updated header
    with mrcfile.new(output_path, overwrite=True) as mrc:
        mrc.set_data(vol.astype(np.float32))
        mrc.header.cella = header.cella
        # Origin may need adjustment after flip
        # If origin.z was set by Warp, it needs to be negated
        # (handled by the origin field in MRC 2014 extension)
```

---

## Subvolume / Sub-tomogram Considerations

Warp often processes tilt series in subvolumes. When converting:

| Artifact | Cause | Fix |
|----------|-------|-----|
| Subvolume Z shift | Each subvolume's Z is flipped independently | Concatenate subvolumes first, then flip Z globally |
| Edge artifacts at subvolume boundaries | Z-flip inverts the subvolume stacking order | Process the full volume as one MRC before flipping |
| Negative Z translations in .xf | Warp's alignment stores offsets in its own coordinate system | Negate Z component of translations when converting |

---

## Version-Specific Notes

| Version | Z Convention | X/Y Convention | Notes |
|---------|-------------|----------------|-------|
| 1.0.6 – 1.0.8 | Z flipped | Direct | Standard case |
| 1.0.9+ | Z flipped | Direct | Minor improvements in subvolume handling |
| 2.x (M/WarpTools) | Verify | Direct | May have changed rendering backend |

---

## Quick Validation Test

To check if a Warp volume needs transformation:

```python
import numpy as np
import mrcfile

# Load Warp and IMOD reconstructions of the same dataset
with mrcfile.open('warp_tomo.mrc') as f: warp_vol = f.data
with mrcfile.open('imod_tomo.mrc') as f: imod_vol = f.data

# Try flipping Z and correlate
flipped = np.flip(warp_vol, axis=0)
from scipy.signal import correlate
corr = correlate(imod_vol.ravel(), flipped.ravel())
print(f"Correlation with Z-flip: {corr.max()}")

# If correlation is significantly higher with flip, Z is confirmed flipped
```
