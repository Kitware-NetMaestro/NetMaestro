# Pin to a specific ROSS commit for reproducible builds.
ARG ROSS_GIT_REF=dc3a6a056cfc7a5e68f7141f88d8833407599ef8

FROM ubuntu:24.04 AS ross-builder
ARG ROSS_GIT_REF

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    build-essential \
    cmake \
    openmpi-bin \
    libmpich-dev \
    libopenmpi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/ross-org/ross.git /ross \
    && cd /ross \
    && git checkout "${ROSS_GIT_REF}" \
    && git submodule update --init --recursive

RUN cmake -S /ross -B /ross/build \
        -DCMAKE_BUILD_TYPE=Release \
        -DROSS_BUILD_MODELS=ON \
        -DROSS_BUILD_TESTING=OFF \
    && cmake --build /ross/build --parallel


FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

# OpenMPI runtime, matching the ross-builder stage, for running the PHOLD binary.
RUN sudo apt-get update && sudo apt-get install -y \
    openmpi-bin \
    && sudo apt-get clean && sudo rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# PHOLD binary built in the ross-builder stage above. Baked into the image instead
# of relying on a host `ross` checkout bind-mounted at runtime.
COPY --from=ross-builder --chown=vscode:vscode /ross/build/models/phold/phold /opt/ross/phold

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

RUN ["chsh", "-s", "/usr/bin/zsh", "vscode"]

USER vscode

# Pre-create named volume mount points, so the new volume inherits `vscode` user ownership:
# https://docs.docker.com/engine/storage/volumes/#populate-a-volume-using-a-container
RUN ["mkdir", "/home/vscode/pkg-cache"]
