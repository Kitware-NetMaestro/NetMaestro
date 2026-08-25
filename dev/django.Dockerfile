FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

# Install OpenMPI for simulations
RUN sudo apt-get update && sudo apt-get install -y \
    openmpi-bin \
    libopenmpi-dev \
    && sudo apt-get clean && sudo rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Ensure Python output appears immediately in container logs.
ENV PYTHONUNBUFFERED=1

# Override Node's default of attempting to bind to IPv6 interfaces over IPv4
ENV NODE_OPTIONS=--dns-result-order=ipv4first

# Put the uv and npm caches in a separate location,
# where they can persist and be shared across containers.
# The uv cache and virtual environment are on different volumes, so hardlinks won't work.
ENV UV_CACHE_DIR=/home/vscode/pkg-cache/uv \
  UV_PYTHON_INSTALL_DIR=/home/vscode/pkg-cache/uv-python \
  UV_LINK_MODE=symlink \
  NPM_CONFIG_CACHE=/home/vscode/pkg-cache/npm

# Put the virtual environment outside the project directory,
# to improve performance on macOS and prevent accidental usage from the host machine.
# Activate it, so `uv run` doesn't need to be prefixed.
ENV UV_PROJECT_ENVIRONMENT=/home/vscode/venv \
  PATH="/home/vscode/venv/bin:$PATH"

# Put tool scratch files outside the project directory too.
ENV TOX_WORK_DIR=/home/vscode/tox \
  RUFF_CACHE_DIR=/home/vscode/.cache/ruff \
  MYPY_CACHE_DIR=/home/vscode/.cache/mypy

# Match the container's vscode user to the host user's uid/gid, so bind-mounted
# files created in the container are owned by the host user. Values come from
# USER_UID/USER_GID build args (see docker-compose.override.yml), which default
# to the base image's own vscode uid/gid, making this a no-op by default.
ARG USER_UID=1000
ARG USER_GID=1000
RUN if [ "$USER_UID" != "1000" ] || [ "$USER_GID" != "1000" ]; then \
      groupmod --gid "$USER_GID" vscode && \
      usermod --uid "$USER_UID" --gid "$USER_GID" vscode && \
      chown --recursive vscode:vscode /home/vscode; \
    fi

RUN ["chsh", "-s", "/usr/bin/zsh", "vscode"]

USER vscode

# Pre-create named volume mount points, so the new volume inherits `vscode` user ownership:
# https://docs.docker.com/engine/storage/volumes/#populate-a-volume-using-a-container
RUN ["mkdir", "/home/vscode/pkg-cache"]
