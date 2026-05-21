# Source Code Coordinate Patterns

## Overview

This document describes **general patterns** to look for when analyzing the source code of any cryo-ET reconstruction software to determine its coordinate system conventions. These patterns are language-agnostic and cover the most common signals of coordinate handling.

The companion script `scripts/detect_coordinate_system.py` automates the search for these patterns.

---

## Pattern Categories

### 1. Memory Layout Signals

The memory layout of the 3D volume reveals which axis is "fast" (innermost loop) and which is "slow" (outermost loop).

#### C/C++ Pattern (Row-Major)

```c
// Row-major: innermost dimension varies fastest
// float volume[NZ][NY][NX];
for (int z = 0; z < nz; z++)      // Outermost: slowest
    for (int y = 0; y < ny; y++)
        for (int x = 0; x < nx; x++)  // Innermost: fastest
            volume[z][y][x] = ...;
```

This indicates:
- **X is the fast axis** → X maps to MRC `nx`
- **Z is the slow axis** → Z maps to MRC `nz`
- This matches IMOD convention

#### Fortran Pattern (Column-Major)

```fortran
! Column-major: first index varies fastest
! real :: volume(nx, ny, nz)
do iz = 1, nz                 ! Outermost
    do iy = 1, ny
        do ix = 1, nx         ! Innermost: fastest
            volume(ix, iy, iz) = ...
        end do
    end do
end do
```

#### CUDA Pattern

```cuda
// CUDA 3D grid: x-dim is innermost (threadIdx.x)
// dim3 block(BX, BY, BZ), grid(GX, GY, GZ)
int ix = blockIdx.x * blockDim.x + threadIdx.x;  // Fast → ?
int iy = blockIdx.y * blockDim.y + threadIdx.y;  // Medium → ?
int iz = blockIdx.z * blockDim.z + threadIdx.z;  // Slow → ?
```

**Key question**: Which physical axis (IMOD X, Y, Z) is assigned to `ix`?

#### Detecting Axis Assignment

Look for dimension assignments like:

```c
// These tell you the axis mapping:
int dimX = tomogram.nx;  // IMOD X → logical X
int dimY = tomogram.ny;  // IMOD Y → logical Y
int dimZ = tomogram.nz;  // IMOD Z → logical Z

// GPU memory assignment (in C order):
float *d_volume;
cudaMalloc3D(&pitchedPtr, make_cudaExtent(dimX * sizeof(float), dimY, dimZ));
//                                        ↑ X dimension            ↑ Y    ↑ Z
// If dimX here is IMOD Y, axes are swapped
```

---

### 2. FFT Plan Signals

FFT library calls are a strong indicator of axis ordering because FFT plans bind an N-D transform to specific axis indices.

#### FFTW (C/C++)

```c
// FFTW uses row-major ordering by default:
fftw_plan plan = fftw_plan_dft_3d(
    nz, ny, nx,  // Dimensions: slowest → fastest
    in, out,
    FFTW_FORWARD, FFTW_ESTIMATE
);
```

If the plan is `(nx, ny, nz)` instead of `(nz, ny, nx)`, the axes are likely permuted.

#### cuFFT (CUDA)

```cuda
cufftPlan3d(&plan, nz, ny, nx, CUFFT_R2C);
//                 ↑   ↑   ↑
// Dimension order tells you the axis mapping
```

#### MKL FFT (Fortran)

```fortran
! MKL FFT stores dimensions in Fortran order:
status = DftiCreateDescriptor(desc, DFTI_DOUBLE, DFTI_REAL, 3, [nx, ny, nz])
!                                                                ↑   ↑   ↑
! Fortran order → first dimension is innermost
```

#### Detection Heuristic

| FFT Library | Expected IMOD Order | Swapped Indicator |
|-------------|-------------------|-------------------|
| FFTW (C) | `(nz, ny, nx)` | `(nx, ny, nz)` or `(ny, nz, nx)` |
| cuFFT | `(nz, ny, nx)` | `(nx, ny, nz)` or `(ny, nx, nz)` |
| MKL (Fortran) | `(nx, ny, nz)` | `(ny, nx, nz)` or `(nz, ny, nx)` |

---

### 3. Rotation / Projection Geometry Signals

The rotation matrix used in back-projection reveals both the tilt axis identity and the sign conventions.

#### Identifying the Tilt Axis

```c
// Rotation around Y (tilt axis = Y) — IMOD convention:
Matrix3x3 R_y(double alpha) {
    return {
        cos(alpha),  0, sin(alpha),
        0,           1, 0,
        -sin(alpha), 0, cos(alpha)
    };
}

// Rotation around X (tilt axis = X) — NOT IMOD:
Matrix3x3 R_x(double alpha) {
    return {
        1, 0,           0,
        0, cos(alpha), -sin(alpha),
        0, sin(alpha),  cos(alpha)
    };
}
```

