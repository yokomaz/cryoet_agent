#!/usr/bin/env python3
"""
Check whether cryo-ET/Cryo-EM data processing tools are installed and
available in the current environment.

Usage:
    python check_tools.py --tools Warp,AreTomo,IMOD
    python check_tools.py --tools IMOD,MotionCor3 --output report.json
    python check_tools.py --all
    python check_tools.py --tools etomo,IMOD --versions
    python check_tools.py --tools Warp,AreTomo --quiet
"""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Tool Database
# ---------------------------------------------------------------------------

@dataclass
class ToolSpec:
    """Specification for a single cryo-ET tool."""
    # Primary name (canonical, case-insensitive match target)
    name: str
    # Aliases the tool may appear as in papers
    aliases: list[str] = field(default_factory=list)
    # Binary names to search in $PATH
    binaries: list[str] = field(default_factory=list)
    # Known installation directories
    known_paths: list[str] = field(default_factory=list)
    # Environment variables that point to the install
    env_vars: list[str] = field(default_factory=list)
    # Python package names to try importing
    python_packages: list[str] = field(default_factory=list)
    # Conda package names
    conda_packages: list[str] = field(default_factory=list)
    # MATLAB-specific: .m files to look for
    matlab_files: list[str] = field(default_factory=list)
    # MATLAB-specific: function names to try in `matlab -batch`
    matlab_functions: list[str] = field(default_factory=list)
    # Docker image names
    docker_images: list[str] = field(default_factory=list)
    # Singularity image patterns
    singularity_patterns: list[str] = field(default_factory=list)
    # Category for grouping
    category: str = "other"
    # Install guide URL
    install_url: str = ""
    # Check is for a full suite: if any binary found, entire suite is "available"
    any_of: bool = True
    # Version command template (None if not versionable)
    version_cmd: Optional[str] = None
    # Command to get version (if different from --version)
    version_flag: str = "--version"
    # Tools this can substitute for (when missing)
    substitutes: list[str] = field(default_factory=list)


# ===================================================================
# Complete tool database
# ===================================================================

TOOL_DATABASE: dict[str, ToolSpec] = {}

def _register(spec: ToolSpec):
    TOOL_DATABASE[spec.name.lower()] = spec
    for alias in spec.aliases:
        TOOL_DATABASE[alias.lower()] = spec

# --- Reconstruction & Alignment ---

_register(ToolSpec(
    name="IMOD",
    aliases=["etomo", "imod"],
    binaries=["etomo", "newstack", "tilt", "3dmod", "tiltxcorr", "clip", "binvol"],
    known_paths=["/usr/local/IMOD/bin", "/opt/IMOD/bin"],
    env_vars=["IMOD_DIR", "IMOD_HOME"],
    any_of=True,
    category="core",
    install_url="https://bio3d.colorado.edu/imod/download.html",
    version_cmd="3dmod -v",
    substitutes=["AreTomo"],
))

_register(ToolSpec(
    name="AreTomo",
    aliases=["aretomo", "are tomo", "are-tomo"],
    binaries=["AreTomo", "aretomo", "AreTomo2"],
    known_paths=["/usr/local/bin", "/opt/aretomo/bin"],
    env_vars=["ARETOMO_HOME"],
    category="reconstruction",
    install_url="https://github.com/czimaging/AreTomo",
    version_cmd="AreTomo",
    substitutes=["IMOD"],
))

_register(ToolSpec(
    name="RELION",
    aliases=["relion", "relion-tomo", "reliontomo", "relion_tomo"],
    binaries=["relion", "relion_refine", "relion_reconstruct", "relion_tomo_reconstruct"],
    known_paths=["/usr/local/relion/bin", "/opt/relion/bin"],
    env_vars=["RELION_HOME", "RELION_DIR"],
    conda_packages=["relion"],
    any_of=True,
    category="reconstruction",
    install_url="https://relion.readthedocs.io/",
    version_cmd="relion_refine --version",
    substitutes=["IMOD", "AreTomo"],
))

_register(ToolSpec(
    name="Warp",
    aliases=["warp", "warptools", "warp tools"],
    binaries=["Warp", "WarpTools", "fs_motion_and_ctf", "warp"],
    known_paths=["/opt/WarpTools/bin", "/opt/Warp/bin"],
    env_vars=["WARP_HOME", "WARP_DIR"],
    any_of=True,
    category="motion_correction",
    install_url="https://warpem.com/warp/",
    substitutes=["MotionCor3"],
))

