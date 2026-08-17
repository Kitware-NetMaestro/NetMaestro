# Net Maestro

Net Maestro is a web-based application for analyzing and visualizing network simulation data from PDES (Parallel Discrete Event Simulation) engines.

## Quick Start

### Running the Application

#### Option A (recommended): Dev Containers (VS Code)

1. Clone the repository: `git clone https://github.com/NetMaestro/NetMaestro.git`
2. Navigate to the NetMaestro directory: `cd {path}/{to}/NetMaestro`
3. Open the project in VS Code, then run `Dev Containers: Reopen in Container` from the Command Palette (`Ctrl+Shift+P`).
4. Access the site at <http://localhost:8000>
5. When finished, use `docker compose down`

#### Option B: Dev Containers CLI (No VS Code)

If you'd rather use the dev container without installing VS Code, use the [Dev Containers CLI](https://github.com/devcontainers/cli):

1. Install the CLI: `npm install -g @devcontainers/cli`
2. Build and start the dev container from the `NetMaestro` directory:
   ```sh
   devcontainer up --workspace-folder . --forward-port 8000
   ```
3. Run commands inside the container (equivalent to a VS Code terminal):
   ```sh
   devcontainer exec --workspace-folder . ./manage.py migrate
   devcontainer exec --workspace-folder . ./manage.py createsuperuser
   devcontainer exec --workspace-folder . ./manage.py runserver_plus 0.0.0.0:8000
   ```
4. Access the site at <http://localhost:8000>
5. When finished, use `docker compose down`

#### Option C: Plain Docker Compose

1. Clone the repository: `git clone https://github.com/NetMaestro/NetMaestro.git`
2. Navigate to the NetMaestro directory: `cd {path}/{to}/NetMaestro`
3. Start the containers, setting `NM_USER` to your host uid/gid:
   ```sh
   NM_USER=$(id -u):$(id -g) docker compose up
   ```
4. Run commands against the `django` container (`NM_USER` is needed here too):
   ```sh
   NM_USER=$(id -u):$(id -g) docker compose run --rm django ./manage.py migrate
   NM_USER=$(id -u):$(id -g) docker compose run --rm django ./manage.py createsuperuser
   ```
5. Access the site at <http://localhost:8000>
6. When finished, use `docker compose down`

### ⚠️ Caution

If you run Net Maestro with plain `docker compose up`, files it creates - like your data files - may end up owned by the wrong user, which can require extra steps (`sudo`) to fix later.

The fix (option C above) is a single environment variable: `NM_USER=$(id -u):$(id -g) docker compose up`.

If you use VS Code or the Dev Containers CLI instead (Options B and C below), this is handled for you automatically - no action needed.

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
