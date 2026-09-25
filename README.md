# Checkmk Intel GPU Monitoring (`cmk_intel_gpu`)

[![Checkmk Version](https://img.shields.io/badge/Checkmk-2.3%20|%202.4%20|%202.5+-blue.svg)](https://checkmk.com)
[![Editions](https://img.shields.io/badge/Edition-Raw%20(CRE)%20|%20Enterprise%20(CEE/CCE)-green.svg)](https://checkmk.com)
[![Platform](https://img.shields.io/badge/Platform-Debian%20|%20Ubuntu%20|%20Proxmox%20VE-orange.svg)](https://www.debian.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A comprehensive, production-ready Checkmk monitoring extension and agent plugin for **Intel Arc GPUs** (A310, A380, A750, A770, Battlemage) and **Intel Integrated GPUs** (Iris Xe, UHD Graphics, Core Ultra / Meteor Lake) on Linux using `intel_gpu_top`.

Optimized for **Proxmox VE (PVE)**, media transcode servers (**Plex**, **Jellyfin**, **Emby**, **ffmpeg**), and compute workloads.

---

## 📸 Highlights & Visualizations

- **Dynamic Hardware Engine Discovery**: Automatically discovers and monitors all exposed engines:
  - `Render/3D` (DirectX/Vulkan/OpenGL, 3D rendering)
  - `Video` (Hardware transcoding: QuickSync, NVDEC/VAAPI, Plex/Jellyfin sessions)
  - `VideoEnhance` (Post-processing, HDR tone mapping, AI scaling)
  - `Blitter` (Memory copy operations)
  - `Compute` (OpenCL, OneAPI, machine learning & AI inference)
- **Active Client Process Tracking**:
  - Live metric of active processes utilizing the GPU.
  - Aggregated summary showing process counts (e.g. `Active client process(es): 2 (2x Plex Transcoder)` or `Active client process(es): 3 (2x Plex, 1x Tdarr)`).
  - Detail/notice view lists individual processes and PIDs (e.g., `Plex Transcoder (PID: 3258677)`).
- **Core Frequency & Power-Saving**:
  - GPU Core Frequency (Actual vs. Requested clock speed in MHz).
  - RC6 Power-Saving State (measures deep sleep state percentage; e.g. 100% idle down to 0% heavy load).
- **Interrupts & Power Draw**:
  - GPU Interrupt Rate (`irqs/s`).
  - GPU & Package Power Consumption (Watts, where supported by kernel RAPL sensors).
- **Perf-O-Meters & Metrics**:
  - Color-coded Perf-O-Meter bars in the service list.
  - Dedicated RRD performance graphs for long-term historical tracking.
- **Universal Auto-Detection**:
  - Automatically identifies whether the Intel GPU is `/dev/dri/card0`, `card1`, or `card2` on each host. No need for separate agent packages!
- **WATO Configuration & Alerting**:
  - Native Checkmk 2.3+ Rulesets API integration.
  - User-configurable Warning / Critical thresholds in the GUI for Engine Utilization, Power draw, and Client Process count.

---

## 📦 What's Included

Two deployment options are provided in this repository:

1. **Official MKP Package** ([`dist/cmk_intel_gpu-1.0.2.mkp`](dist/cmk_intel_gpu-1.0.2.mkp)):
   - Recommended for Checkmk **2.3.0 to 2.5+** (both **Raw Edition** and **Enterprise Edition**).
   - Includes Checkmk agent-based check plugins, WATO GUI rulesets, Perf-O-Meters, metrics definitions, and Agent Bakery integration.
2. **Standalone Local Check Script** ([`check_cmk_intel_gpu.sh`](check_cmk_intel_gpu.sh)):
   - Single, self-contained Bash script.
   - Compatible with **any Checkmk version (1.6 through 2.5+)** without requiring server packages.

---

## 🛠 Prerequisites on Monitored Linux Hosts

The plugin uses `intel_gpu_top` from the official `intel-gpu-tools` package. Install it on your monitored Debian, Ubuntu, or Proxmox VE hosts:

```bash
sudo apt update
sudo apt install -y intel-gpu-tools
```

*Verify the installation:*
```bash
intel_gpu_top -L
```

---

## 🚀 Installation via Checkmk Extension Package (MKP)

### Step 1: Install the Package on Checkmk Server

#### Option A — Via Checkmk Web GUI:
1. In your Checkmk site, go to **Setup** > **Maintenance** > **Extension packages**.
2. Click **Upload package**.
3. Select [`dist/cmk_intel_gpu-1.0.2.mkp`](dist/cmk_intel_gpu-1.0.2.mkp) and confirm upload.
4. The extension will activate immediately.

#### Option B — Via Checkmk CLI (OMD):
```bash
# As the site user (su - <sitename>)
mkp install /path/to/cmk_intel_gpu-1.0.2.mkp
cmk -R
```

---

### Step 2: Deploy the Agent Plugin to Monitored Hosts

#### For Checkmk Enterprise Edition (CEE / CCE / CME) — Agent Bakery:
1. Navigate to **Setup** > **Agents** > **Windows, Linux, Solaris, AIX** > **Agent rules**.
2. Search for **Intel GPU Monitoring (cmk_intel_gpu)**.
3. Create a single rule applied to your Linux / Proxmox hosts:
   - **Execution interval / check frequency**: `60` seconds (runs asynchronously in background).
   - **Target GPU device**: Leave **empty** (automatically detects `card0`, `card1`, etc. on each machine).
   - **Metrics Selection**: Toggle any metrics you wish to collect (Engines, Frequency, RC6, Interrupts, Power, Clients).
4. Click **Bake and sign agents**.
5. The Checkmk Agent Updater will automatically distribute the plugin and configuration to your targets.

#### For Checkmk Raw Edition (CRE) — Manual Deployment:
1. Create the asynchronous plugin directory on your monitored host:
   ```bash
   sudo mkdir -p /usr/lib/check_mk_agent/plugins/60
   ```
2. Copy the agent plugin [`src/agents/plugins/cmk_intel_gpu`](src/agents/plugins/cmk_intel_gpu) to the host:
   ```bash
   sudo cp src/agents/plugins/cmk_intel_gpu /usr/lib/check_mk_agent/plugins/60/cmk_intel_gpu
   sudo chmod +x /usr/lib/check_mk_agent/plugins/60/cmk_intel_gpu
   ```
3. *(Optional)* To customize settings on Raw Edition without Bakery, create `/etc/check_mk/cmk_intel_gpu.cfg`:
   ```bash
   # Target GPU device (empty = auto-detect)
   INTEL_GPU_DEVICE=""
   
   # Disable specific metrics if desired (1=enable, 0=disable)
   REPORT_FREQUENCY=1
   REPORT_INTERRUPTS=1
   ```

---

### Step 3: Run Service Discovery

1. In the Checkmk GUI, open the target host (e.g. `pve-hpc`).
2. Click **Run service discovery** (🔨).
3. Checkmk will detect the services:
   - `Intel GPU Engine Render/3D`
   - `Intel GPU Engine Video`
   - `Intel GPU Engine Blitter`
   - `Intel GPU Engine Compute`
   - `Intel GPU Engine VideoEnhance`
   - `Intel GPU Frequency`
   - `Intel GPU RC6`
   - `Intel GPU Interrupts`
   - `Intel GPU Clients`
4. Click **Accept all** (or **Fix all**) and **Activate changes**.

---

## ⚙️ WATO Threshold Rules (Configuring Alerts)

You can customize Warning and Critical thresholds in the Checkmk GUI under **Setup** > **Service monitoring rules**:

| Rule Name | Target Metric | Defaults / Pre-fills | Description |
| :--- | :--- | :--- | :--- |
| **Intel GPU Engine Utilization** | Engine busy % | **80% / 90%** | Configurable globally, per-host, or per-engine (e.g., set distinct levels for `Video` vs `Render/3D`). |
| **Intel GPU Power Consumption** | GPU Power (Watts) | **65 W / 75 W** | Triggers alerts if the GPU power draw exceeds defined wattage. |
| **Intel GPU Active Clients** | Process Count | Pre-fill: **5 / 10** | Triggers alerts if too many concurrent client processes are utilizing the GPU. |

> [!NOTE]
> Metrics such as **Frequency**, **RC6 sleep state**, and **Interrupt rate** do not have static threshold rules because they fluctuate dynamically as part of normal hardware power management (e.g., RC6 is 100% at idle and 0% under full load).

---

## 📄 Method 2: Standalone Local Check (Legacy / Any Checkmk Version)

If you monitor older Checkmk instances (v1.6 – v2.2) or prefer not to install an MKP package on the server:

1. Create the asynchronous local checks directory on the target host:
   ```bash
   sudo mkdir -p /usr/lib/check_mk_agent/local/60
   ```
2. Copy [`check_cmk_intel_gpu.sh`](check_cmk_intel_gpu.sh) to the host:
   ```bash
   sudo cp check_cmk_intel_gpu.sh /usr/lib/check_mk_agent/local/60/cmk_intel_gpu
   sudo chmod +x /usr/lib/check_mk_agent/local/60/cmk_intel_gpu
   ```
3. Run Service Discovery in Checkmk.

---

## 🔧 Building from Source

To build or rebuild the `.mkp` package:

```bash
python3 build_mkp.py
```

The output package will be generated in `dist/cmk_intel_gpu-<VERSION>.mkp`.

---

## ❓ Troubleshooting

### 1. No output when running `./cmk_intel_gpu`
- Verify `intel_gpu_top` is installed: `which intel_gpu_top`.
- Run `intel_gpu_top -L` to check if an Intel GPU is recognized by the kernel.
- Verify user permissions: `intel_gpu_top` requires access to `/dev/dri/card*` and kernel debugfs counters (run as `root` or ensure `sudo` permissions).

### 2. Missing Power metrics
- Power metrics (Watts) depend on kernel driver support (e.g. RAPL / hwmon interface). Certain motherboard chipsets or virtualized PCIe passthrough setups do not expose power telemetry to `intel_gpu_top`. The check plugin automatically omits power sensors if not reported by the hardware.

### 3. Multiple GPUs on one host
- If a server has both an Intel iGPU and a discrete Intel Arc card, or an ASPEED BMC display adapter, use `intel_gpu_top -L` to identify the device node, then specify `INTEL_GPU_DEVICE="/dev/dri/card1"` in `/etc/check_mk/cmk_intel_gpu.cfg` or via the Bakery rule.

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