_register(ToolSpec(
    name="novaCTF",
    aliases=["novactf", "nova ctf", "nova-ctf"],
    binaries=["novaCTF", "novactf"],
    known_paths=["/usr/local/bin", "/opt/novactf"],
    category="ctf",
    install_url="https://github.com/turonova/novaCTF",
    version_cmd="novaCTF",
    substitutes=["IMOD ctffind"],
))

_register(ToolSpec(
    name="emClarity",
    aliases=["emclarity", "em-clarity", "em clarity"],
    binaries=[],
    matlab_files=["emClarity.m", "emClarity_init.m"],
    matlab_functions=["emClarity"],
    known_paths=["/opt/emClarity", "$HOME/emClarity"],
    env_vars=["EMCLARITY_HOME"],
    category="reconstruction",
    install_url="https://github.com/bHimes/emClarity",
    substitutes=["IMOD", "AreTomo"],
))

# --- Motion Correction ---

_register(ToolSpec(
    name="MotionCor3",
    aliases=["motioncor3", "motioncor", "motion cor", "motion correction"],
    binaries=["MotionCor3", "motioncor3", "MotionCor2", "motioncor2"],
    known_paths=["/usr/local/bin", "/opt/MotionCor3/bin"],
    env_vars=["MOTIONCOR3_HOME"],
    category="motion_correction",
    install_url="https://emcore.ucsf.edu/ucsf-software",
    version_cmd="MotionCor3",
    substitutes=["Warp", "IMOD alignframes"],
))

# --- CTF Estimation ---

_register(ToolSpec(
    name="CTFFIND4",
    aliases=["ctffind4", "ctffind", "ctf find", "ctf estimation"],
    binaries=["ctffind", "ctffind4", "ctffind5"],
    known_paths=["/usr/local/bin", "/opt/ctffind/bin"],
    env_vars=["CISTEM_HOME"],
    category="ctf",
    install_url="https://grigoriefflab.umassmed.edu/ctffind4",
    version_cmd="ctffind",
    substitutes=["Gctf", "IMOD ctffind"],
))

_register(ToolSpec(
    name="Gctf",
    aliases=["gctf", "gctf_gui", "gctf gui"],
    binaries=["Gctf", "gctf"],
    known_paths=["/usr/local/bin"],
    env_vars=["GCTF_HOME"],
    category="ctf",
    install_url="https://www.mrc-lmb.cam.ac.uk/kzhang/Gctf/",
    substitutes=["CTFFIND4"],
))

# --- Particle Picking ---

_register(ToolSpec(
    name="crYOLO",
    aliases=["cryolo", "cr-yolo", "cr yolo"],
    binaries=["crYOLO", "cryolo"],
    python_packages=["cryolo"],
    conda_packages=["cryolo"],
    category="particle_picking",
    install_url="https://cryolo.readthedocs.io/",
    version_cmd="cryolo --version",
    substitutes=["Dynamo", "pyTOM"],
))

_register(ToolSpec(
    name="Dynamo",
    aliases=["dynamo", "dynamo catalogue"],
    binaries=[],
    matlab_files=["dynamo.m", "dynamo_catalogue.m"],
    matlab_functions=["dynamo", "dynamo_catalogue"],
    known_paths=["/opt/dynamo", "$HOME/dynamo"],
    env_vars=["DYNAMO_HOME", "DYNAMO_ROOT"],
    category="particle_picking",
    install_url="https://wiki.dynamo.biozentrum.unibas.ch/w/index.php/Downloads",
    substitutes=["pyTOM", "crYOLO"],
))

_register(ToolSpec(
    name="pyTOM",
    aliases=["pytom", "pytom_tm", "py-tom"],
    binaries=["pytom", "pytom_tm"],
    python_packages=["pytom", "pytom_tm", "pytom_volume", "pytom.basic", "pytom.tm"],
    conda_packages=["pytom"],
    category="particle_picking",
    install_url="https://pytom.readthedocs.io/",
    substitutes=["Dynamo", "crYOLO"],
))

_register(ToolSpec(
    name="Topaz",
    aliases=["topaz", "topaz denoise", "topaz pick"],
    binaries=["topaz"],
    python_packages=["topaz", "topaz.denoise", "topaz.picking"],
    conda_packages=["topaz-em"],
    category="particle_picking",
    install_url="https://github.com/tbepler/topaz",
    version_cmd="topaz --version",
    substitutes=["crYOLO"],
))

