# Developers

## Local Development Setup

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [VS Code](https://code.visualstudio.com/) with [Dev Containers](https://code.visualstudio.com/docs/devcontainers/containers#_installation) support (recommended)

### Getting Started

**Option 1: VS Code Dev Container (recommended)**

1. Open the project in VS Code
2. Run `Dev Containers: Reopen in Container` from the Command Palette (`Ctrl+Shift+P`)
3. Once the container is ready, open a terminal and run:
   ```sh
   ./manage.py migrate
   ./manage.py createsuperuser
   ```

**Option 2: Docker Compose**

```sh
docker compose up -d
docker compose run --rm django uv run python manage.py migrate
docker compose run --rm django uv run python manage.py createsuperuser
```

### Services

The application runs as a set of Docker Compose services:

| Service      | Purpose                          | Port  |
|-------------|----------------------------------|-------|
| **django**   | Django development server        | 8000  |
| **celery**   | Celery async task worker         | —     |
| **postgres** | PostgreSQL database              | 5432  |
| **rabbitmq** | Message broker for Celery        | 5672  |
| **minio**    | S3-compatible object storage     | 9000  |

### Running the Server

From VS Code, use the **Run and Debug** panel (`Ctrl+Shift+D`):

- **Django: Server** — starts at http://localhost:8000/
- **Django: Server (eager Celery)** — Celery tasks run synchronously (useful for debugging)
- **Celery: Worker** — starts only the Celery worker
- **Django + Celery** — starts both
- **Django: Management Command** — pick and run any management command

### Rebuilding

After changes to Dockerfiles or `devcontainer.json`, run `Dev Containers: Rebuild Container`.

For dependency changes in `pyproject.toml`, run `uv sync --all-extras --all-groups`.

## Testing & Linting

All checks run via [tox](https://tox.wiki/), which manages isolated environments automatically.

### Running Everything

```sh
# Inside the dev container or via Docker:
tox

# Or via Docker Compose:
docker compose run --rm django uv run tox
```

### Individual Environments

| Environment          | Command                | What it does                        |
|---------------------|------------------------|-------------------------------------|
| **lint**            | `tox -e lint`          | Ruff linting + format check         |
| **format**          | `tox -e format`        | Auto-fix lint issues + reformat     |
| **type**            | `tox -e type`          | Mypy type checking                  |
| **test**            | `tox -e test`          | Pytest test suite                   |
| **check-migrations**| `tox -e check-migrations` | Verify no missing migrations     |

### Running Specific Tests

```sh
# Run tests matching a pattern:
tox -e test -- -k "test_component"

# Run a single test file:
tox -e test -- net_maestro/core/tests/test_component_views.py

# Verbose output:
tox -e test -- -v
```

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`. They check:

- File hygiene (large files, merge conflicts, trailing whitespace)
- Ruff linting and formatting
- YAML/TOML syntax

To run manually: `pre-commit run --all-files`

## Architecture Overview

### Project Structure

```
net_maestro/
├── core/
│   ├── admin/              # Django admin configuration
│   ├── base_models.py      # Base component model registry (TypedDict definitions)
│   ├── constants.py        # Shared enums (RunStatus, ModelType, etc.)
│   ├── forms.py            # Django forms (ComponentModelForm, PHOLDSimulationForm)
│   ├── management/
│   │   └── commands/       # Management commands
│   │       ├── data_ingest.py      # Ingest binary result files
│   │       ├── ingest_topology.py  # Import topology YAML + create components
│   │       ├── run_ffw.py          # Execute FFW simulation
│   │       └── run_phold.py        # Execute PHOLD simulation
│   ├── models/             # Django ORM models
│   │   ├── component_model.py  # Custom component presets
│   │   ├── run.py              # Simulation runs
│   │   └── ...                 # Event/model/simulation file records
│   ├── parsers/            # Binary and CSV file parsers
│   ├── rest/               # DRF API views
│   │   ├── component_api.py    # GET /api/v1/component-models/
│   │   ├── run_api.py          # Run data endpoints
│   │   └── topology_api.py     # Topology CRUD
│   ├── services/           # Business logic (simulation execution)
│   │   └── ffw.py              # FFW binary execution and result handling
│   ├── simulation_models.py    # Simulation model registry (FFW, PHOLD, etc.)
│   ├── tasks/              # Celery async tasks (PHOLD, FFW)
│   ├── templates/          # Django/HTMX templates
│   ├── tests/              # Pytest test suite
│   ├── topology.py         # Topology YAML parsing and storage
│   └── views.py            # Page views and form handlers
├── settings/               # Django settings (base, development, testing)
└── urls.py                 # URL routing
```

### Key Concepts

**Base Model Registry** (`base_models.py`): Defines the available LP types that users can create custom components from. Each entry specifies the component type, engine, parameters (with types, units, and validation ranges), and whether it's currently enabled.

**Simulation Models** (`simulation_models.py`): The top-level simulation model registry shown on the Available Models page. Each simulation model (e.g., Fluid Flow WAN, PHOLD) maps to one or more base component models and links to its workflow entry point.

**Component Models** (`models/component_model.py`): User-created presets derived from a base model. For example, a "Core WAN Switch" component with `switch_buffer=64` and `terminal_bandwidth=100` is a preset of the `fluid-flow-wan-switch-lp` base model.

**Topologies** (`topology.py`): FFW topology YAML files representing switch/link configurations. Stored as files in `settings.TOPOLOGY_DIR` and parsed into `Topology`/`Switch`/`Link` dataclasses. The topology editor reads and writes these files through a REST API.

**Services** (`services/`): Business logic for simulation execution. The FFW service (`services/ffw.py`) handles running the CODES binary via MPI, managing working directories, and coordinating result ingestion.

**Parsers** (`parsers/`): Convert simulation output files into the columnar format the visualization layer expects. Includes parsers for ROSS binary stats and FFW CSV logs (terminal events, switch events, fluid segments).

### Frontend Stack

The UI is built with:

- **Django templates + HTMX** for page navigation and partial updates
- **Alpine.js** for reactive form behavior (base model selection, parameter rendering)
- **Cytoscape.js** for topology graph visualization
- **DaisyUI + Tailwind CSS** for styling

### API Endpoints

| Endpoint                                    | Method | Purpose                              |
|--------------------------------------------|--------|--------------------------------------|
| `/api/v1/component-models/`               | GET    | List custom components (filterable)  |
| `/api/v1/runs/<id>/ross`                  | GET    | ROSS simulation PE records           |
| `/api/v1/runs/<id>/event`                 | GET    | Event trace records                  |
| `/api/v1/runs/<id>/model`                 | GET    | Model statistics records             |
| `/api/v1/topologies`                      | POST   | Create a new topology                |
| `/api/v1/topologies/<name>`               | GET    | Get topology details                 |
| `/api/v1/topologies/<name>/simulation-inputs` | GET | LP counts for simulation config  |
