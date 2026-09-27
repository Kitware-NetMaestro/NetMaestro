# Net Maestro

Net Maestro is a web-based application for analyzing and visualizing network simulation data from PDES (Parallel Discrete Event Simulation) engines.

## Quick Start

### Running the Application

1. Clone the repository: `git clone https://github.com/NetMaestro/NetMaestro.git`
2. Navigate to the NetMaestro directory: `cd {path}/{to}/NetMaestro`
3. Run `docker compose up -d`
4. Access the site at <http://localhost:8000>
5. When finished, use `docker compose down`

## Management Commands

Run these inside the `django` container. From the host, with the stack running:

```sh
docker compose run --rm django ./manage.py <command> [options]
```

The repo is mounted at the container's working directory, so file paths relative to the `NetMaestro/` directory work as-is. Every command lists all of its options with `--help`.

Commands that queue work on Celery (everything except `ingest_topology` and `run_ffw`) need the `--immediate` flag.

### Ingest a topology: `ingest_topology`

```sh
./manage.py ingest_topology path/to/my-topology.yaml
```

Validates a fluid-flow WAN topology YAML file, saves it to `data/topologies/` (so it appears on the Topology page and in the FFW simulation form), and creates a switch component for each new combination of terminal bandwidth and switch buffer. The topology is named after the file, and the command stops if a topology with that name already exists.

### Ingest simulation results: `data_ingest` and `ingest_ffw`

ROSS event, model, and simulation files (one of each at most) as a new run:

```sh
./manage.py data_ingest --name "ESnet sample" \
    --event-file data/events/esnet-model-inst-evtrace.bin \
    --model-file data/models/esnet-model-inst-analysis-lps.bin \
    --simulation-file data/simulations/ross-stats-gvt.bin
```

FFW model-stats files from a finished fluid-flow WAN run, as a new run or added to an existing one with `--run-id`:

```sh
./manage.py ingest_ffw --name "FFW results" \
    path/to/ross-stats-model.bin path/to/ross-stats-analysis-lps.bin
```

### Run PHOLD: `run_phold`

```sh
./manage.py run_phold --name "PHOLD test" \
    --phold-path /opt/ross/phold --output-dir /tmp/phold_output \
    --synch 3 --np 4
```

Runs the PHOLD model bundled in the image, then creates a run and ingests its output. `--name`, `--phold-path`, and `--output-dir` are required; the model's parameters (`--nlp`, `--remote`, `--lookahead`, …) default to sensible values.

### Run a fluid-flow WAN simulation: `run_ffw`

```sh
./manage.py run_ffw --name "FFW 16-switch random" \
    --topology fluid-flow-wan-16-switch --traffic random \
    --sync 2 --np 4
```

Runs the FFW model on a topology from `data/topologies/` (by name, without `.yaml`), then stores and ingests its results. `--traffic` is `random` or `trace` and picks the model binary and traffic config from the `DJANGO_FFW_*` settings in `dev/.env.docker-compose`. The command waits for the simulation to finish. Conservative synchronization (`--sync 2`) with 2–4 MPI processes (`--np`) is the fastest setting for the bundled topologies.

## Features

- **Data Visualization**: Interactive plots and graphs for network simulation analysis
- **Multiple Data Formats**: Support for event, model, and simulation binary files
- **Flexible Data Loading**: Multiple options for providing your own data files
- **Web-Based Interface**: Access from any browser

## Requirements

- [VS Code with dev container support](https://code.visualstudio.com/docs/devcontainers/containers#_installation)
- Binary data files from PDES simulation engines (ROSS/CODES, etc.)

## Contributing

Contributions are welcome! See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup, testing, and code quality guidelines.

## License

Apache 2.0 - See LICENSE and NOTICE files for details.
