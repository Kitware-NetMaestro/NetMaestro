#!/bin/bash
# Entrypoint for the django/celery dev containers.
#
# By default, these containers run as the image's built-in `vscode` user (uid/gid 1000:1000). If
# the host user has a different uid/gid, files created in bind mounts end up owned by 1000:1000
# instead of the host user. To avoid this, set NM_USER to match the host user before starting, e.g.
#   NM_USER=$(id -u):$(id -g) docker compose up
#
# Note: VS Code/the Dev Containers CLI's `overrideCommand` replaces this entrypoint entirely with
# their own keep-alive wrapper, so this script never runs for that path; it only applies to `docker
# compose up`/`run` (see README.md).
set -e

if [[ -n "$NM_USER" ]]; then
  nm_uid="${NM_USER%%:*}"
  nm_gid="${NM_USER#*:}"

  if [[ "$(id -u vscode)" != "$nm_uid" ]]; then
    usermod --uid "$nm_uid" vscode
  fi
  if [[ "$(id -g vscode)" != "$nm_gid" ]]; then
    groupmod --gid "$nm_gid" vscode
  fi
  # Named volumes and other files under the home directory were created under the old uid/gid;
  # re-chown them so `vscode` can still read/write them after the uid/gid change.
  chown -R vscode:vscode /home/vscode
fi

exec gosu vscode "$@"
