#!/usr/bin/env bash
# Install the Resistor Station systemd service on the Pi.
# Run once:  sudo bash install-service.sh

set -euo pipefail

SERVICE_SRC="$(cd "$(dirname "$0")" && pwd)/resistor-station.service"
SERVICE_DST="/etc/systemd/system/resistor-station.service"

echo "Installing service..."
cp "$SERVICE_SRC" "$SERVICE_DST"

echo "Reloading systemd..."
systemctl daemon-reload

echo "Enabling service (starts on boot)..."
systemctl enable resistor-station.service

echo "Starting service now..."
systemctl start resistor-station.service

echo ""
echo "Done! The app will now start on every boot."
echo ""
echo "Useful commands:"
echo "  sudo systemctl status resistor-station   # check status"
echo "  sudo journalctl -u resistor-station -f    # live logs"
echo "  sudo systemctl restart resistor-station   # restart"
echo "  sudo systemctl stop resistor-station      # stop"
echo "  sudo systemctl disable resistor-station   # disable auto-start"
