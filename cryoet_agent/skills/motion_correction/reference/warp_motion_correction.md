# WarpTools Motion Correction Reference

## Prerequisites

Before running motion correction, the following preparations must be completed:

### 1. Raw Data
- **Frame Series files**: e.g., `.tif`, `.mrc`, `.eer`, etc.
- **Gain Reference** (optional but recommended): e.g., `gain_ref.mrc`, used for flat-field correction.
- **Defects File** (optional): e.g., `defects.txt`, used for masking bad pixels.

### 2. Settings File
A `.settings` file must be generated using the `create_settings` command. This file is a **mandatory input** that records metadata such as data paths, pixel size, and dose.

**Example command to generate settings:**
```bash
WarpTools create_settings \
  --folder_data <raw_data_dir> \
  --folder_processing <output_dir> \
  --output <name>.settings \
  --extension "*.tif" \
  --angpix <pixel_size> \
  --gain_path <gain_ref.mrc> \
  --gain_flip_y \
  --exposure <e_per_A2> \
  [--eer_ngroups 40] \
  [--bin 1] \
  [--bin_angpix <target_angpix>]
```

**Key parameters:**

| Parameter | Description |
|-----------|-------------|
| `--folder_data` | Directory containing raw frame series |
| `--folder_processing` | Output directory for results (XML, averages, logs) |
| `--output` | Path to the generated `.settings` file |
| `--extension` | File search pattern, e.g., `*.tif`, `*.mrc`, `*.eer` |
| `--angpix` | Unbinned pixel size in Ångström |
| `--gain_path` | Path to gain file, relative to the `--output` directory |
| `--gain_flip_x/y`, `--gain_transpose` | Flip/transpose operations for the gain reference |
| `--exposure` | Total electron dose (e⁻/Å²); negative value means dose per frame |
| `--eer_ngroups` | Number of EER frame groups (required only for EER data) |
| `--bin` / `--bin_angpix` | Fourier-space pre-binning (mutually exclusive) |

## Command 1: fs_motion
**Purpose**: Perform motion correction on a frame series only.

### Usage
```bash
WarpTools fs_motion --settings <path_to.settings> [options]
```

### Parameters
#### Motion parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--range_min` | float | 500 | Minimum resolution in Ångström to consider in fit |
| `--range_max` | float | 10 | Maximum resolution in Ångström to consider in fit |
| `--bfac` | float | -500 | Downweight higher spatial frequencies using a B-factor (Å²) |
| `--grid` | string | (auto) | Motion model grid resolution as `XxYxT`, e.g., `5x5x40`; leave empty for auto |

#### Output control

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--averages` | flag | false | Export aligned averages |
| `--average_halves` | flag | false | Export odd and even frame averages separately (for denoiser training) |
| `--skip_first` | int | 0 | Skip first N frames when exporting averages |
| `--skip_last` | int | 0 | Skip last N frames when exporting averages |

#### Data flow and work distribution

| Parameter | Description |
|-----------|-------------|
| `--settings` | **Required**. Path to the `.settings` file |
| `--input_data` | Override input file list from settings. Supports explicit files, wildcards, or `.txt` lists |
| `--input_processing` | Alternative directory containing pre-processed results |
| `--output_processing` | Alternative directory to save processing results |
| `--input_norawdata` | Ignore raw data and look for XML metadata in the processing directory only |
| `--device_list` | Space-separated list of GPU IDs to use. Default: all GPUs |
| `--perdevice` | Number of worker processes per GPU. Default: 1 |
| `--workers` | List of remote workers as `host:port` pairs |

### Outputs
- `<processing_dir>/<movie_name>.xml`: motion parameters and trajectories
- `<processing_dir>/average/<movie_name>.mrc` (if `--averages`)
- `<processing_dir>/average/<movie_name>_odd.mrc` / `_even.mrc` (if `--average_halves`)
- `<processing_dir>/logs/<movie_name>.log`: per-item processing log
- `<processing_dir>/align_frameseries.settings`: copy of parameters used
- `<processing_dir>/processed_items.json` / `failed_items.json`

---

## Command 2: fs_motion_and_ctf

**Purpose**: Estimate motion and CTF, produce aligned averages, and optionally thumbnails—all in one step.

**Source location**: `WarpTools/Commands/Frameseries/MotionCTFFrameseries.cs`

### Usage
```bash
WarpTools fs_motion_and_ctf --settings <path_to.settings> [options]
```

### Parameters

#### Motion parameters (`m_` prefix)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--m_range_min` | float | 500 | Minimum resolution for motion fit (Å) |
| `--m_range_max` | float | 10 | Maximum resolution for motion fit (Å) |
| `--m_bfac` | float | -500 | B-factor for motion fit (Å²) |
| `--m_grid` | string | (auto) | Motion model grid, e.g., `1x1x3` |

