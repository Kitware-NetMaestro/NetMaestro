# CLI Reference

NetMaestro provides management commands for common operations that can also be run outside the UI.

All commands are invoked through Django's `manage.py`:

```sh
# Inside the dev container:
./manage.py <command> [options]

# Via Docker Compose:
docker compose run --rm django uv run python manage.py <command> [options]
```

## ingest_topology

Import a fluid-flow WAN topology YAML file into the application.

This command copies the file into the topology directory so it appears in the topology dropdown and creates custom switch components for each unique switch configuration in the file:

```sh
./manage.py ingest_topology /path/to/my-topology.yaml
```

### Behavior

1. Parses the YAML and validates it as a well-formed FFW topology
2. For each unique `(terminal_bandwidth, switch_buffer)` pair:
   - Checks if a matching `ComponentModel` already exists
   - Creates one if not, named after the first switch with that configuration
3. Copies the topology file into the topology directory

### Example

Given a topology file with three switches where A and B share the same configuration:

```yaml
topology:
  switches:
    A:
      terminals: 2
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "64 Gb"
      connections:
        B: "30 Gbps"
    B:
      terminals: 2
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "64 Gb"
      connections:
        A: "30 Gbps"
        C: "10 Gbps"
    C:
      terminals: 2
      terminal_bandwidth: "50 Gbps"
      switch_buffer: "32 Gb"
      connections:
        A: "20 Gbps"
        B: "10 Gbps"
```

Running the command:

```
$ ./manage.py ingest_topology example-topology.yaml
Created: Switch A (100 Gbps, 64 Gb)
Created: Switch C (50 Gbps, 32 Gb)
Skipped: Switch B — config (100 Gbps, 64 Gb) already exists
Saved topology: example-topology
Done: 2 created, 1 skipped
```

The command is **idempotent** for components — running it again with the same file skips all existing configurations. Topology files cannot be overwritten; attempting to re-import a topology with the same name raises an error.

### Options

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH`   | Yes      | Path to the topology YAML file |

## run_ffw

Execute a Fluid Flow WAN simulation and track it as a Run.

```sh
./manage.py run_ffw \
  --name "My FFW Run" \
  --np 3 \
  --sync 3 \
  --config-path /path/to/traffic-config.yaml \
  --working-dir /path/to/codes/build
```

### Behavior

1. Creates (or updates) a `Run` record in the database
2. Ensures the logs output directory exists
3. Submits the simulation as a Celery task that:
   - Runs the FFW binary via `mpirun` with the specified parameters
   - Ingests the resulting CSV log files (terminal events, switch events, fluid segments)

### Options

| Option           | Required | Default          | Description                                    |
|-----------------|----------|------------------|------------------------------------------------|
| `--name`        | Yes      | —                | Run identifier                                 |
| `--np`          | No       | 1                | Number of MPI ranks                            |
| `--sync`        | No       | 1                | Synchronization protocol (1–6)                 |
| `--config-path` | No       | —                | Path to FFW traffic configuration file         |
| `--working-dir` | No       | `FFW_BUILD_PATH` | Working directory for the simulation binary    |
| `--binary-path` | No       | auto-detected    | Path to the FFW binary                         |
| `--description` | No       | —                | Description of the run                         |
| `--run-id`      | No       | —                | Existing run ID to update instead of creating  |

## run_phold

Execute a PHOLD simulation and ingest the results.

```sh
./manage.py run_phold --name "PHOLD Benchmark"
```

Runs the PHOLD binary with the configured parameters and pipes the output through the data ingestion pipeline.

## data_ingest

Create a simulation run and ingest binary result files.

```sh
./manage.py data_ingest \
  --name "My Run" \
  --description "Test run" \
  --simulation-file /path/to/ross.bin \
  --event-file /path/to/events.bin \
  --model-file /path/to/model.bin
```

Creates a `Run` record in the database and kicks off Celery tasks to parse the binary files into queryable database records.
