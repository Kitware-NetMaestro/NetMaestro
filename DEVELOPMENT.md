# Development Guide

This guide covers development setup, testing, and code quality tools for Net Maestro contributors.

## Setup
1. Install [VS Code with dev container support](https://code.visualstudio.com/docs/devcontainers/containers#_installation).
1. Open the project in VS Code, then run `Dev Containers: Reopen in Container`
   from the Command Palette (`Ctrl+Shift+P`).
1. Once the container is ready, open a terminal and run:
   ```sh
   ./manage.py migrate
   ./manage.py createsuperuser
   ```

## Run
Open the **Run and Debug** panel (`Ctrl+Shift+D`) and select a launch configuration:

* **Django: Server** — Starts the development server at http://localhost:8000/
* **Django: Server (eager Celery)** — Same, but Celery tasks run synchronously
  in the web process (useful for debugging task code without a worker)
* **Celery: Worker** — Starts only the Celery worker
* **Django + Celery** — Starts both the server and a Celery worker
* **Django: Management Command** — Pick and run any management command

## Test
Run the full test suite from a terminal: `tox`

Auto-format code: `tox -e format`

Run and debug individual tests from the **Testing** panel (`Ctrl+Shift+;`).

## Rebuild
After changes to the Dockerfile, Docker Compose files, or `devcontainer.json`,
run `Dev Containers: Rebuild Container` from the Command Palette (`Ctrl+Shift+P`).

For dependency changes in `pyproject.toml`, just run `uv sync --all-extras --all-groups`.

## Code Quality with Pre-commit

This project uses pre-commit hooks to enforce code quality standards before commits.

### Initial Setup
1. Run `uv sync` to install dependencies including pre-commit
2. Run `pre-commit install` to install the git hooks

### What Pre-commit Checks
Pre-commit automatically runs the following checks on staged files:
* **File checks**: Large files, merge conflicts, YAML/TOML syntax, trailing whitespace
* **Formatting**: Black (code formatting) and isort (import sorting)
* **Linting**: flake8 with plugins for docstrings, bugbear, quotes, and naming conventions

**Note**: Type checking (mypy) and Django migrations checks are **not** included in pre-commit because they require a full Django environment setup. Run these via tox instead:
* Type checking: `tox -e type`
* Migrations check: `tox -e check-migrations`
* All checks: `tox`

### Usage
Pre-commit hooks run automatically when you commit. If any check fails, the commit is blocked and you'll see which files need fixes.

To manually run pre-commit on all files:
```bash
pre-commit run --all-files
```

To skip pre-commit hooks (not recommended):
```bash
git commit --no-verify
```
