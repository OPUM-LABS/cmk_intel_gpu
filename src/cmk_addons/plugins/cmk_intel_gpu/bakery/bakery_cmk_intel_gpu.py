#!/usr/bin/env python3
# ==============================================================================
# Checkmk Agent Bakery Plugin: cmk_intel_gpu
# ==============================================================================
# Automatically bakes the cmk_intel_gpu agent plugin into Linux agent packages
# for Checkmk Enterprise Edition (CEE/CCE). Safe on Raw Edition (CRE).
# ==============================================================================

try:
    from pathlib import Path
    from typing import Any, Dict
    from cmk.base.cee.plugins.bakery.bakery_api.v1 import OS, Plugin, PluginConfig, register

    def get_cmk_intel_gpu_files(conf: Dict[str, Any]):
        interval = conf.get("interval", 60) if isinstance(conf, dict) else 60
        yield Plugin(
            base_os=OS.LINUX,
            source=Path("cmk_intel_gpu"),
            interval=interval,
        )

        if isinstance(conf, dict):
            lines = [
                "# Created by Checkmk Agent Bakery for cmk_intel_gpu",
            ]
            if "device" in conf and conf["device"]:
                lines.append(f'INTEL_GPU_DEVICE="{conf["device"]}"')
            if "report_engines" in conf:
                lines.append(f'REPORT_ENGINES={1 if conf["report_engines"] else 0}')
            if "report_frequency" in conf:
                lines.append(f'REPORT_FREQUENCY={1 if conf["report_frequency"] else 0}')
            if "report_rc6" in conf:
                lines.append(f'REPORT_RC6={1 if conf["report_rc6"] else 0}')
            if "report_interrupts" in conf:
                lines.append(f'REPORT_INTERRUPTS={1 if conf["report_interrupts"] else 0}')
            if "report_power" in conf:
                lines.append(f'REPORT_POWER={1 if conf["report_power"] else 0}')
            if "report_clients" in conf:
                lines.append(f'REPORT_CLIENTS={1 if conf["report_clients"] else 0}')

            yield PluginConfig(
                base_os=OS.LINUX,
                lines=lines,
                target=Path("cmk_intel_gpu.cfg"),
            )

    register.bakery_plugin(
        name="cmk_intel_gpu",
        files_function=get_cmk_intel_gpu_files,
    )
except ImportError:
    # Checkmk Raw Edition (CRE) does not have Bakery API
    pass
