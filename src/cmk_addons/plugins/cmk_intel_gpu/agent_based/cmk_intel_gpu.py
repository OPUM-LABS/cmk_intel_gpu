#!/usr/bin/env python3
# ==============================================================================
# Checkmk Check Plugin: cmk_intel_gpu
# ==============================================================================
# Compatible with: Checkmk 2.3.0 through 2.5+ (Raw and Enterprise Editions)
# Uses Checkmk Agent-based API v2 (cmk.agent_based.v2)
# ==============================================================================

import json
import re
from typing import Any, Dict, Optional, Tuple

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Metric,
    Result,
    Service,
    State,
    StringTable,
    check_levels,
    render,
)


def _normalize_levels(levels: Any) -> Any:
    """Normalize levels to Checkmk API v2 format: ('fixed', (warn, crit)) or None."""
    if not levels:
        return None
    if isinstance(levels, (tuple, list)):
        if len(levels) == 2 and levels[0] == "fixed":
            val = levels[1]
            if isinstance(val, (tuple, list)) and len(val) == 2:
                return ("fixed", (float(val[0]), float(val[1])))
            return levels
        if len(levels) == 2 and levels[0] == "no_levels":
            return None
        if len(levels) == 2 and isinstance(levels[0], (int, float)):
            return ("fixed", (float(levels[0]), float(levels[1])))
    return levels


# ------------------------------------------------------------------------------
# 1. Section Parser
# ------------------------------------------------------------------------------
def parse_cmk_intel_gpu(string_table: StringTable) -> Optional[Dict[str, Any]]:
    """Parse JSON stream and optional CONFIG header produced by cmk_intel_gpu agent plugin."""
    config = {
        "engines": True,
        "frequency": True,
        "rc6": True,
        "interrupts": True,
        "power": True,
        "clients": True,
    }
    json_lines = []
    for row in string_table:
        if not row:
            continue
        line = row[0].strip()
        if line.startswith("CONFIG:"):
            parts = line[len("CONFIG:") :].split(":")
            for part in parts:
                if "=" in part:
                    k, v = part.split("=", 1)
                    k = k.lower().replace("report_", "")
                    config[k] = (v.strip() == "1")
        else:
            json_lines.append(row[0])

    text = "\n".join(json_lines).strip()
    if not text:
        return None

    # Ensure valid JSON array enclosure if truncated by signal
    if not text.startswith("["):
        text = f"[{text.rstrip(',')}]"
    elif not text.endswith("]"):
        text = f"{text.rstrip(',')}]"

    data = None
    # 1. Standard JSON parse
    try:
        loaded = json.loads(text)
        if isinstance(loaded, list) and len(loaded) > 0:
            data = loaded[-1]
        elif isinstance(loaded, dict):
            data = loaded
    except Exception:
        pass

    # 2. Fix missing commas between objects: "}\s*{" -> "},\n{"
    if data is None:
        try:
            fixed_text = re.sub(r"\}\s*\{", "},\n{", text).strip()
            if not fixed_text.startswith("["):
                fixed_text = f"[{fixed_text.rstrip(',')}]"
            elif not fixed_text.endswith("]"):
                fixed_text = f"{fixed_text.rstrip(',')}]"
            loaded = json.loads(fixed_text)
            if isinstance(loaded, list) and len(loaded) > 0:
                data = loaded[-1]
            elif isinstance(loaded, dict):
                data = loaded
        except Exception:
            pass

    # 3. Fallback: iterative raw_decode scanner to grab the last valid JSON dict
    if data is None:
        try:
            decoder = json.JSONDecoder()
            pos = 0
            clean = text.strip().lstrip("[").rstrip("]").strip()
            while pos < len(clean):
                match = clean.find("{", pos)
                if match == -1:
                    break
                try:
                    obj, idx = decoder.raw_decode(clean, match)
                    if isinstance(obj, dict):
                        data = obj
                    pos = idx
                except Exception:
                    pos = match + 1
        except Exception:
            pass

    if data is not None and isinstance(data, dict):
        data["_config"] = config
        return data

    return None


agent_section_cmk_intel_gpu = AgentSection(
    name="cmk_intel_gpu",
    parse_function=parse_cmk_intel_gpu,
)

# Backward compatibility for hosts still outputting <<<intel_gpu_top>>>
agent_section_legacy_intel_gpu_top = AgentSection(
    name="intel_gpu_top",
    parsed_section_name="cmk_intel_gpu",
    parse_function=parse_cmk_intel_gpu,
)


# ------------------------------------------------------------------------------
# 2. Engines Check Plugin (Item-based: Render/3D, Blitter, Video, Compute, etc.)
# ------------------------------------------------------------------------------
def discover_cmk_intel_gpu_engines(section: Dict[str, Any]) -> DiscoveryResult:
    if not section.get("_config", {}).get("engines", True):
        return
    engines = section.get("engines", {})
    if isinstance(engines, dict):
        for engine_name in sorted(engines.keys()):
            yield Service(item=engine_name)


