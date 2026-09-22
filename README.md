# Net Maestro

Net Maestro is a web-based digital twin framework for research wide-area networks. It integrates PDES simulation engines (ROSS, CODES) with an interactive workflow for configuring network topologies, running simulations, and visualizing results.

## Quick Start

### Running the Application

1. Clone the repository: `git clone https://github.com/NetMaestro/NetMaestro.git`
2. Navigate to the NetMaestro directory: `cd {path}/{to}/NetMaestro`
3. Open the project in VS Code, then run `Dev Containers: Reopen in Container`
   from the Command Palette (`Ctrl+Shift+P`).
4. Access the site at <http://localhost:8000>
5. When finished, use `docker compose down`

## Features

- **Simulation Model Selection**: Choose from available models (Fluid Flow WAN, PHOLD) with guided workflows
- **Custom Components**: Create reusable switch presets with specific buffer and bandwidth configurations
- **Topology Editor**: Build and edit network topologies with a Cytoscape.js graph editor
- **Simulation Execution**: Configure and run simulations via the UI or CLI, with async Celery task processing
- **Data Visualization**: Interactive plots (time-series, heatmaps, scatter plots, parallel coordinates) for simulation analysis
- **Topology Ingestion**: Import external topology YAML files and auto-create matching switch components

## Populating with Data

The quickest way to get simulation data into the application is through the CLI. This example walks through the full Fluid Flow WAN workflow.

### 1. Ingest a topology

Import one of the bundled preset topologies (or your own YAML file). This makes it available in the topology dropdown and creates custom switch components for each unique switch configuration:

```sh
./manage.py ingest_topology data/topologies/fluid-flow-wan-3-switch.yaml
```

### 2. Run a simulation

Execute the FFW model against the ingested topology:

```sh
./manage.py run_ffw \
  --name "FFW 3-switch run" \
  --np 3 \
  --sync 3 \
  --config-path data/topologies/fluid-flow-wan-3-switch.yaml
```

The simulation runs asynchronously via Celery. Once complete, the run and its parsed results appear on the Analysis page.

### 3. View results

Open http://localhost:8000, navigate to the Analysis page, and select the run to explore the visualizations.

For more detail on each command, see the [CLI Reference](docs/cli-reference.md).

## Requirements

- [VS Code with dev container support](https://code.visualstudio.com/docs/devcontainers/containers#_installation)

## Documentation

- [UI Workflow](docs/ui-workflow.md) — walkthrough of the application from model selection to results
- [CLI Reference](docs/cli-reference.md) — management commands for topology ingestion and simulation execution
- [Developers](docs/developers.md) — local setup, testing, and architecture overview

## Contributing

Contributions are welcome! See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup, testing, and code quality guidelines.

## License

Apache 2.0 - See LICENSE and NOTICE files for details.