#### CTF parameters (`c_` prefix)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--c_window` | int | 512 | Patch size for CTF estimation in binned pixels |
| `--c_range_min` | float | 30 | Minimum resolution for CTF fit (Å) |
| `--c_range_max` | float | 4 | Maximum resolution for CTF fit (Å) |
| `--c_defocus_min` | float | 0.5 | Minimum defocus value to explore (μm) |
| `--c_defocus_max` | float | 5.0 | Maximum defocus value to explore (μm) |
| `--c_voltage` | int | 300 | Acceleration voltage (kV) |
| `--c_cs` | float | 2.7 | Spherical aberration (mm) |
| `--c_amplitude` | float | 0.07 | Amplitude contrast |
| `--c_fit_phase` | flag | false | Fit phase shift of a phase plate |
| `--c_use_sum` | flag | false | Use motion-corrected average spectrum for CTF estimation. Helps without an energy filter or when signal is low |
| `--c_grid` | string | (auto) | Defocus model grid as `XxYxT`, e.g., `2x2x1` |

#### Output control (`out_` prefix)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--out_averages` | flag | false | Export aligned averages |
| `--out_average_halves` | flag | false | Export odd/even frame half-averages |
| `--out_thumbnails` | int | (none) | Export thumbnails with the specified long-edge size in pixels (must be a positive even number) |
| `--out_skip_first` | int | 0 | Skip first N frames |
| `--out_skip_last` | int | 0 | Skip last N frames |

**Note**: `--out_thumbnails` requires `--out_averages` to be enabled.

#### Data flow and work distribution

Same as `fs_motion` (`--settings`, `--input_data`, `--input_processing`, `--output_processing`, `--device_list`, `--perdevice`, `--workers`).

### Outputs

In addition to all `fs_motion` outputs:
- `<processing_dir>/<movie_name>.xml`: includes CTF parameters
- `<processing_dir>/thumbnail/<movie_name>.jpg` (if `--out_thumbnails`)
- `<processing_dir>/align_and_ctf_frameseries.settings`

---

## Typical Usage Examples

### Example 1: Motion correction only, exporting averages
```bash
WarpTools fs_motion \
  --settings warp_frameseries.settings \
  --grid 5x5x40 \
  --averages \
  --skip_first 2
```

### Example 2: One-step motion and CTF (common for tilt-series preprocessing)
```bash
WarpTools fs_motion_and_ctf \
  --settings warp_frameseries.settings \
  --m_grid 1x1x3 \
  --c_grid 2x2x1 \
  --c_range_max 7 \
  --c_defocus_max 8 \
  --c_use_sum \
  --out_averages \
  --out_average_halves \
  --device_list 0 1 \
  --perdevice 2
```

### Example 3: Override input file list with an explicit text file
```bash
WarpTools fs_motion \
  --settings warp_frameseries.settings \
  --input_data movies.txt \
  --out_averages
```
where `movies.txt` contains one file path per line.

---

## Troubleshooting Quick Reference

| Error / Issue | Likely Cause | Fix |
|---------------|--------------|-----|
| `No devices found or specified` | No GPU detected or wrong `--device_list` | Check CUDA environment, or explicitly use `--device_list 0` |
| `Duplicate file names found` | Recursive search finds identical names in subdirectories | Ensure all filenames are unique, or disable recursive search |
| `Can't export thumbnails without exporting averages` | `--out_thumbnails` set without `--out_averages` | Add `--out_averages` |
| `CTF grid can't be larger than 1 in Z dimension when using movie sums` | `--c_use_sum` conflicts with `--c_grid` Z > 1 | Disable `--c_use_sum` or set Z dimension to 1 |
