from __future__ import annotations

import csv
from dataclasses import dataclass
import logging
import shutil
import subprocess
from typing import TYPE_CHECKING, Any

import yaml

from net_maestro.core.constants import FFWTrafficMode
from net_maestro.core.topology import SWITCH_LP_NAME

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from net_maestro.core.topology import Topology

logger = logging.getLogger(__name__)


FFW_STATS_FILES = ("ross-stats-model.bin", "ross-stats-analysis-lps.bin")

NS_PER_S = 1_000_000_000

# GVT-sampled simulation engine stats (PE/KP/LP), written when --engine-stats is on.
FFW_ENGINE_STATS_FILE = "ross-stats-gvt.bin"


# For each traffic mode: the settings naming the stock binary and the template traffic
# config, and the `fluid_flow_wan` settings NetMaestro owns, which win over the
# template's (see write_run_inputs).
FFW_TRAFFIC_DEFAULTS: dict[str, dict[str, Any]] = {
    FFWTrafficMode.RANDOM: {
        "binary": "FFW_BINARY_PATH",
        "config": "FFW_CONFIG_PATH",
        # The template's 30 drain intervals are too few for the slow links a sweep
        # visits: at 40 Gbps the STAR-MICH members need about 85 to empty the network,
        # so they ended with traffic still in flight. Intervals after the drain are
        # idle and cost little, so the margin is generous.
        "overrides": {"num_drain_intervals": 100},
    },
    FFWTrafficMode.TRACE: {
        "binary": "FFW_TRACE_BINARY_PATH",
        "config": "FFW_TRACE_CONFIG_PATH",
        # The validation ladder's 5 x 10 s drain is part of its design; keep it.
        "overrides": {},
    },
}


class FFWInputError(Exception):
    """Raised when the traffic config or trace cannot be used with the topology."""


def _with_unit(value: float, unit: str) -> str:
    """Write a gigabit value the way the FFW YAML wants it: `18.3324 Gbps`."""
    return f"{f'{value:.4f}'.rstrip('0').rstrip('.') or '0'} {unit}"


def _topology_document(topology: Topology) -> dict[str, Any]:
    outbound: dict[str, dict[str, str]] = {switch.name: {} for switch in topology.switches}
    for link in topology.links:
        outbound[link.source][link.target] = _with_unit(link.bandwidth_gbps, "Gbps")
    return {
        "topology": {
            "switches": {
                switch.name: {
                    "terminals": switch.terminals,
                    "terminal_bandwidth": _with_unit(switch.terminal_bandwidth_gbps, "Gbps"),
                    "switch_buffer": _with_unit(switch.switch_buffer_gb, "Gb"),
                    **({"connections": outbound[switch.name]} if outbound[switch.name] else {}),
                }
                for switch in topology.switches
            }
        }
    }


def _ffw_group(config: dict[str, Any]) -> dict[str, Any]:
    """Return the LP group that holds the FFW switch and terminal LPs."""
    groups = (config.get("topology") or {}).get("groups") or {}
    for group in groups.values():
        if SWITCH_LP_NAME in (group.get("lps") or {}):
            if group.get("repetitions", 1) != 1:
                raise FFWInputError("The FFW LP group must have repetitions: 1")
            return group
    raise FFWInputError(f"No LP group in the traffic config lists {SWITCH_LP_NAME}")


def _check_trace(path: Path, terminal_count: int) -> None:
    """Refuse a trace CSV that names terminals the topology does not have."""
    with path.open(newline="", encoding="utf-8") as stream:
        for line, row in enumerate(csv.DictReader(stream), start=2):
            for column in ("source_terminal", "destination_terminal"):
                terminal = int(row[column])
                if not 0 <= terminal < terminal_count:
                    raise FFWInputError(
                        f"{path.name} line {line}: {column} {terminal} is outside this "
                        f"topology's terminals 0-{terminal_count - 1}"
                    )


def write_run_inputs(
    *,
    run_dir: Path,
    template_path: Path,
    topology: Topology,
    overrides: Mapping[str, Any],
) -> Path:
    """Write the inputs for one run on `topology` into `run_dir/inputs`, and return the config.

    The traffic config is generated from `template_path`, which is only read: each
    run gets its own config, topology file and logs, so runs do not overwrite one
    another's inputs and the stock example stays as it shipped. The generated config
    keeps every template field NetMaestro does not own, so a new model setting passes
    through untouched; it takes the topology's LP counts and `topology_yaml_file`, and
    then `overrides` is applied to `sections.fluid_flow_wan` last, so a NetMaestro-owned
    value wins over the template's. The file is written by PyYAML, so the template's
    comments do not carry over; nobody edits the generated copy.

    The model resolves the topology file, the trace and the log paths relative to the
    traffic config, so all of them go under `inputs/` beside it: the topology YAML,
    each `*_log_path` directory, and for trace traffic a copy of the template's trace
    at the same relative path, checked against the topology's terminals first.
    Nothing is written outside `run_dir`.
    """
    inputs = topology.simulation_inputs()
    config = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    section = config["sections"]["fluid_flow_wan"]
    inputs_dir = run_dir / "inputs"

    _ffw_group(config)["lps"].update(inputs["lps"])
    section["topology_yaml_file"] = inputs["topology_yaml_file"]
    section.update(overrides)

    trace_source: Path | None = None
    if trace := section.get("traffic_trace_file"):
        trace_source = template_path.parent / trace
        _check_trace(trace_source, inputs["terminal_count"])

    inputs_dir.mkdir(parents=True, exist_ok=True)
    if trace_source is not None:
        trace_copy = inputs_dir / section["traffic_trace_file"]
        trace_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(trace_source, trace_copy)
    for key, value in section.items():
        if key.endswith("_log_path"):
            (inputs_dir / value).parent.mkdir(parents=True, exist_ok=True)

    (inputs_dir / inputs["topology_yaml_file"]).write_text(
        yaml.safe_dump(_topology_document(topology), sort_keys=False), encoding="utf-8"
    )
    config_path = inputs_dir / template_path.name
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