_register(ToolSpec(
    name="template_matching",
    aliases=["template matching", "pytom template matching"],
    binaries=["pytom_match_template.py"],
    python_packages=["pytom"],
    conda_packages=["pytom"],
    category="particle_picking",
    install_url="https://pytom.readthedocs.io/",
    substitutes=["Dynamo", "RELION template matching"],
))

# --- Denoising ---

_register(ToolSpec(
    name="deepEMhancer",
    aliases=["deepemhancer", "deep emhancer", "deepenhancer", "deep enhancer"],
    binaries=["deepEMhancer"],
    python_packages=["deepemhancer"],
    conda_packages=["deepemhancer"],
    category="denoising",
    install_url="https://github.com/rsanchezgarc/deepEMhancer",
    version_cmd="deepEMhancer --version",
    substitutes=["cryoCARE", "Topaz denoise"],
))

_register(ToolSpec(
    name="cryoCARE",
    aliases=["cryocare", "cryo-care", "cryo care"],
    python_packages=["cryoCARE"],
    conda_packages=["cryocare"],
    category="denoising",
    install_url="https://github.com/juglab/cryoCARE",
    substitutes=["deepEMhancer", "Topaz denoise"],
))

_register(ToolSpec(
    name="IsoNet",
    aliases=["isonet", "iso-net", "iso net"],
    python_packages=["isonet"],
    conda_packages=["isonet"],
    category="denoising",
    install_url="https://github.com/IsoNet-cryoET/IsoNet",
    version_cmd="isonet --version",
    substitutes=[],
))

# --- Subtomogram Averaging ---

_register(ToolSpec(
    name="cryoSPARC",
    aliases=["cryosparc", "cryo-sparc", "cryo sparc"],
    binaries=["cryosparc", "cryosparcm"],
    known_paths=["/opt/cryosparc", "/opt/cryoSPARC"],
    env_vars=["CRYOSPARC_HOME", "CRYOSPARC_ROOT"],
    docker_images=["cryosparc"],
    category="sta",
    install_url="https://cryosparc.com/",
    substitutes=["RELION"],
))

_register(ToolSpec(
    name="RELIONtomo",
    aliases=["relion-tomo", "relion tomo"],
    binaries=["relion_tomo_reconstruct", "relion_tomo_subtomo"],
    known_paths=["/usr/local/relion/bin"],
    env_vars=["RELION_HOME"],
    category="sta",
    install_url="https://relion.readthedocs.io/",
    substitutes=["Dynamo", "emClarity"],
))

# --- ML / Analysis ---

_register(ToolSpec(
    name="cryoDRGN",
    aliases=["cryodrgn", "cryo-drgn", "cryo drgn"],
    binaries=["cryodrgn"],
    python_packages=["cryodrgn"],
    conda_packages=["cryodrgn"],
    category="analysis",
    install_url="https://github.com/zhonge/cryodrgn",
    version_cmd="cryodrgn --version",
    substitutes=[],
))

_register(ToolSpec(
    name="tomoDRGN",
    aliases=["tomodrgn", "tomo-drgn"],
    python_packages=["tomodrgn"],
    conda_packages=["tomodrgn"],
    category="analysis",
    install_url="https://github.com/zhonge/tomodrgn",
    substitutes=[],
))

# --- Core Utilities ---

_register(ToolSpec(
    name="mrcfile",
    aliases=["mrc file", "mrc", "python mrcfile"],
    python_packages=["mrcfile"],
    conda_packages=["mrcfile"],
    category="utility",
    install_url="pip install mrcfile",
    substitutes=[],
))

_register(ToolSpec(
    name="starfile",
    aliases=["star file", "star", "starfile"],
    python_packages=["starfile"],
    conda_packages=["starfile"],
    category="utility",
    install_url="pip install starfile",
    substitutes=[],
))

_register(ToolSpec(
    name="cupy",
    aliases=["cupy", "cu py", "cuda numpy"],
    python_packages=["cupy"],
    conda_packages=["cupy"],
    category="utility",
    install_url="pip install cupy-cuda11x",
    substitutes=[],
))


# ---------------------------------------------------------------------------
# Check Methods
# ---------------------------------------------------------------------------

CheckResult = dict  # {status, method, detail, version}


def _check_path_binary(spec: ToolSpec) -> CheckResult:
    """Check if any of the spec's binaries are in $PATH."""
    for binary in spec.binaries:
        found = shutil.which(binary)
        if found:
            return {
                "status": "available",
                "method": "path_binary",
                "detail": found,
            }
    if spec.binaries:
        return {"status": "missing", "method": "path_binary",
                "detail": f"No binaries ({', '.join(spec.binaries[:3])}) found in $PATH"}
    return {"status": "unknown", "method": "path_binary",
            "detail": "No binary names registered for this tool"}