def check_cmk_intel_gpu_engines(
    item: str,
    params: Dict[str, Any],
    section: Dict[str, Any],
) -> CheckResult:
    engines = section.get("engines", {})
    if not isinstance(engines, dict) or item not in engines:
        yield Result(state=State.UNKNOWN, summary=f"Engine {item} not present in telemetry")
        return

    engine_data = engines[item]
    try:
        busy = float(engine_data.get("busy", 0.0))
    except (ValueError, TypeError):
        busy = 0.0

    levels_upper = _normalize_levels(params.get("levels"))
    try:
        yield from check_levels(
            value=busy,
            levels_upper=levels_upper,
            metric_name="utilization",
            label="Utilization",
            render_func=render.percent,
            boundaries=(0.0, 100.0),
        )
    except Exception as e:
        yield Result(state=State.OK, summary=f"Utilization: {busy:.1f}%")
        yield Metric("utilization", value=busy, boundaries=(0.0, 100.0))
        yield Result(state=State.WARN, notice=f"Threshold evaluation error: {e}")


check_plugin_cmk_intel_gpu_engines = CheckPlugin(
    name="cmk_intel_gpu_engines",
    sections=["cmk_intel_gpu"],
    service_name="Intel GPU Engine %s",
    discovery_function=discover_cmk_intel_gpu_engines,
    check_function=check_cmk_intel_gpu_engines,
    check_ruleset_name="cmk_intel_gpu_engines",
    check_default_parameters={"levels": ("fixed", (80.0, 90.0))},
)


# ------------------------------------------------------------------------------
# 3. Frequency Check Plugin
# ------------------------------------------------------------------------------
def discover_cmk_intel_gpu_frequency(section: Dict[str, Any]) -> DiscoveryResult:
    if not section.get("_config", {}).get("frequency", True):
        return
    if "frequency" in section and isinstance(section["frequency"], dict):
        yield Service()


def check_cmk_intel_gpu_frequency(
    section: Dict[str, Any],
) -> CheckResult:
    freq = section.get("frequency", {})
    if not isinstance(freq, dict) or not freq:
        yield Result(state=State.UNKNOWN, summary="Frequency metrics unavailable")
        return

    try:
        act = float(freq.get("actual", 0.0))
        req = float(freq.get("requested", 0.0))
        u = freq.get("unit", "MHz")
    except (ValueError, TypeError):
        yield Result(state=State.UNKNOWN, summary="Invalid frequency data format")
        return

    yield Result(state=State.OK, summary=f"Actual: {act:.0f} {u} (requested: {req:.0f} {u})")
    yield Metric("frequency_actual", value=act)
    yield Metric("frequency_requested", value=req)


check_plugin_cmk_intel_gpu_frequency = CheckPlugin(
    name="cmk_intel_gpu_frequency",
    sections=["cmk_intel_gpu"],
    service_name="Intel GPU Frequency",
    discovery_function=discover_cmk_intel_gpu_frequency,
    check_function=check_cmk_intel_gpu_frequency,
)


# ------------------------------------------------------------------------------
# 4. RC6 Sleep State Check Plugin
# ------------------------------------------------------------------------------
def discover_cmk_intel_gpu_rc6(section: Dict[str, Any]) -> DiscoveryResult:
    if not section.get("_config", {}).get("rc6", True):
        return
    if "rc6" in section and isinstance(section["rc6"], dict):
        yield Service()


def check_cmk_intel_gpu_rc6(
    section: Dict[str, Any],
) -> CheckResult:
    rc6 = section.get("rc6", {})
    if not isinstance(rc6, dict) or "value" not in rc6:
        yield Result(state=State.UNKNOWN, summary="RC6 sleep state unavailable")
        return

    try:
        val = float(rc6.get("value", 0.0))
    except (ValueError, TypeError):
        val = 0.0

    yield Result(state=State.OK, summary=f"RC6 sleep state: {val:.1f}%")
    yield Metric("rc6", value=val, boundaries=(0.0, 100.0))


check_plugin_cmk_intel_gpu_rc6 = CheckPlugin(
    name="cmk_intel_gpu_rc6",
    sections=["cmk_intel_gpu"],
    service_name="Intel GPU RC6",
    discovery_function=discover_cmk_intel_gpu_rc6,
    check_function=check_cmk_intel_gpu_rc6,
)


# ------------------------------------------------------------------------------
# 5. Interrupts Check Plugin
# ------------------------------------------------------------------------------
def discover_cmk_intel_gpu_interrupts(section: Dict[str, Any]) -> DiscoveryResult:
    if not section.get("_config", {}).get("interrupts", True):
        return
    if "interrupts" in section and isinstance(section["interrupts"], dict):
        yield Service()


def check_cmk_intel_gpu_interrupts(
    section: Dict[str, Any],
) -> CheckResult:
    irq = section.get("interrupts", {})
    if not isinstance(irq, dict) or "count" not in irq:
        yield Result(state=State.UNKNOWN, summary="Interrupt telemetry unavailable")
        return

    try:
        val = float(irq.get("count", 0.0))
    except (ValueError, TypeError):
        val = 0.0

    yield Result(state=State.OK, summary=f"Interrupt rate: {val:.1f} irqs/s")
    yield Metric("interrupts", value=val)