# VT samples per fluid interval when NetMaestro picks the cadence. One per interval
# is too coarse to draw a curve; ten keeps a 42 s run at a few hundred samples per LP.
VT_SAMPLES_PER_INTERVAL = 10


@dataclass(frozen=True)
class VTSampling:
    """The model's virtual-time sampling settings, both in nanoseconds."""

    interval_ns: int
    end_ns: int


def vt_sampling_for(config_path: Path) -> VTSampling:
    """Return the VT sampling that covers the whole run described by a traffic config.

    The model runs for `num_send_intervals + num_drain_intervals` fluid intervals of
    `interval_seconds` each, so sampling ends there. A fixed end is wrong in both
    directions: 1.7e10 ns cut the 42 s FABRIC random-traffic run short at 17 s, so
    its summaries saw a network that had not drained yet, and it would waste samples
    on a run shorter than that. The cadence follows the interval length too, so the
    420 s trace ladder gets the same samples per interval as a 42 s run rather than
    ten times as many rows.
    """
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    section = (config.get("sections") or {}).get("fluid_flow_wan") or {}
    try:
        interval_s = float(section["interval_seconds"])
        intervals = int(section["num_send_intervals"]) + int(section["num_drain_intervals"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FFWInputError(
            f"{config_path.name}: fluid_flow_wan needs numeric interval_seconds, "
            "num_send_intervals and num_drain_intervals"
        ) from exc
    if interval_s <= 0 or intervals <= 0:
        raise FFWInputError(f"{config_path.name}: the run length must be positive")
    return VTSampling(
        interval_ns=max(1, round(interval_s * NS_PER_S / VT_SAMPLES_PER_INTERVAL)),
        end_ns=round(intervals * interval_s * NS_PER_S),
    )


def execute_ffw_model(  # noqa: PLR0913
    *,
    np: int,
    sync: int,
    model_stats: int,
    num_gvt: int,
    rt_interval: int,
    vt_interval: int,
    vt_samp_end: int,
    engine_stats: int,
    pe_data: int,
    kp_data: int,
    lp_data: int,
    config_path: str,
    working_dir: str,
    binary_path: str,
    stats_dir: Path,
) -> Path:
    """Run the model, writing its ROSS stats into `stats_dir`, and return that directory.

    `stats_dir` must not exist yet: ROSS creates it, but if it already exists ROSS
    quietly writes to `<stats_dir>-<pid>-<time>` instead, and the results would be
    read from the wrong place.
    """
    if stats_dir.exists():
        raise FileExistsError(f"FFW stats directory {stats_dir} already exists")
    stats_dir.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "mpirun",
        "-np",
        str(np),
        binary_path,
        f"--sync={sync}",
        f"--model-stats={model_stats}",
        f"--num-gvt={num_gvt}",
        f"--rt-interval={rt_interval}",
        f"--vt-interval={vt_interval}",
        f"--vt-samp-end={vt_samp_end}",
        f"--engine-stats={engine_stats}",
        f"--pe-data={pe_data}",
        f"--kp-data={kp_data}",
        f"--lp-data={lp_data}",
        f"--stats-path={stats_dir}",
        "--",
        config_path,
    ]
    try:
        result = subprocess.run(cmd, cwd=working_dir, check=True, capture_output=True, text=True)  # noqa: S603
    except subprocess.CalledProcessError as e:
        # The model's own error message is at the end of its output. No traceback here:
        # run_ffw_simulation logs it once.
        logger.error(  # noqa: TRY400
            "FFW simulation exited with code %s.\n--- last lines of stdout ---\n%s\n"
            "--- last lines of stderr ---\n%s",
            e.returncode,
            _tail(e.stdout),
            _tail(e.stderr),
        )
        raise
    logger.info("FFW simulation finished; full output is logged at DEBUG level")
    logger.debug("FFW simulation output:\n%s", result.stdout)
    missing = [name for name in FFW_STATS_FILES if not (stats_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"FFW finished but wrote no {', '.join(missing)} in {stats_dir}")
    return stats_dir


def _tail(text: str | None, lines: int = 20) -> str:
    return "\n".join((text or "").splitlines()[-lines:])
