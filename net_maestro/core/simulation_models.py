"""Static registry of simulation models available in the application."""

from __future__ import annotations

from .base_models import BASE_MODEL_REGISTRY


def _component_models_for(names: list[str]) -> list[dict[str, object]]:
    """Return component model dicts for the given base model names."""
    return [
        {
            "name": m["name"],
            "type": m["component_type"],
            "description": m["description"],
            "parameters": [p["name"] if isinstance(p, dict) else p for p in m["parameters"]],
            "icon_class": m["icon_class"],
        }
        for m in BASE_MODEL_REGISTRY
        if m["name"] in names
    ]


SIMULATION_MODELS: list[dict[str, object]] = [
    {
        "name": "Fluid Flow WAN",
        "engine": "CODES",
        "category": "WAN Simulation",
        "icon_class": "ri-global-line",
        "description": (
            "Interval-fluid model of a multi-site WAN with max-min "
            "fair-share scheduling, switch buffer congestion, and "
            "Ethernet PAUSE/RESUME backpressure."
        ),
        "tags": ["interval-fluid", "backpressure", "trace/random"],
        "url_name": "configuration-partial",
        "active_page": "customComponents",
        "disabled": False,
        "component_models": _component_models_for(["fluid-flow-wan-switch-lp"]),
    },
    {
        "name": "PHOLD",
        "engine": "ROSS",
        "category": "Benchmark",
        "icon_class": "ri-speed-line",
        "description": (
            "Synthetic benchmark that exchanges random events across "
            "logical processes. Measures simulator throughput, not "
            "real network behavior."
        ),
        "tags": ["synthetic", "throughput", "validation"],
        "url_name": "simulation-config",
        "active_page": "simulation",
        "disabled": False,
        "component_models": [],
    },
    {
        "name": "Ping Pong",
        "engine": "CODES",
        "category": "HPC Interconnect",
        "icon_class": "ri-arrow-left-right-line",
        "description": (
            "Tutorial workload over a dragonfly-dally fabric. "
            "Compute nodes exchange fixed-size messages through "
            "routers to study latency and adaptive routing."
        ),
        "tags": ["dragonfly-dally", "packet-level", "tutorial"],
        "url_name": "",
        "active_page": "",
        "disabled": True,
        "component_models": _component_models_for(["nw-lp", "simplep2p"]),
    },
    {
        "name": "ESnet",
        "engine": "CODES",
        "category": "WAN Reference Topology",
        "icon_class": "ri-earth-line",
        "description": (
            "DOE Energy Sciences Network modeled as a WAN topology "
            "configuration with site-to-site latencies and bandwidths "
            "from the ESnet testbed."
        ),
        "tags": ["simplep2p", "trace-driven", "DOE"],
        "url_name": "",
        "active_page": "",
        "disabled": True,
        "component_models": _component_models_for(["nw-lp", "simplep2p"]),
    },
]