def _check_known_paths(spec: ToolSpec) -> CheckResult:
    """Check if any of the known install paths exist."""
    for path_str in spec.known_paths:
        path = Path(os.path.expandvars(os.path.expanduser(path_str)))
        if path.exists():
            return {
                "status": "available",
                "method": "known_path",
                "detail": str(path),
            }
    return {"status": "unknown", "method": "known_path",
            "detail": "No known install paths found"}


def _check_env_vars(spec: ToolSpec) -> CheckResult:
    """Check if any of the spec's env vars are set."""
    for var in spec.env_vars:
        val = os.environ.get(var)
        if val:
            return {
                "status": "available",
                "method": "env_var",
                "detail": f"${var}={val}",
            }
    return {"status": "unknown", "method": "env_var",
            "detail": "No environment variables set"}


def _check_python_package(tool_spec: ToolSpec) -> CheckResult:
    """Check if any Python packages can be imported."""
    for pkg in tool_spec.python_packages:
        try:
            found = importlib.util.find_spec(pkg)
        except (ModuleNotFoundError, ValueError, ImportError):
            continue
        if found is not None:
            loc = str(found.origin) if found.origin else "(namespace)"
            return {
                "status": "available",
                "method": "python_package",
                "detail": f"import {pkg} → {loc}",
            }
    return {"status": "unknown", "method": "python_package",
            "detail": "No Python packages found"}


def _check_matlab(tool_spec: ToolSpec) -> CheckResult:
    """Check if MATLAB is available and the tool's .m files exist."""
    if not tool_spec.matlab_files and not tool_spec.matlab_functions:
        return {"status": "unknown", "method": "matlab",
                "detail": "Not a MATLAB-based tool"}

    matlab_bin = shutil.which("matlab")
    if not matlab_bin:
        return {"status": "missing", "method": "matlab",
                "detail": "MATLAB binary not found in $PATH"}

    for mfile in tool_spec.matlab_files:
        for base in [os.environ.get("MATLABPATH", "").split(":"),
                      ["/opt", os.path.expanduser("~")]]:
            for bp in base:
                if not bp:
                    continue
                candidate = Path(bp) / mfile
                if candidate.exists():
                    return {
                        "status": "available",
                        "method": "matlab_file",
                        "detail": str(candidate),
                    }
    return {"status": "unknown", "method": "matlab",
            "detail": f"MATLAB found ({matlab_bin}), but tool files not located"}


