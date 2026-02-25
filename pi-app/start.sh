#!/usr/bin/env bash
# Resistor Station launcher — called by systemd on boot
# Sets environment for Pygame on the Pi touchscreen, then runs main.py

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

# Framebuffer display (no X11 needed)
export SDL_VIDEODRIVER=kmsdrm
export SDL_FBDEV=/dev/fb0

# Hide mouse cursor on touchscreen
export SDL_NOMOUSE=1

# Use the Pi's touchscreen input
export SDL_MOUSEDEV=/dev/input/touchscreen

# Ensure shared/ is importable
export PYTHONPATH="$APP_DIR:$APP_DIR/../shared:${PYTHONPATH:-}"

exec python3 main.py
