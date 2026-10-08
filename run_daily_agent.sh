#!/usr/bin/env bash

set -euo pipefail

# cd to project
cd "$(dirname "$0")"

# Run the agent
exec .venv/bin/python main.py >> logs/runs.log 2>&1