check_plugin_cmk_intel_gpu_interrupts = CheckPlugin(
    name="cmk_intel_gpu_interrupts",
    sections=["cmk_intel_gpu"],
    service_name="Intel GPU Interrupts",
    discovery_function=discover_cmk_intel_gpu_interrupts,
    check_function=check_cmk_intel_gpu_interrupts,
)


# ------------------------------------------------------------------------------
# 6. Power Consumption Check Plugin
# ------------------------------------------------------------------------------
def discover_cmk_intel_gpu_power(section: Dict[str, Any]) -> DiscoveryResult:
    if not section.get("_config", {}).get("power", True):
        return
    power = section.get("power", {})
    if isinstance(power, dict) and any(k in power for k in ("GPU", "Package")):
        yield Service()


def check_cmk_intel_gpu_power(
    params: Dict[str, Any],
    section: Dict[str, Any],
) -> CheckResult:
    power = section.get("power", {})
    if not isinstance(power, dict) or not power:
        yield Result(state=State.UNKNOWN, summary="Power metrics unavailable")
        return

    p_gpu = power.get("GPU")
    p_pkg = power.get("Package")

    if p_gpu is not None:
        try:
            gpu_w = float(p_gpu)
            levels_gpu = _normalize_levels(params.get("levels_gpu"))
            try:
                yield from check_levels(
                    value=gpu_w,
                    levels_upper=levels_gpu,
                    metric_name="power_gpu",
                    label="GPU Power",
                    render_func=lambda v: f"{v:.1f} W",
                )
            except Exception as e:
                yield Result(state=State.OK, summary=f"GPU Power: {gpu_w:.1f} W")
                yield Metric("power_gpu", value=gpu_w)
                yield Result(state=State.WARN, notice=f"Power threshold evaluation error: {e}")
        except (ValueError, TypeError):
            pass

    if p_pkg is not None:
        try:
            pkg_w = float(p_pkg)
            yield Metric("power_package", value=pkg_w)
            yield Result(state=State.OK, summary=f"Package: {pkg_w:.1f} W")
        except (ValueError, TypeError):
            pass


check_plugin_cmk_intel_gpu_power = CheckPlugin(
    name="cmk_intel_gpu_power",
    sections=["cmk_intel_gpu"],
    service_name="Intel GPU Power",
    discovery_function=discover_cmk_intel_gpu_power,
    check_function=check_cmk_intel_gpu_power,
    check_ruleset_name="cmk_intel_gpu_power",
    check_default_parameters={"levels_gpu": ("fixed", (65.0, 75.0))},
)


# ------------------------------------------------------------------------------
# 7. Active Client Processes Check Plugin
# ------------------------------------------------------------------------------
def discover_cmk_intel_gpu_clients(section: Dict[str, Any]) -> DiscoveryResult:
    if not section.get("_config", {}).get("clients", True):
        return
    if "clients" in section and isinstance(section["clients"], dict):
        yield Service()


def check_cmk_intel_gpu_clients(
    params: Dict[str, Any],
    section: Dict[str, Any],
) -> CheckResult:
    clients = section.get("clients", {})
    if not isinstance(clients, dict):
        clients = {}

    client_list = []
    name_counts: Dict[str, int] = {}
    for cid, cinfo in clients.items():
        name = cinfo.get("name") or "Unknown"
        pid = cinfo.get("pid", "?")
        client_list.append(f"{name} (PID: {pid})")
        name_counts[name] = name_counts.get(name, 0) + 1

    count = len(client_list)
    levels_upper = _normalize_levels(params.get("levels"))

    if name_counts:
        sorted_counts = sorted(name_counts.items(), key=lambda x: (-x[1], x[0]))
        summary_breakdown = " (" + ", ".join(f"{cnt}x {pname}" for pname, cnt in sorted_counts) + ")"
    else:
        summary_breakdown = ""

    render_func = lambda v: f"{int(v)}{summary_breakdown}"

    try:
        yield from check_levels(
            value=count,
            levels_upper=levels_upper,
            metric_name="active_clients",
            label="Active client process(es)",
            render_func=render_func,
            boundaries=(0.0, None),
        )
    except Exception as e:
        yield Result(state=State.OK, summary=f"Active client process(es): {count}{summary_breakdown}")
        yield Metric("active_clients", value=count, boundaries=(0.0, None))
        yield Result(state=State.WARN, notice=f"Client threshold evaluation error: {e}")

    # Provide process details in notice view (accessible in drill-down details without cluttering overview)
    for client_item in client_list:
        yield Result(state=State.OK, notice=f"Process: {client_item}")


check_plugin_cmk_intel_gpu_clients = CheckPlugin(
    name="cmk_intel_gpu_clients",
    sections=["cmk_intel_gpu"],
    service_name="Intel GPU Clients",
    discovery_function=discover_cmk_intel_gpu_clients,
    check_function=check_cmk_intel_gpu_clients,
    check_ruleset_name="cmk_intel_gpu_clients",
    check_default_parameters={},
)