**If tilt axis is X instead of Y**, the reconstruction axes are swapped vs IMOD.

#### Identifying the Back-Projection Direction

```c
// IMOD convention: back-project along +Z (beam direction)
float proj_x = x + t * sin(tilt);
float proj_z = z + t * cos(tilt);  // Positive Z is beam direction

// Non-IMOD: back-project along -Z
float proj_z = z - t * cos(tilt);  // Negative sign → Z is flipped
```

#### Sign Convention Check

Look for these patterns in the back-projection code:

```python
# Pattern A: IMOD-compatible (positive Z beam)
z_prime = x * sin(tilt) + z * cos(tilt)  # Forward projection
z_3d = z_prime  # + direction is beam

# Pattern B: Flipped Z (graphics convention)
z_prime = x * sin(tilt) - z * cos(tilt)  # Negative Z → flipped
z_3d = z_prime
```

---

### 4. MRC I/O Signals

How the software reads/writes MRC files directly reveals its axis convention.

#### Writing MRC Slices

```c
// IMOD: each slice is an X-Y plane, Z varies between slices
for (int z = 0; z < nz; z++) {
    float *slice = &volume[z * nx * ny];  // Slice: [Z][Y][X]
    mrc_write_slice(fp, slice, z);
}

// Swapped: slices are X-Z planes (Y is depth instead of Z)
for (int y = 0; y < ny; y++) {
    float *slice = &volume[y * nx * nz];  // Slice: [Y][Z][X] — WRONG
    mrc_write_slice(fp, slice, y);
}
```

#### Reading MRC Slices

```c
// IMOD-compatible:
for (int z = 0; z < header.nz; z++) {
    mrc_read_slice(fp, &volume[z * nx * ny], z);
    // volume[z] is an X-Y plane → correct
}
```

#### MRC Header Dimension Assignment

```c
// Search for the lines that set header.nx, header.ny, header.nz:
header.nx = dimX;  // Should be ~image width (⊥ tilt axis)
header.ny = dimY;  // Should be ~image height (tilt axis)
header.nz = dimZ;  // Should be number of sections (depth)

// Warning signs:
header.nx = dimY;  // X and Y swapped
header.nz = dimX;  // Z is actually an in-plane dimension
```

---

### 5. Alignment File I/O Signals

How the software handles `.xf` or similar alignment files indicates its coordinate model.

```c
// IMOD .xf: 6 values per tilt (A, B, C as rotation; D, E, F as translation)
// Application: x' = A*x + B*y + D; y' = C*x + E*y + F

// If the software applies .xf values in a different order or to different axes,
// the coordinate system is different
```

---

### 6. Command-Line Parameter Signals

Sometimes the coordinate convention is exposed in the user interface:

```bash
# Signs of coordinate customization features:
./some_reconstructor --swap-xy       # Explicit X↔Y swap option
./some_reconstructor --flip-z        # Explicit Z flip option
./some_reconstructor --origin CORNER # Origin convention selection
./some_reconstructor --output-order ZYX  # Explicit output ordering
```

These flags indicate the software *can* produce non-IMOD-standard output and the user needs to set them correctly.

---

### 7. Header Comment Signals

Source code comments often document coordinate choices:

```c
// IMOD-style comments:
// "x: perpendicular to tilt axis"
// "y: along tilt axis"
// "z: beam direction"

// Non-IMOD signals:
// "z: tilt axis (for GPU memory alignment)"
// "y: depth direction (for cache efficiency)"
// "We transpose the volume here to match IMOD output"
```

Search for: `"IMOD"`, `"coordinate"`, `"axis"`, `"transpose"`, `"flip"`, `"permute"`, `"tilt axis"`, `"beam direction"` in source comments.

---

## Automated Detection Script

The script `scripts/detect_coordinate_system.py` automates these checks. It produces a JSON report:

```json
{
  "software": "UnknownReconstructor v2.1",
  "patterns_found": {
    "fft_dimension_order": "cufftPlan3d(nz, nx, ny) → X/Y swapped",
    "tilt_axis": "X (rotation matrix is R_x)",
    "backprojection_sign": "positive (IMOD-compatible)",
    "mrc_write_order": "slices are X-Y planes → Z is depth",
    "memory_layout": "CUDA row-major: X=fast (threadIdx.x)",
    "comments": "Found: 'tilt axis along X for coalesced access'"
  },
  "inferred_convention": {
    "x_maps_to": "IMOD_Z",
    "y_maps_to": "IMOD_X",
    "z_maps_to": "IMOD_Y",
    "handedness": "right",
    "transformation": {
      "axes_permutation": [2, 0, 1],
      "flips": [false, false, false]
    }
  },
  "confidence": 0.85
}
```
