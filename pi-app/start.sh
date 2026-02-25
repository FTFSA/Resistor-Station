#!/usr/bin/env bash
# Resistor Station launcher — called by systemd on boot
# Sets environment for Pygame on the Pi touchscreen, then runs main.py

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

# X11 display (Pi desktop environment)
export DISPLAY=:0
export XAUTHORITY=/home/azmeares/.Xauthority

# Activate the project virtual environment
source "$APP_DIR/../venv/bin/activate"

# Ensure shared/ is importable
export PYTHONPATH="$APP_DIR:$APP_DIR/../shared:${PYTHONPATH:-}"

exec python3 main.py
