# Net Maestro

## Develop with Docker (recommended quickstart)
This is the simplest configuration for developers to start with.

### Initial Setup
1. Run `docker compose run --rm django ./manage.py migrate`
2. Run `docker compose run --rm django ./manage.py createsuperuser`
   and follow the prompts to create your own user

### Run Application
1. Run `docker compose up`
2. Access the site, starting at <http://localhost:8000/admin/>
3. When finished, use `Ctrl+C`

### Using your own data
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

Notes:

- The `:ro` mount is recommended so the app can't accidentally modify your input data.
- If you use Option 2 or 3, you must keep the `/host_data` mount present when running the app,
  because the symlinks created in `data/` point into `/host_data`.

### Maintenance
To non-destructively update your development stack at any time:
1. Run `docker compose down`
2. Run `docker compose pull`
3. Run `docker compose build --pull`
4. Run `docker compose run --rm django ./manage.py migrate`

### Destruction
1. Run `docker compose down -v`

## Develop Natively (advanced)
This configuration still uses Docker to run attached services in the background,
but allows developers to run Python code on their native system.

### Initial Setup
1. Run `docker compose -f ./docker-compose.yml up -d`
2. [Install `uv`](https://docs.astral.sh/uv/getting-started/installation/)
3. Run `export UV_ENV_FILE=./dev/.env.docker-compose-native`
4. Run `./manage.py migrate`
5. Run `./manage.py createsuperuser` and follow the prompts to create your own user

### Run Application
1. Ensure `docker compose -f ./docker-compose.yml up -d` is still active
2. Run `export UV_ENV_FILE=./dev/.env.docker-compose-native`
3. Run: `./manage.py runserver_plus`
4. Run in a separate terminal: `uv run celery --app net_maestro.celery worker --loglevel INFO --without-heartbeat`
5. When finished, run `docker compose stop`

## Testing
### Initial Setup
tox is used to manage the execution of all tests.
[Install `uv`](https://docs.astral.sh/uv/getting-started/installation/) and run tox with
`uv run tox ...`.

When running the "Develop with Docker" configuration, all tox commands must be run as
`docker compose run --rm django uv run tox`; extra arguments may also be appended to this form.

### Running Tests
Run `uv run tox` to launch the full test suite.

Individual test environments may be selectively run.
This also allows additional options to be be added.
Useful sub-commands include:
* `uv run tox -e lint`: Run only the style checks
* `uv run tox -e type`: Run only the type checks
* `uv run tox -e test`: Run only the pytest-driven tests

To automatically reformat all code to comply with
some (but not all) of the style checks, run `uv run tox -e format`.
