from __future__ import annotations

from typing import TypedDict


class TypedParameter(TypedDict):
    name: str
    label: str
    type: str
    unit: str
    min: int
    max: int
    step: int


class BaseModel(TypedDict, total=False):
    name: str
    component_type: str
    engine: str
    icon_class: str
    description: str
    parameters: list[str | TypedParameter]
    disabled: bool


BASE_MODEL_REGISTRY: list[BaseModel] = [
    {
        "name": "nw-lp",
        "component_type": "host",
        "engine": "PDES (CODES)",
        "icon_class": "ri-organization-chart",
        "description": (
            "Network LP for compute-node endpoints. "
            "Carries an inline workload: block \u2014 traffic pattern, "
            "message count, timing, payload size."
        ),
        "parameters": [
            "traffic",
            "num_messages",
            "arrival_time",
            "payload_size",
        ],
        "disabled": True,
    },
    {
        "name": "simplep2p",
        "component_type": "router",
        "engine": "PDES (CODES)",
        "icon_class": "ri-server-line",
        "description": "Simple point-to-point router.",
        "parameters": [
            "routing",
            "latency",
            "bandwidth",
            "chunk_size",
            "vc_size",
        ],
        "disabled": True,
    },
    {
        "name": "fluid-flow-wan-switch-lp",
        "component_type": "switch",
        "engine": "PDES (CODES)",
        "icon_class": "ri-router-fill",
        "description": (
            "WAN router with a shared buffer pool and max-min fair-share "
            "egress scheduling. Connects to terminals and other switches. "
            "Supports Ethernet PAUSE/RESUME backpressure."
        ),
        "parameters": [
            {
                "name": "switch_buffer",
                "label": "Switch Buffer",
                "type": "number",
                "unit": "Gb",
                "min": 1,
                "max": 256,
                "step": 1,
            },
            {
                "name": "terminal_bandwidth",
                "label": "Terminal Bandwidth",
                "type": "number",
                "unit": "Gbps",
                "min": 1,
                "max": 400,
                "step": 1,
            },
        ],
    },
]

BASE_MODEL_BY_NAME: dict[str, BaseModel] = {m["name"]: m for m in BASE_MODEL_REGISTRY}
