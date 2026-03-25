# Net Maestro

Net Maestro is a web-based application for analyzing and visualizing network simulation data from PDES (Parallel Discrete Event Simulation) engines.

## Quick Start

### Running the Application

1. Clone the repository: `git clone https://github.com/NetMaestro/NetMaestro.git`
2. Navigate to the NetMaestro directory: `cd {path}/{to}/NetMaestro`
3. Open the project in VS Code, then run `Dev Containers: Reopen in Container`
   from the Command Palette (`Ctrl+Shift+P`).
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

#### Copy files into `NetMaestro/data/`
Copy your files into the appropriate subdirectory under `NetMaestro/data/`.

Docker already mounts the repo into the container. Files will be immediately available to the app.

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