def _check_conda(spec: ToolSpec) -> CheckResult:
    """Check conda package availability."""
    conda_bin = shutil.which("conda")
    if not conda_bin:
        return {"status": "unknown", "method": "conda", "detail": "conda not available"}
    try:
        result = subprocess.run(
            ["conda", "list", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {"status": "unknown", "method": "conda",
                    "detail": "conda list failed"}
        installed = json.loads(result.stdout)
        for pkg in spec.conda_packages:
            for entry in installed:
                if entry.get("name", "").lower() == pkg.lower():
                    return {
                        "status": "available",
                        "method": "conda",
                        "detail": f"{entry['name']} {entry.get('version', '?')}",
                    }
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        pass
    return {"status": "unknown", "method": "conda",
            "detail": "conda package not found in environment"}


def _check_docker(spec: ToolSpec) -> CheckResult:
    """Check for Docker images."""
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return {"status": "unknown", "method": "docker",
                "detail": "docker not available"}
    try:
        result = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True, text=True, timeout=10,
        )
        for image in spec.docker_images:
            if image.lower() in result.stdout.lower():
                return {
                    "status": "available",
                    "method": "docker",
                    "detail": f"docker image: {image}",
                }
    except subprocess.TimeoutExpired:
        pass
    return {"status": "unknown", "method": "docker",
            "detail": "docker image not found"}


def _check_singularity(spec: ToolSpec) -> CheckResult:
    """Check for Singularity images."""
    sing_bin = shutil.which("singularity") or shutil.which("apptainer")
    if not sing_bin:
        return {"status": "unknown", "method": "singularity",
                "detail": "singularity/apptainer not available"}
    # Singularity images are usually in specific directories
    for pattern in spec.singularity_patterns:
        path = Path(os.path.expandvars(os.path.expanduser(pattern)))
        if path.exists():
            return {
                "status": "available",
                "method": "singularity",
                "detail": str(path),
            }
    return {"status": "unknown", "method": "singularity",
            "detail": "singularity image not found"}


CHECK_METHODS = [
    _check_path_binary,
    _check_known_paths,
    _check_env_vars,
    _check_python_package,
    _check_matlab,
    _check_conda,
    _check_docker,
    _check_singularity,
]


# ---------------------------------------------------------------------------
# Version detection
# ---------------------------------------------------------------------------

def _get_version(spec: ToolSpec) -> Optional[str]:
    """Attempt to get the tool version."""
    if not spec.version_cmd:
        return None
    binary = spec.version_cmd.split()[0]
    if not shutil.which(binary):
        return None
    try:
        result = subprocess.run(
            f"{spec.version_cmd} {spec.version_flag}",
            shell=True, capture_output=True, text=True, timeout=15,
        )
        out = result.stdout + result.stderr
        # Try to extract a version number pattern
        import re
        match = re.search(r'v?(\d+\.\d+[\.\d+]*[a-z]?)', out, re.IGNORECASE)
        if match:
            return match.group(1)
        return out.strip().split("\n")[0][:80]  # First line, truncated
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Core check logic
# ---------------------------------------------------------------------------

def resolve_tool_name(name: str) -> Optional[ToolSpec]:
    """Resolve a potentially aliased tool name to its canonical spec."""
    key = name.strip().lower()
    # Direct match
    if key in TOOL_DATABASE:
        return TOOL_DATABASE[key]
    # Substring match on aliases
    for spec_name, spec in TOOL_DATABASE.items():
        if key in spec_name or key in [a.lower() for a in spec.aliases]:
            return spec
    return None


def check_tool(name: str, get_version: bool = False) -> CheckResult:
    """
    Check a single tool's availability via all applicable methods.

    Args:
        name: Tool name (can be an alias)
        get_version: Attempt to retrieve version info if available

    Returns:
        Dict with status, method, detail, and optionally version
    """
    spec = resolve_tool_name(name)
    if spec is None:
        return {
            "status": "unknown",
            "method": None,
            "detail": f"Tool '{name}' not in database — cannot check",
            "spec_name": name,
        }

    result = {"spec_name": spec.name, "status": "missing",
              "method": None, "detail": "No check method succeeded"}

    for method_fn in CHECK_METHODS:
        partial = method_fn(spec)
        if partial["status"] == "available":
            result.update(partial)
            break
        # Accumulate missing info
        if partial["status"] == "missing":
            if result["status"] != "available":
                result["detail"] = partial.get("detail", result["detail"])

    # Collect alternative installation methods
    hints = []
    if not spec.binaries and spec.python_packages:
        hints.append(f"pip install {' '.join(spec.python_packages)}")
    if spec.install_url:
        hints.append(spec.install_url)

    if hints:
        result["suggested_install"] = "; ".join(hints)

    if spec.substitutes:
        result["substitutes"] = spec.substitutes

    if get_version and result["status"] == "available":
        version = _get_version(spec)
        if version:
            result["version"] = version

    return result


def check_tools(tool_names: list[str], get_versions: bool = False) -> dict:
    """
    Check multiple tools and generate a full report.

    Args:
        tool_names: List of tool name strings
        get_versions: Attempt version detection

    Returns:
        Full report dict
    """
    results = {}
    for name in tool_names:
        results[name] = check_tool(name, get_version=get_versions)

    statuses = [r["status"] for r in results.values()]
    available_count = statuses.count("available")
    missing_count = statuses.count("missing")
    unknown_count = statuses.count("unknown")

    return {
        "tools": results,
        "summary": {
            "total": len(tool_names),
            "available": available_count,
            "missing": missing_count,
            "unknown": unknown_count,
        },
        "missing_tools": [name for name, r in results.items()
                          if r["status"] == "missing"],
        "unknown_tools": [name for name, r in results.items()
                          if r["status"] == "unknown"],
        "action_required": _action_message(available_count, missing_count, unknown_count),
    }


def _action_message(avail: int, miss: int, unk: int) -> str:
    parts = []
    if miss:
        parts.append(f"{miss} tool(s) missing — need installation or alternatives")
    if unk:
        parts.append(f"{unk} tool(s) unrecognized — manual check needed")
    if not miss and not unk:
        return "All tools available — follow paper workflow directly"
    return "; ".join(parts)


def check_all(get_versions: bool = False) -> dict:
    """Check all tools in the database — a full system audit."""
    canonical_names = sorted(set(
        k for k, v in TOOL_DATABASE.items()
        if v.name.lower() == k  # Only canonical names, skip aliases
    ))
    return check_tools(canonical_names, get_versions=get_versions)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Check cryo-ET tool availability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --tools Warp,AreTomo,IMOD,MotionCor3
  %(prog)s --tools imod,Dynamo --versions
  %(prog)s --all --output system_audit.json
  %(prog)s --tools AreTomo --quiet
  %(prog)s --list          # List all known tools
        """,
    )
    parser.add_argument("-t", "--tools",
                        help="Comma-separated list of tool names to check")
    parser.add_argument("-a", "--all", action="store_true",
                        help="Check ALL known tools (system audit)")
    parser.add_argument("-o", "--output",
                        help="Save JSON report to file")
    parser.add_argument("-v", "--versions", action="store_true",
                        help="Attempt version detection (slower)")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Only print missing/unrecognized tools")
    parser.add_argument("--list", action="store_true",
                        help="List all known tools in database and exit")
    parser.add_argument("--category",
                        help="Filter --list or --all by category "
                             "(core, motion_correction, ctf, reconstruction, "
                             "particle_picking, sta, denoising, analysis, utility)")

    args = parser.parse_args()

    # --list mode
    if args.list:
        cats = {}
        for spec in TOOL_DATABASE.values():
            cats.setdefault(spec.category, set()).add(spec.name)
        for cat in sorted(cats):
            if args.category and cat != args.category:
                continue
            print(f"\n[{cat}]")
            for name in sorted(cats[cat]):
                spec = TOOL_DATABASE[name.lower()]
                print(f"  {name}")
                if spec.aliases:
                    print(f"    aliases: {', '.join(spec.aliases)}")
                if spec.binaries:
                    print(f"    binaries: {', '.join(spec.binaries[:5])}"
                          f"{'...' if len(spec.binaries) > 5 else ''}")
                if spec.python_packages:
                    print(f"    python: {', '.join(spec.python_packages)}")
        sys.exit(0)

    # Determine which tools to check
    if args.all:
        canonical = sorted(set(
            k for k, v in TOOL_DATABASE.items() if v.name.lower() == k
        ))
        if args.category:
            canonical = [n for n in canonical
                         if TOOL_DATABASE.get(n, ToolSpec(name="")).category == args.category]
        tool_list = canonical
    elif args.tools:
        tool_list = [t.strip() for t in args.tools.split(",") if t.strip()]
    else:
        parser.print_help()
        sys.exit(1)

    if not tool_list:
        print("No tools specified.", file=sys.stderr)
        sys.exit(1)

    # Run check
    report = check_tools(tool_list, get_versions=args.versions)

    # Output
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        if not args.quiet:
            print(f"Report saved: {args.output}")

    if not args.quiet:
        print(f"\n{'='*55}")
        print("Tool Availability Report")
        print(f"{'='*55}")

        for cat in ["core", "motion_correction", "ctf", "reconstruction",
                     "particle_picking", "sta", "denoising", "analysis", "other"]:
            cat_tools = [(n, r) for n, r in report["tools"].items()
                         if r.get("spec_name") and TOOL_DATABASE.get(
                             r["spec_name"].lower(), ToolSpec(name="")).category == cat]
            if not cat_tools:
                continue
            print(f"\n  [{cat}]")
            for name, result in cat_tools:
                icon = {"available": "✅", "missing": "❌",
                        "unknown": "❓"}.get(result["status"], "❓")
                print(f"    {icon} {result.get('spec_name', name)}"
                      f" — {result['detail']}")
                if result.get("version"):
                    print(f"              version: {result['version']}")
                if result.get("substitutes") and result["status"] == "missing":
                    print(f"              alternatives: {', '.join(result['substitutes'])}")

        print(f"\n{'='*55}")
        print(f"Summary: {report['summary']['available']}/{report['summary']['total']} available")
        print(f"  {report['action_required']}")

    if args.quiet:
        for name in report.get("missing_tools", []) + report.get("unknown_tools", []):
            result = report["tools"][name]
            subs = result.get("substitutes", [])
            subs_str = f" (alternatives: {', '.join(subs)})" if subs else ""
            print(f"MISSING: {name}{subs_str}")
        if not report.get("missing_tools") and not report.get("unknown_tools"):
            print("OK: all tools available")


if __name__ == "__main__":
    main()
