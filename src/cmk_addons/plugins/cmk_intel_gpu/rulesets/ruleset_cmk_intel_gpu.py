#!/usr/bin/env python3
# ==============================================================================
# Checkmk Ruleset: cmk_intel_gpu
# ==============================================================================
# Defines Setup (WATO) configuration forms for Intel GPU checks and Agent Bakery.
# Uses Checkmk Rulesets API v1 (cmk.rulesets.v1)
# ==============================================================================

from cmk.rulesets.v1 import Help, Label, Title
from cmk.rulesets.v1.form_specs import (
    BooleanChoice,
    DefaultValue,
    DictElement,
    Dictionary,
    Float,
    InputHint,
    Integer,
    LevelDirection,
    Percentage,
    SimpleLevels,
    String,
)
from cmk.rulesets.v1.rule_specs import (
    AgentConfig,
    CheckParameters,
    HostAndItemCondition,
    HostCondition,
    Topic,
)


# ------------------------------------------------------------------------------
# 1. Service Monitoring Rule: Engine Utilization
# ------------------------------------------------------------------------------
def _parameter_form_engines():
    return Dictionary(
        elements={
            "levels": DictElement(
                parameter_form=SimpleLevels[float](
                    title=Title("Upper percentage levels for engine utilization"),
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Percentage(),
                    prefill_fixed_levels=InputHint(value=(80.0, 90.0)),
                ),
            ),
        }
    )


rule_spec_cmk_intel_gpu_engines = CheckParameters(
    name="cmk_intel_gpu_engines",
    topic=Topic.APPLICATIONS,
    condition=HostAndItemCondition(item_title=Title("Engine name")),
    parameter_form=_parameter_form_engines,
    title=Title("Intel GPU Engine Utilization"),
)


# ------------------------------------------------------------------------------
# 2. Service Monitoring Rule: GPU Power Draw
# ------------------------------------------------------------------------------
def _parameter_form_power():
    return Dictionary(
        elements={
            "levels_gpu": DictElement(
                parameter_form=SimpleLevels[float](
                    title=Title("Upper levels for GPU power draw (Watts)"),
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Float(),
                    prefill_fixed_levels=InputHint(value=(65.0, 75.0)),
                ),
            ),
        }
    )


rule_spec_cmk_intel_gpu_power = CheckParameters(
    name="cmk_intel_gpu_power",
    topic=Topic.APPLICATIONS,
    condition=HostCondition(),
    parameter_form=_parameter_form_power,
    title=Title("Intel GPU Power Consumption"),
)


# ------------------------------------------------------------------------------
# 3. Service Monitoring Rule: Active Client Processes
# ------------------------------------------------------------------------------
def _parameter_form_clients():
    return Dictionary(
        elements={
            "levels": DictElement(
                parameter_form=SimpleLevels[int](
                    title=Title("Upper levels for active client process count"),
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Integer(),
                    prefill_fixed_levels=InputHint(value=(5, 10)),
                ),
            ),
        }
    )


rule_spec_cmk_intel_gpu_clients = CheckParameters(
    name="cmk_intel_gpu_clients",
    topic=Topic.APPLICATIONS,
    condition=HostCondition(),
    parameter_form=_parameter_form_clients,
    title=Title("Intel GPU Active Clients"),
)


# ------------------------------------------------------------------------------
# 4. Agent Bakery configuration rule (Enterprise Edition)
# ------------------------------------------------------------------------------
try:
    def _parameter_form_bakery():
        return Dictionary(
            elements={
                "interval": DictElement(
                    parameter_form=Integer(
                        title=Title("Execution interval / check frequency (seconds)"),
                        prefill=DefaultValue(60),
                        help_text=Help(
                            "Defines how often (in seconds) the agent plugin executes "
                            "asynchronously in the background on the monitored host (default: 60s)."
                        ),
                    ),
                    required=True,
                ),
                "device": DictElement(
                    parameter_form=String(
                        title=Title("Target GPU device (empty for auto-detect)"),
                        prefill=DefaultValue(""),
                        help_text=Help(
                            "Path to GPU device node (e.g. /dev/dri/card1). "
                            "Leave empty to automatically detect the Intel GPU on each host (recommended)."
                        ),
                    ),
                ),
                "report_engines": DictElement(
                    parameter_form=BooleanChoice(
                        title=Title("Hardware Engines"),
                        label=Label("Monitor hardware engines (Render/3D, Video, Compute, Blitter)"),
                        prefill=DefaultValue(True),
                    ),
                    required=True,
                ),
                "report_frequency": DictElement(
                    parameter_form=BooleanChoice(
                        title=Title("GPU Core Frequency"),
                        label=Label("Monitor actual and requested clock frequency (MHz)"),
                        prefill=DefaultValue(True),
                    ),
                    required=True,
                ),
                "report_rc6": DictElement(
                    parameter_form=BooleanChoice(
                        title=Title("RC6 Power Saving"),
                        label=Label("Monitor RC6 power-saving sleep state (%)"),
                        prefill=DefaultValue(True),
                    ),
                    required=True,
                ),
                "report_interrupts": DictElement(
                    parameter_form=BooleanChoice(
                        title=Title("Interrupts"),
                        label=Label("Monitor GPU interrupt rate (irqs/s)"),
                        prefill=DefaultValue(True),
                    ),
                    required=True,
                ),
                "report_power": DictElement(
                    parameter_form=BooleanChoice(
                        title=Title("Power Consumption"),
                        label=Label("Monitor GPU and Package power draw (Watts)"),
                        prefill=DefaultValue(True),
                    ),
                    required=True,
                ),
                "report_clients": DictElement(
                    parameter_form=BooleanChoice(
                        title=Title("Active Client Processes"),
                        label=Label("Monitor active client processes (Plex Transcoder, etc.)"),
                        prefill=DefaultValue(True),
                    ),
                    required=True,
                ),
            }
        )

    rule_spec_cmk_intel_gpu_bakery = AgentConfig(
        name="cmk_intel_gpu",
        topic=Topic.APPLICATIONS,
        parameter_form=_parameter_form_bakery,
        title=Title("Intel GPU Monitoring (cmk_intel_gpu)"),
    )
except (ImportError, AttributeError):
    pass
