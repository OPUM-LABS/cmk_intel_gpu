#!/usr/bin/env bash
# ==============================================================================
# Checkmk Local Check: Intel Arc GPU Monitoring (cmk_intel_gpu)
# ==============================================================================
# Compatible with: Debian 11 (Bullseye), Debian 12 (Bookworm), Ubuntu, Proxmox
# Prerequisites: intel-gpu-tools (apt install intel-gpu-tools)
# Recommended:   python3 (base system) or jq (apt install jq)
#
# Checkmk Installation:
#   Save to: /usr/lib/check_mk_agent/local/60/cmk_intel_gpu
#   Make executable: chmod +x /usr/lib/check_mk_agent/local/60/cmk_intel_gpu
#   (Using the '60' subfolder runs the script asynchronously every 60s,
#    preventing agent latency while sampling the GPU)
# ==============================================================================

set -u

# --- CONFIGURATION -----------------------------------------------------------
# Device to monitor. Leave empty ("") for automatic detection (recommended),
# or specify a path such as "/dev/dri/card1" or "/dev/dri/card0".
DEVICE="${INTEL_GPU_DEVICE:-}"

# Checkmk Service Name Prefix
SERVICE_PREFIX="${INTEL_GPU_PREFIX:-Intel GPU Arc}"

# Sampling settings
# SAMPLE_MS: sampling duration per sample in milliseconds (1000 = 1 sec)
# SAMPLE_DURATION: total seconds to sample via timeout (2.5s yields 2 full samples)
SAMPLE_MS="${INTEL_GPU_SAMPLE_MS:-1000}"
SAMPLE_DURATION="${INTEL_GPU_SAMPLE_DURATION:-2.5}"

# Warning and Critical thresholds for engine utilization in %
WARN_BUSY="${INTEL_GPU_WARN:-80}"
CRIT_BUSY="${INTEL_GPU_CRIT:-90}"

# What to report (1 = enable, 0 = disable)
REPORT_SEPARATE_ENGINES=1  # Dedicated service for each engine (Render/3D, Video, etc.)
REPORT_SUMMARY_ENGINE=1   # Consolidated service with all engines in one metric list
REPORT_FREQUENCY=1        # Actual & requested frequency (MHz)
REPORT_RC6=1              # RC6 power saving sleep state (%)
REPORT_INTERRUPTS=1       # Interrupt rate (irq/s)
REPORT_POWER=1            # GPU / Package power draw in Watts (if supported by kernel)
REPORT_CLIENTS=1          # Active processes using the GPU (e.g. Plex Transcoder)
REPORT_CLIENT_DETAILS=0   # Include process names & PIDs in multi-line details (1=yes, 0=no)
# -----------------------------------------------------------------------------

# Check if intel_gpu_top binary is available
if ! command -v intel_gpu_top >/dev/null 2>&1; then
    echo "2 \"${SERVICE_PREFIX}\" - CRIT: 'intel_gpu_top' binary not found. Install it via 'apt install intel-gpu-tools'."
    exit 0
fi

# Detect parser: prefer python3, fallback to jq
PARSER=""
if command -v python3 >/dev/null 2>&1; then
    PARSER="python3"
elif command -v jq >/dev/null 2>&1; then
    PARSER="jq"
else
    echo "3 \"${SERVICE_PREFIX}\" - UNKNOWN: Neither 'python3' nor 'jq' found. Please install python3 or jq (apt install jq)."
    exit 0
fi

# Check permissions: if not root and sudo is available, use sudo
CMD_PREFIX=""
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
        CMD_PREFIX="sudo -n"
    fi
fi

