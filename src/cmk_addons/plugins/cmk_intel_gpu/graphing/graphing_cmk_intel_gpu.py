#!/usr/bin/env python3
# ==============================================================================
# Checkmk Graphing & Perf-O-Meter: cmk_intel_gpu
# ==============================================================================
# Defines Metrics and Perf-O-Meters for Intel GPU services.
# Uses Checkmk Graphing API v1 (cmk.graphing.v1)
# ==============================================================================

from cmk.graphing.v1 import Title
from cmk.graphing.v1.metrics import (
    Color,
    DecimalNotation,
    Metric,
    Unit,
)
from cmk.graphing.v1.perfometers import (
    Closed,
    FocusRange,
    Perfometer,
)

# ------------------------------------------------------------------------------
# Metrics Definitions (Variables must begin with 'metric_')
# ------------------------------------------------------------------------------
metric_utilization = Metric(
    name="utilization",
    title=Title("Engine Utilization"),
    unit=Unit(DecimalNotation("%")),
    color=Color.BLUE,
)

metric_active_clients = Metric(
    name="active_clients",
    title=Title("Active GPU Clients"),
    unit=Unit(DecimalNotation("")),
    color=Color.GREEN,
)

metric_power_gpu = Metric(
    name="power_gpu",
    title=Title("GPU Power Draw"),
    unit=Unit(DecimalNotation("W")),
    color=Color.ORANGE,
)

metric_power_package = Metric(
    name="power_package",
    title=Title("Package Power Draw"),
    unit=Unit(DecimalNotation("W")),
    color=Color.PURPLE,
)

metric_rc6 = Metric(
    name="rc6",
    title=Title("RC6 Power Saving State"),
    unit=Unit(DecimalNotation("%")),
    color=Color.CYAN,
)

# ------------------------------------------------------------------------------
# Perf-O-Meter Definitions (Variables must begin with 'perfometer_')
# ------------------------------------------------------------------------------
perfometer_utilization = Perfometer(
    name="utilization",
    focus_range=FocusRange(Closed(0), Closed(100)),
    segments=["utilization"],
)

perfometer_active_clients = Perfometer(
    name="active_clients",
    focus_range=FocusRange(Closed(0), Closed(10)),
    segments=["active_clients"],
)

perfometer_power_gpu = Perfometer(
    name="power_gpu",
    focus_range=FocusRange(Closed(0), Closed(75)),
    segments=["power_gpu"],
)
