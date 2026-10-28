# Follow-ons

Work that was deliberately left for later, with the details needed to pick it up cold.
Unlike `KNOWN_ISSUES.md`, these are not bugs; they are the next steps behind decisions
already made. Move an entry to the bottom section when it lands.

---

## Ensembles and FFW runs

### Parallel members

Members of an ensemble run one after another in a Celery chain
(`services/ensembles.py::launch_ensemble`). That was forced while every FFW run rewrote the
stock example config in place; since each run generates its own inputs under
`FFW_OUTPUT_DIR/run-<id>-<uuid>/` (`Run.work_dir`), nothing stops members running at once.
Switching the chain to a Celery `group` is a one-line change. What is not decided is how
many `mpirun` processes a developer laptop or a deployment should run at once: the worker's
concurrency caps the number of simultaneous members, and each member's `np` multiplies it.
Decide a budget (e.g. a `FFW_MAX_CONCURRENT_RUNS` setting honoured by the chain/group
builder) before flipping it.

### Traffic-config sweep axes

`write_run_inputs` (`services/ffw.py`) applies a NetMaestro-owned `overrides` mapping to the
generated config's `sections.fluid_flow_wan` block, and `run_ffw_simulation` accepts an
`overrides` kwarg merged over the traffic mode's defaults. That is the hook for the knobs
that are not yet sweepable:

- `rng_seed` — replicates. The first axis where statistics across members (mean ± std per
  configuration) become meaningful; `ensemble_stats.effect_table` already averages members
  that share a cell and flags it with `averaged`.
- `random_flow_min` / `random_flow_max` — offered load.
- `flow_generation_every_n_intervals`, `num_send_intervals`, `num_drain_intervals`,
  `interval_seconds` — run shape and length.
- `pause_enabled`, `pause_high_watermark_fraction`, `pause_low_watermark_fraction`,
  `backpressure_delay_ms` — PAUSE behaviour.

Each is a `sweeps.py` `Axis` whose `apply` puts the value into `params["overrides"]`, plus
passing `overrides` through `launch_ensemble`'s task signature and storing it on
`FFWSimulationConfig` (a JSON field) so a saved run reproduces it. **Held until Sanjay's
model changes settle**: the config schema may move, and the template approach was chosen so
NetMaestro does not have to know about fields it does not own.

### Advanced run options in the UI

Caitlin wants NetMaestro to pick sensible settings itself and only later expose them. The
settings currently chosen for the user: VT sampling interval and end
(`services/ffw.py::vt_sampling_for`, ten samples per fluid interval over the whole run) and
the random-traffic drain length (`FFW_TRAFFIC_DEFAULTS[...]["overrides"]`). An "advanced"
section on the FFW and ensemble forms would surface these and the traffic overrides above,
with the derived values shown as placeholders so a user sees what NetMaestro would do.

### Drain-until-idle in the model

An FFW run ends when its interval schedule runs out (`num_send_intervals +
num_drain_intervals`; see `schedule_switch_egress` in `model-net-fluid-flow-wan.cxx`), not
at ROSS's end time, which the model sets to a year. Whatever is still queued at the last
interval is left behind, and the `drained` health check reports it. A model option that
keeps scheduling intervals while any source backlog or in-flight volume remains (up to
`MAX_SIMULATION_INTERVALS = 4096`) would remove the guesswork from sizing the drain for a
sweep's slowest member. This is a CODES change in Caitlin's fork, not a NetMaestro one.

### Rebuilding the FFW image

The django/celery images clone Caitlin's CODES fork at `FFW_GIT_REF` in
`dev/django.Dockerfile` and build it; the stock example configs come from that checkout's
`doc/example/`. Changing a template means committing to the fork, bumping the ref, and
rebuilding (ROSS, CODES and FFW compile, so plan for the wait). NetMaestro no longer needs
template edits for the settings it owns, which is the point of the overrides.

### Links from the member table into a run's inputs and logs

`Run.work_dir` records where a run's generated config, topology YAML, trace and the model's
own CSV logs live, but nothing shows it. A "details" disclosure per member (or a download of
the generated config) would close the provenance loop the May 2026 reproducibility
requirement asked for; the CSV export already carries the topology name.

### Ensemble page

- **Cross-member plots.** Parallel coordinates landed ("Compare members" card; one line per
  member, brushing dims the table, hovering a row lights its line). Known rough edges: the
  Viridis low end is faint on the dark theme, so low-valued lines are hard to see unless
  hovered; lower-is-better metrics are not reversed on the colour scale; members without a
  value on every axis (running, failed) are left off the plot. Next: a parameter-vs-metric
  scatter with replicates once seed sweeps exist, and overlaid time series per member
  (needs multi-run sample fetching; the run data endpoints are unpaginated, see
  `KNOWN_ISSUES.md`).
- **Cancel.** No way to stop a running ensemble or member; `RunStatus.CANCELLED` exists
  but nothing sets it.
- **Edit / clone an ensemble.** The form only creates; cloning a saved sweep with one axis
  changed is the obvious next convenience.
- **Delete.** Neither ensembles nor their derived topology files
  (`data/topologies/<base>-sweep-<ensemble>-<member>.yaml`) can be removed from the UI; the
  admin can delete the rows but leaves the files.

### Other simulation types

`sweeps.SWEEP_AXES` and `summaries.METRICS` are keyed by `SimulationType`; only FFW is
registered. PHOLD is nearly free (its ten numeric config fields are already columns, and
`summaries` already computes engine metrics for any run with PE rows), and would let the
ensemble page be exercised without the FFW build. Dragonfly / ping-pong need their config
plumbing first.

### Summaries beyond FFW traffic

`RunSummary.metrics` is flat JSON with a registry describing each key. Candidates not yet
computed: per-switch peak occupancy (today only the overall peak and its switch), flow
completion times (only the model's `fluid-segment-events.csv` has per-flow identity; the
binary stats do not), and anything the LLM-summarization design note
(Notion, "LLM-assisted model creation…") wants as a finding record with provenance.

### Multi-user

Single user per instance is assumed throughout: no ownership on runs or ensembles, and the
ensemble chain assumes nobody else is launching FFW runs. Listed in the Phase II narrative as
future work.

---

## Development notes that bite

- The `celery` container does not reload code. After changing anything under
  `net_maestro/core/tasks/` or the services they import, `docker compose restart celery`,
  or the worker keeps running the old task (symptom: runs complete with no summary, no
  `started_at`).
- Templates are cached by the dev server; `docker compose restart django` after editing
  one before checking in a browser (tests do not care).
- `./manage.py summarize_runs --all` backfills summaries for completed runs that predate
  the summary hook or were ingested from files.

---

## Landed

_(nothing yet)_
