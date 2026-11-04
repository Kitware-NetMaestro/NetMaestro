"""Load finished FABRIC runs into the database, so a fresh instance has results to explore.

Reads `data/webinar/manifest.yaml`: a standalone run and an ensemble, each member with
the output a real FFW run left behind. The outputs go through the same ingest as a run
the worker finished (stats files, model logs, summary), so the loaded runs look and
behave like ones run from the UI. No simulation runs and the Celery worker is not used.

Runs and ensembles already in the database under the same name are left alone, so the
command is safe to run more than once.
"""

from __future__ import annotations

from datetime import timedelta
import gzip
from pathlib import Path
import shutil
import tempfile
from typing import Any

from django.conf import settings
from django.core.files import File
from django.db import transaction
from django.utils import timezone
import djclick as click
import yaml

from net_maestro.core.constants import RunStatus, SimulationType
from net_maestro.core.models import Ensemble, FFWResultFile, FFWSimulationConfig, Run
from net_maestro.core.services.ensembles import create_ensemble
from net_maestro.core.services.ffw import FFW_STATS_FILES
from net_maestro.core.summaries import compute_run_summary
from net_maestro.core.tasks.ingest_ffw import run_ffw_ingest_task
from net_maestro.core.tasks.ingest_ffw_logs import ingest_ffw_logs

DEFAULT_SEED_DIR = Path(settings.BASE_DIR) / "data" / "webinar"


def _unpack(seed_dir: Path, work_dir: Path) -> Path:
    """Copy a run's seed files into `work_dir`, gunzipping them, and return its config."""
    for source in seed_dir.rglob("*"):
        if not source.is_file():
            continue
        target = work_dir / source.relative_to(seed_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix == ".gz":
            with gzip.open(source, "rb") as packed, target.with_suffix("").open("wb") as out:
                shutil.copyfileobj(packed, out)
        else:
            shutil.copyfile(source, target)
    configs = list(work_dir.glob("*.yaml"))
    if len(configs) != 1:
        raise click.ClickException(f"{seed_dir}: expected one traffic config, found {len(configs)}")
    return configs[0]


def _load_outputs(run: Run, seed_dir: Path, wall_time_s: float) -> None:
    """Ingest a run's seed outputs the way `run_ffw_simulation` does, and complete it."""
    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)
        config_path = _unpack(seed_dir, work_dir)
        result_files = []
        for name in FFW_STATS_FILES:
            with (work_dir / name).open("rb") as stream:
                result_files.append(
                    FFWResultFile.objects.create(run=run, file=File(stream, name=name))
                )
        run_ffw_ingest_task([result_file.pk for result_file in result_files])
        ingest_ffw_logs(run, config_path)

    finished = timezone.now()
    run.status = RunStatus.COMPLETED
    run.started_at = finished - timedelta(seconds=wall_time_s)
    run.finished_at = finished
    run.save(update_fields=["status", "started_at", "finished_at"])
    compute_run_summary(run)


def _load_run(spec: dict[str, Any], seed_root: Path) -> None:
    if Run.objects.filter(name=spec["name"], ensemble__isnull=True).exists():
        click.echo(f"Run '{spec['name']}': already loaded")
        return
    with transaction.atomic():
        run = Run.objects.create(
            name=spec["name"],
            description=spec.get("description", ""),
            status=RunStatus.SAVED,
            simulation_type=SimulationType.FFW,
        )
        FFWSimulationConfig.objects.create(run=run, **spec["config"])
        _load_outputs(run, seed_root / spec["dir"], spec["wall_time_s"])
    click.echo(f"Run {run.id}: loaded '{run.name}'")


def _load_ensemble(spec: dict[str, Any], seed_root: Path) -> None:
    if Ensemble.objects.filter(name=spec["name"]).exists():
        click.echo(f"Ensemble '{spec['name']}': already loaded")
        return
    with transaction.atomic():
        ensemble = create_ensemble(
            name=spec["name"],
            description=spec.get("description", ""),
            simulation_type=SimulationType.FFW,
            base_params=spec["base_params"],
            sweep_spec=spec["sweep_spec"],
            run_status=RunStatus.SAVED,
        )
        members = {run.member_index: run for run in ensemble.members}
        if set(members) != set(spec["members"]):
            raise click.ClickException(
                f"{spec['name']}: the sweep makes members {sorted(members)}, "
                f"the manifest has {sorted(spec['members'])}"
            )
        for index, member in spec["members"].items():
            _load_outputs(members[index], seed_root / member["dir"], member["wall_time_s"])
    click.echo(f"Ensemble {ensemble.id}: loaded '{ensemble.name}' with {len(members)} members")


@click.command()
@click.option(
    "--seed-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=DEFAULT_SEED_DIR,
    show_default=True,
    help="Directory holding manifest.yaml and the runs' outputs.",
)
def load_demo(seed_dir: Path) -> None:
    """Load the FABRIC demo runs and ensemble, skipping any already loaded."""
    manifest = yaml.safe_load((seed_dir / "manifest.yaml").read_text(encoding="utf-8"))
    for spec in manifest.get("runs", []):
        _load_run(spec, seed_dir)
    for spec in manifest.get("ensembles", []):
        _load_ensemble(spec, seed_dir)