# Normalize DEVICE filter for intel_gpu_top (-d drm:/dev/dri/cardX)
normalize_device() {
    local dev="$1"
    if [ -z "$dev" ]; then
        echo ""
        return
    fi
    if [[ "$dev" == drm:* ]] || [[ "$dev" == sys:* ]] || [[ "$dev" == pci:* ]]; then
        echo "$dev"
    elif [[ "$dev" == /dev/dri/* ]]; then
        echo "drm:$dev"
    elif [[ "$dev" == card* ]]; then
        echo "drm:/dev/dri/$dev"
    else
        echo "drm:/dev/dri/$dev"
    fi
}

DEVICE_ARG=$(normalize_device "${DEVICE}")

# If DEVICE was not explicitly provided by environment and default /dev/dri/card1 does not exist,
# fall back to /dev/dri/card0 if present, or let intel_gpu_top auto-detect
if [ -z "${INTEL_GPU_DEVICE:-}" ] && [ ! -e "/dev/dri/card1" ]; then
    if [ -e "/dev/dri/card0" ]; then
        DEVICE_ARG="drm:/dev/dri/card0"
    else
        DEVICE_ARG=""
    fi
fi

# Build intel_gpu_top arguments (no -n flag because Debian package lacks it)
ARGS=(-J -s "${SAMPLE_MS}")
if [ -n "${DEVICE_ARG}" ]; then
    ARGS+=(-d "${DEVICE_ARG}")
fi

# Timeout wrapper: send SIGINT after SAMPLE_DURATION to let intel_gpu_top gracefully flush JSON array
TIMEOUT_CMD=""
if command -v timeout >/dev/null 2>&1; then
    TIMEOUT_CMD="timeout -k 1s -s INT ${SAMPLE_DURATION}s"
fi

# Locate hwmon sensors for Intel GPU (used for discrete Arc power calculation)
find_hwmon_dir() {
    local target_dev="${1:-}"
    if [ -n "$target_dev" ]; then
        local cname
        cname=$(basename "$target_dev")
        for h in /sys/class/drm/"$cname"/device/hwmon/hwmon*; do
            [ -d "$h" ] && echo "$h" && return
        done
    fi
    for h in /sys/class/drm/card*/device/hwmon/hwmon*; do
        if [ -d "$h" ] && [ -r "$h/name" ]; then
            local dname
            dname=$(cat "$h/name" 2>/dev/null)
            if [ "$dname" = "i915" ] || [ "$dname" = "xe" ]; then
                echo "$h"
                return
            fi
        fi
    done
    for h in /sys/class/hwmon/hwmon*; do
        if [ -d "$h" ] && [ -r "$h/name" ]; then
            local dname
            dname=$(cat "$h/name" 2>/dev/null)
            if [ "$dname" = "i915" ] || [ "$dname" = "xe" ]; then
                echo "$h"
                return
            fi
        fi
    done
}

HWMON_DIR=$(find_hwmon_dir "${DEVICE}")
ENERGY_FILE=""
if [ -n "$HWMON_DIR" ] && [ -r "$HWMON_DIR/energy1_input" ]; then
    ENERGY_FILE="$HWMON_DIR/energy1_input"
fi

E1=""
T1=""
if [ -n "$ENERGY_FILE" ]; then
    E1=$(cat "$ENERGY_FILE" 2>/dev/null)
    T1=$(date +%s%N 2>/dev/null)
fi

# Execute intel_gpu_top and capture both stdout and stderr
TEMP_ERR=$(mktemp 2>/dev/null || echo "/tmp/intel_gpu_top_err.$$")
RAW_JSON=$(${TIMEOUT_CMD} ${CMD_PREFIX} intel_gpu_top "${ARGS[@]}" 2>"${TEMP_ERR}")
EXIT_CODE=$?
STDERR_OUTPUT=$(cat "${TEMP_ERR}" 2>/dev/null)
rm -f "${TEMP_ERR}"

# Auto-recovery: if a specific device argument failed, fallback to automatic detection
if [ -z "${RAW_JSON}" ] && [ -n "${DEVICE_ARG}" ]; then
    TEMP_ERR=$(mktemp 2>/dev/null || echo "/tmp/intel_gpu_top_err.$$")
    RAW_JSON=$(${TIMEOUT_CMD} ${CMD_PREFIX} intel_gpu_top -J -s "${SAMPLE_MS}" 2>"${TEMP_ERR}")
    EXIT_CODE=$?
    STDERR_OUTPUT=$(cat "${TEMP_ERR}" 2>/dev/null)
    rm -f "${TEMP_ERR}"
fi

# Calculate power from hwmon energy delta or power1_average
HWMON_W=""
if [ -n "$E1" ] && [ -n "$T1" ] && [ -n "$ENERGY_FILE" ]; then
    E2=$(cat "$ENERGY_FILE" 2>/dev/null)
    T2=$(date +%s%N 2>/dev/null)
    if [ -n "$E2" ] && [ -n "$T2" ]; then
        HWMON_W=$(awk -v e1="$E1" -v e2="$E2" -v t1="$T1" -v t2="$T2" 'BEGIN {
            de = e2 - e1
            dt = (t2 - t1) / 1000000000.0
            if (dt > 0.1 && de >= 0) {
                watts = (de / 1000000.0) / dt
                if (watts >= 0 && watts <= 600) {
                    printf "%.1f", watts
                }
            }
        }' 2>/dev/null)
    fi
fi

if [ -z "$HWMON_W" ] && [ -n "$HWMON_DIR" ] && [ -r "$HWMON_DIR/power1_average" ]; then
    PA=$(cat "$HWMON_DIR/power1_average" 2>/dev/null)
    if [ -n "$PA" ] && [ "$PA" -gt 0 ] 2>/dev/null; then
        HWMON_W=$(awk -v p="$PA" 'BEGIN { printf "%.1f", p / 1000000.0 }' 2>/dev/null)
    fi
fi

# Handle empty output or execution failure
if [ -z "${RAW_JSON}" ]; then
    err_msg=$(echo "${STDERR_OUTPUT}" | head -n 2 | tr '\n' ' ')
    if [ -n "${err_msg}" ]; then
        echo "2 \"${SERVICE_PREFIX}\" - CRIT: intel_gpu_top failed: ${err_msg} (target device: ${DEVICE_ARG:-auto})."
    else
        echo "2 \"${SERVICE_PREFIX}\" - CRIT: intel_gpu_top returned no data (exit code ${EXIT_CODE}). Check permissions (root required)."
    fi
    exit 0
fi

# Validate that stdout actually contains JSON curly braces '{'
# (Prevents wrapping plain error text into brackets which causes cryptic JSONDecodeError)
if ! [[ "${RAW_JSON}" =~ \{ ]]; then
    combined_err="${RAW_JSON} ${STDERR_OUTPUT}"
    combined_err=$(echo "${combined_err}" | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g' | sed 's/^ //;s/ $//')
    [ -z "${combined_err}" ] && combined_err="No JSON object produced by intel_gpu_top"
    echo "2 \"${SERVICE_PREFIX}\" - CRIT: intel_gpu_top error: ${combined_err} (target device: ${DEVICE_ARG:-auto})."
    exit 0
fi

# Ensure enclosed in brackets [ ... ] if needed
if ! [[ "${RAW_JSON}" =~ ^[[:space:]]*\[ ]]; then
    RAW_JSON="[${RAW_JSON%,}]"
elif ! [[ "${RAW_JSON}" =~ \][[:space:]]*$ ]]; then
    RAW_JSON="${RAW_JSON%,}]"
fi

# -----------------------------------------------------------------------------
# Parser Implementation
# -----------------------------------------------------------------------------
if [ "${PARSER}" = "python3" ]; then
    python3 - <<EOF
import json
import sys

raw = """${RAW_JSON}"""

data = None
try:
    data = json.loads(raw)
except Exception:
    pass

if data is None:
    # Try recovering by locating first '{' and last '}'
    start = raw.find('{')
    end = raw.rfind('}')
    if start != -1 and end != -1:
        chunk = raw[start:end+1].strip()
        try:
            data = json.loads(f"[{chunk}]")
        except Exception:
            last_start = raw.rfind('\n{')
            if last_start != -1:
                try:
                    data = [json.loads(raw[last_start:end+1])]
                except Exception:
                    pass

if data is None or (isinstance(data, list) and len(data) == 0):
    print(f'3 "${SERVICE_PREFIX}" - UNKNOWN: Failed to parse JSON from intel_gpu_top. Target: ${DEVICE_ARG:-auto}')
    sys.exit(0)

# Always pick the last sample (settled data after initial PMU sampling)
sample = data[-1] if isinstance(data, list) and len(data) > 0 else (data if isinstance(data, dict) else {})

prefix = "${SERVICE_PREFIX}"
warn_busy = float("${WARN_BUSY}")
crit_busy = float("${CRIT_BUSY}")

report_separate = bool(${REPORT_SEPARATE_ENGINES})
report_summary = bool(${REPORT_SUMMARY_ENGINE})
report_freq = bool(${REPORT_FREQUENCY})
report_rc6 = bool(${REPORT_RC6})
report_irq = bool(${REPORT_INTERRUPTS})
report_power = bool(${REPORT_POWER})
report_clients = bool(${REPORT_CLIENTS})
report_client_details = bool(${REPORT_CLIENT_DETAILS})

# 1. ENGINES
engines = sample.get("engines", {})
summary_metrics = []
active_engines = []
max_engine_state = 0

for engine_name, engine_data in engines.items():
    try:
        busy = float(engine_data.get("busy", 0.0))
    except (ValueError, TypeError):
        busy = 0.0

    # Determine status
    if busy >= crit_busy:
        st = 2
        st_txt = "CRIT"
    elif busy >= warn_busy:
        st = 1
        st_txt = "WARN"
    else:
        st = 0
        st_txt = "OK"

    if st > max_engine_state:
        max_engine_state = st

    # Metrics sanitized name (no slashes or spaces for perfdata key)
    metric_key = engine_name.replace("/", "_").replace(" ", "_")

    if report_separate:
        perfdata = f"utilization={busy:.2f};{warn_busy:.0f};{crit_busy:.0f};0;100"
        msg = f"Engine utilization: {busy:.2f}%"
        if st == 2:
            msg = f"CRIT - {msg}"
        elif st == 1:
            msg = f"WARN - {msg}"
        print(f'{st} "{prefix} Engine {engine_name}" {perfdata} {msg}')

    summary_metrics.append(f"{metric_key}={busy:.2f};{warn_busy:.0f};{crit_busy:.0f};0;100")
    if busy > 0.0:
        active_engines.append(f"{engine_name}: {busy:.2f}%")

if report_summary and summary_metrics:
    active_str = ", ".join(active_engines) if active_engines else "all engines idle"
    msg = f"Active engines: {active_str}"
    if max_engine_state == 2:
        msg = f"CRIT - {msg}"
    elif max_engine_state == 1:
        msg = f"WARN - {msg}"
    summary_perf = "|".join(summary_metrics)
    print(f'{max_engine_state} "{prefix} Engines Summary" {summary_perf} {msg}')

# 2. FREQUENCY
if report_freq:
    freq = sample.get("frequency", {})
    if freq:
        try:
            act = float(freq.get("actual", 0.0))
            req = float(freq.get("requested", 0.0))
            u = freq.get("unit", "MHz")
            max_f = max(act, req, 2450.0)
            print(f'0 "{prefix} Frequency" actual={act:.0f};;;0;{max_f:.0f}|requested={req:.0f};;;0;{max_f:.0f} Frequency: {act:.0f} {u} (requested: {req:.0f} {u})')
        except (ValueError, TypeError):
            pass

# 3. RC6 (Power Saving Sleep State)
if report_rc6:
    rc6 = sample.get("rc6", {})
    if rc6:
        try:
            val = float(rc6.get("value", 0.0))
            print(f'0 "{prefix} RC6" rc6={val:.1f};;;0;100 RC6 power saving state: {val:.1f}%')
        except (ValueError, TypeError):
            pass

# 4. INTERRUPTS
if report_irq:
    irq = sample.get("interrupts", {})
    if irq:
        try:
            val = float(irq.get("count", 0.0))
            print(f'0 "{prefix} Interrupts" interrupts={val:.1f};;;0; Interrupt rate: {val:.1f} irqs/s')
        except (ValueError, TypeError):
            pass

# 5. POWER CONSUMPTION
if report_power:
    power = sample.get("power", {})
    if not power and "${HWMON_W}":
        try:
            power = {"GPU": float("${HWMON_W}")}
        except ValueError:
            pass
    if power:
        p_perf = []
        p_txt = []
        p_gpu = power.get("GPU")
        p_pkg = power.get("Package")
        if p_gpu is not None:
            try:
                gpu_w = float(p_gpu)
                p_perf.append(f"power_gpu={gpu_w:.2f};65;75;0;75")
                p_txt.append(f"GPU: {gpu_w:.1f} W")
            except (ValueError, TypeError):
                pass
        if p_pkg is not None:
            try:
                pkg_w = float(p_pkg)
                p_perf.append(f"power_package={pkg_w:.2f};;;0;")
                p_txt.append(f"Package: {pkg_w:.1f} W")
            except (ValueError, TypeError):
                pass
        if p_perf:
            power_perf = "|".join(p_perf)
            power_txt = ", ".join(p_txt)
            print(f'0 "{prefix} Power" {power_perf} Power draw: {power_txt}')

# 6. ACTIVE CLIENTS (Processes utilizing the GPU)
if report_clients:
    clients = sample.get("clients", {})
    if clients and isinstance(clients, dict):
        client_list = []
        name_counts = {}
        for cid, cinfo in clients.items():
            name = cinfo.get("name") or "Unknown"
            pid = cinfo.get("pid", "?")
            client_list.append(f"{name} (PID {pid})")
            name_counts[name] = name_counts.get(name, 0) + 1
        c_count = len(client_list)
        if name_counts:
            sorted_counts = sorted(name_counts.items(), key=lambda x: (-x[1], x[0]))
            breakdown = " (" + ", ".join(f"{cnt}x {pname}" for pname, cnt in sorted_counts) + ")"
        else:
            breakdown = ""
        long_out = ""
        if report_client_details and client_list:
            long_out = "\\n" + "\\n".join([f"- {item}" for item in client_list])
        print(f'0 "{prefix} Clients" processes={c_count};;;0;|active_clients={c_count};;;0; {c_count} active client process(es){breakdown}{long_out}')
    elif report_clients:
        print(f'0 "{prefix} Clients" processes=0;;;0;|active_clients=0;;;0; No active client processes')
EOF

elif [ "${PARSER}" = "jq" ]; then
    echo "${RAW_JSON}" | jq -r --arg prefix "${SERVICE_PREFIX}" \
      --arg hwmon_w "${HWMON_W}" \
      --argjson warn "${WARN_BUSY}" \
      --argjson crit "${CRIT_BUSY}" \
      --argjson sep "${REPORT_SEPARATE_ENGINES}" \
      --argjson summ "${REPORT_SUMMARY_ENGINE}" \
      --argjson freq "${REPORT_FREQUENCY}" \
      --argjson rc6 "${REPORT_RC6}" \
      --argjson irq "${REPORT_INTERRUPTS}" \
      --argjson pwr "${REPORT_POWER}" \
      --argjson cli "${REPORT_CLIENTS}" \
      --argjson cldet "${REPORT_CLIENT_DETAILS}" '
      (.[-1] // .[0] // .) as $s |
      
      # 1. Engines
      ($s.engines // {}) as $eng |
      ($eng | to_entries) as $entries |
      
      # Individual Engine Services
      (if $sep == 1 then
        $entries[] |
        (.value.busy // 0 | tonumber) as $busy |
        (if $busy >= $crit then 2 elif $busy >= $warn then 1 else 0 end) as $st |
        (if $busy >= $crit then "CRIT - " elif $busy >= $warn then "WARN - " else "" end) as $txt |
        "\($st) \"\($prefix) Engine \(.key)\" utilization=\($busy);\( $warn );\( $crit );0;100 \($txt)Engine utilization: \($busy)%"
      else empty end),

      # Summary Engine Service
      (if $summ == 1 and ($entries | length > 0) then
        ([$entries[] | (.value.busy // 0 | tonumber) as $busy | "\(.key | gsub("/";"_") | gsub(" ";"_"))=\($busy);\( $warn );\( $crit );0;100"] | join("|")) as $perf |
        ([$entries[] | select((.value.busy // 0 | tonumber) > 0) | "\(.key): \(.value.busy // 0)%"] | if length > 0 then join(", ") else "all engines idle" end) as $act |
        ([$entries[] | (.value.busy // 0 | tonumber) as $busy | if $busy >= $crit then 2 elif $busy >= $warn then 1 else 0 end] | max // 0) as $maxst |
        (if $maxst == 2 then "CRIT - " elif $maxst == 1 then "WARN - " else "" end) as $sttxt |
        "\($maxst) \"\($prefix) Engines Summary\" \($perf) \($sttxt)Active engines: \($act)"
      else empty end),
      
      # Frequency
      (if $freq == 1 and $s.frequency then
        ($s.frequency.actual // 0 | tonumber) as $act |
        ($s.frequency.requested // 0 | tonumber) as $req |
        "0 \"\($prefix) Frequency\" actual=\($act);;;0;2450|requested=\($req);;;0;2450 Frequency: \($act) MHz (requested: \($req) MHz)"
      else empty end),
      
      # RC6
      (if $rc6 == 1 and $s.rc6 then
        ($s.rc6.value // 0 | tonumber) as $rc |
        "0 \"\($prefix) RC6\" rc6=\($rc);;;0;100 RC6 power saving state: \($rc)%"
      else empty end),
      
      # Interrupts
      (if $irq == 1 and $s.interrupts then
        ($s.interrupts.count // 0 | tonumber) as $irqc |
        "0 \"\($prefix) Interrupts\" interrupts=\($irqc);;;0; Interrupt rate: \($irqc) irqs/s"
      else empty end),

      # Power
      (if $pwr == 1 then
        (($s.power // {}) + (if ($s.power | not) and ($hwmon_w | length > 0) then {GPU: ($hwmon_w | tonumber)} else {} end)) as $pwr_data |
        (if ($pwr_data | length > 0) then
          (
            [
              (if $pwr_data.GPU then "power_gpu=\($pwr_data.GPU);65;75;0;75" else empty end),
              (if $pwr_data.Package then "power_package=\($pwr_data.Package);;;0;" else empty end)
            ] | join("|")
          ) as $pperf |
          (
            [
              (if $pwr_data.GPU then "GPU: \($pwr_data.GPU) W" else empty end),
              (if $pwr_data.Package then "Package: \($pwr_data.Package) W" else empty end)
            ] | join(", ")
          ) as $ptxt |
          (if ($pperf | length > 0) then
            "0 \"\($prefix) Power\" \($pperf) Power draw: \($ptxt)"
          else empty end)
        else empty end)
      else empty end),

      # Clients
      (if $cli == 1 then
        ($s.clients // {}) as $clients |
        ($clients | to_entries) as $clist |
        (if ($clist | length > 0) then
          ($clist | map(.value.name // "Unknown") | group_by(.) | map({name: .[0], count: length}) | sort_by(-.count)) as $grouped |
          (if ($grouped | length > 0) then " (" + ($grouped | map("\(.count)x \(.name)") | join(", ")) + ")" else "" end) as $breakdown |
          (if $cldet == 1 then
            "\\n" + ([$clist[] | "- \(.value.name // "Unknown") (PID \(.value.pid // "?"))"] | join("\\n"))
          else "" end) as $longout |
          "0 \"\($prefix) Clients\" processes=\($clist | length);;;0;|active_clients=\($clist | length);;;0; \($clist | length) active client process(es)\($breakdown)\($longout)"
        else
          "0 \"\($prefix) Clients\" processes=0;;;0;|active_clients=0;;;0; No active client processes"
        end)
      else empty end)
    '
fi
