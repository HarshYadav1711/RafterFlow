#!/bin/sh
# Compatibility wrapper; Dockerfile uses scripts/docker_entrypoint.py.
set -eu
exec python scripts/docker_entrypoint.py
