#!/usr/bin/env python3
"""Build Checkmk Extension Package (.mkp) for cmk_intel_gpu.

Compatible with Checkmk 2.3 through 2.5+.
Generates an official tar-of-tars MKP containing:
- info (Python dict literal)
- info.json (JSON format)
- cmk_addons_plugins.tar (agent_based, rulesets, graphing, bakery)
- agents.tar (agent plugins)
"""

import io
import json
import os
import pprint
import tarfile

PKG_NAME = "cmk_intel_gpu"
VERSION = "1.0.2"
TITLE = "Intel GPU Monitoring (cmk_intel_gpu)"
AUTHOR = "OPUM-LABS"
DESCRIPTION = (
    "Comprehensive monitoring for Intel Arc GPUs (A310, A380, A750, A770, Battlemage) "
    "and Intel iGPUs using intel_gpu_top. Supports all hardware engines, Core Frequency, "
    "RC6 Sleep State, Interrupt Rate, Power draw, and Active Client Processes (e.g. Plex Transcoder)."
)
MIN_REQUIRED = "2.3.0"
DOWNLOAD_URL = "https://github.com/OPUM-LABS/cmk_intel_gpu"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
DIST_DIR = os.path.join(BASE_DIR, "dist")
OUTPUT_MKP = os.path.join(DIST_DIR, f"{PKG_NAME}-{VERSION}.mkp")

manifest = {
    "name": PKG_NAME,
    "title": TITLE,
    "version": VERSION,
    "version.min_required": MIN_REQUIRED,
    "version.packaged": MIN_REQUIRED,
    "author": AUTHOR,
    "description": DESCRIPTION,
    "download_url": DOWNLOAD_URL,
    "files": {
        "cmk_addons_plugins": [
            "cmk_intel_gpu/agent_based/cmk_intel_gpu.py",
            "cmk_intel_gpu/rulesets/ruleset_cmk_intel_gpu.py",
            "cmk_intel_gpu/graphing/graphing_cmk_intel_gpu.py",
            "cmk_intel_gpu/bakery/bakery_cmk_intel_gpu.py",
            "cmk_intel_gpu/checkman/cmk_intel_gpu_engines",
        ],
        "agents": [
            "plugins/cmk_intel_gpu",
        ],
    },
}


def create_tar_from_dir(base_path: str, subpath: str) -> bytes:
    """Pack files from base_path into an uncompressed tar byte string."""
    buf = io.BytesIO()
    full_path = os.path.join(base_path, subpath)
    with tarfile.open(mode="w", fileobj=buf) as tar:
        for root, _, files in os.walk(full_path):
            for file in sorted(files):
                file_full = os.path.join(root, file)
                rel_path = os.path.relpath(file_full, full_path)
                tar.add(file_full, arcname=rel_path)
    return buf.getvalue()


def build():
    os.makedirs(DIST_DIR, exist_ok=True)

    # 1. Build cmk_addons_plugins.tar
    cmk_addons_dir = os.path.join(SRC_DIR, "cmk_addons", "plugins")
    cmk_addons_tar_bytes = io.BytesIO()
    with tarfile.open(mode="w", fileobj=cmk_addons_tar_bytes) as tar:
        cmk_intel_gpu_dir = os.path.join(cmk_addons_dir, "cmk_intel_gpu")
        for root, _, files in os.walk(cmk_intel_gpu_dir):
            for file in sorted(files):
                file_full = os.path.join(root, file)
                rel_path = os.path.relpath(file_full, cmk_addons_dir)
                tar.add(file_full, arcname=rel_path)

    # 2. Build agents.tar
    agents_dir = os.path.join(SRC_DIR, "agents")
    agents_tar_bytes = io.BytesIO()
    with tarfile.open(mode="w", fileobj=agents_tar_bytes) as tar:
        for root, _, files in os.walk(agents_dir):
            for file in sorted(files):
                file_full = os.path.join(root, file)
                rel_path = os.path.relpath(file_full, agents_dir)
                tar.add(file_full, arcname=rel_path)

    # 3. Create outer tar.gz archive (.mkp)
    info_py_content = pprint.pformat(manifest).encode("utf-8")
    info_json_content = json.dumps(manifest, indent=2).encode("utf-8")

    with tarfile.open(OUTPUT_MKP, mode="w:gz") as mkp:
        # Add info
        info_tarinfo = tarfile.TarInfo(name="info")
        info_tarinfo.size = len(info_py_content)
        mkp.addfile(info_tarinfo, io.BytesIO(info_py_content))

        # Add info.json
        info_json_tarinfo = tarfile.TarInfo(name="info.json")
        info_json_tarinfo.size = len(info_json_content)
        mkp.addfile(info_json_tarinfo, io.BytesIO(info_json_content))

        # Add cmk_addons_plugins.tar
        cmk_bytes = cmk_addons_tar_bytes.getvalue()
        cmk_tarinfo = tarfile.TarInfo(name="cmk_addons_plugins.tar")
        cmk_tarinfo.size = len(cmk_bytes)
        mkp.addfile(cmk_tarinfo, io.BytesIO(cmk_bytes))

        # Add agents.tar
        ag_bytes = agents_tar_bytes.getvalue()
        ag_tarinfo = tarfile.TarInfo(name="agents.tar")
        ag_tarinfo.size = len(ag_bytes)
        mkp.addfile(ag_tarinfo, io.BytesIO(ag_bytes))

    print(f"Successfully generated MKP: {OUTPUT_MKP}")
    print(f"File size: {os.path.getsize(OUTPUT_MKP)} bytes")


if __name__ == "__main__":
    build()
