#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec .venv/bin/site-architecture-lab serve "$@"
