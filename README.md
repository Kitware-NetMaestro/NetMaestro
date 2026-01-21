# Net Maestro

Net Maestro is a web-based application for analyzing and visualizing network simulation data from PDES (Parallel Discrete Event Simulation) engines.

## Quick Start

### Running the Application

1. Clone the repository: `git clone https://github.com/NetMaestro/NetMaestro.git`
2. Navigate to the NetMaestro directory: `cd {path}/{to}/NetMaestro`
3. Run `docker compose up -d`
4. Access the site at <http://localhost:8000>
5. When finished, use `docker compose down`

### Using Your Own Data
Net Maestro reads binary files from the Django project's `data/` directory:

```
data/
  events/
  models/
  simulations/
```

There are three supported ways to provide your own data, depending on which best supports your workflow.

#### Option 1: Copy files into `NetMaestro/data/` (least effort, most data movement)
Copy your files into the appropriate subdirectory under `NetMaestro/data/`.

This is the simplest approach because Docker already mounts the repo into the container. Files will be immediately available to the app.

#### Option 2: Mount a structured data directory and auto-ingest symlinks (slightly more effort, minimal data movement)
If you have a host directory that already follows the expected structure:

```
/absolute/path/to/your/data/
  events/
  models/
  simulations/
```

1. Create a Compose override file (for example `docker-compose.data.yml`) containing:

```yaml
services:
  django:
    volumes:
      - /absolute/path/to/your/data:/host_data:ro
```

2. Run ingest once to create symlinks under `NetMaestro/data/`:

```
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.data.yml \
  run --rm django ./manage.py data_ingest --source-root /host_data
```

3. Start the app with the same override mounted:

```
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.data.yml up
```

#### Option 3: Mount a data directory and ingest explicit file mappings (most effort, least data movement)
If your files are not organized into `events/`, `models/`, `simulations/`, you can still mount a
directory and provide an explicit mapping when running `data_ingest`.

1. Create a Compose override file (for example `docker-compose.data.yml`) containing:

```yaml
services:
  django:
    volumes:
      - /absolute/path/to/your/data:/host_data:ro
```

2. Run ingest with explicit mappings (flags can be repeated):

```
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.data.yml \
  run --rm django ./manage.py data_ingest \
  --event-file /host_data/path/to/event.bin \
  --event-file /host_data/path/to/another-event.bin \
  --simulation-file /host_data/path/to/sim.bin \
  --model-file /host_data/path/to/model.bin
```

3. Start the app with the same override mounted:

```
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.data.yml up
```

**Notes:**
- The `:ro` mount is recommended so the app can't accidentally modify your input data.
- If you use Option 2 or 3, you must keep the `/host_data` mount present when running the app,
  because the symlinks created in `data/` point into `/host_data`.

## Features

- **Data Visualization**: Interactive plots and graphs for network simulation analysis
- **Multiple Data Formats**: Support for event, model, and simulation binary files
- **Flexible Data Loading**: Multiple options for providing your own data files
- **Web-Based Interface**: Access from any browser

## Requirements

- Docker and Docker Compose
- Binary data files from PDES simulation engines (ROSS/CODES, etc.)

## Contributing

Contributions are welcome! See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup, testing, and code quality guidelines.

## License

Apache 2.0 - See LICENSE and NOTICE files for details.
