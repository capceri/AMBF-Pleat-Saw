#!/bin/bash
# Setup script for Pleat Saw HMI auto-start on boot
# Run this script on the Raspberry Pi to configure kiosk mode

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "========================================="
echo "Pleat Saw HMI Autostart Configuration"
echo "========================================="
echo ""

# Check if running as user (not root)
if [ "$EUID" -eq 0 ]; then
    echo "ERROR: Do not run this script as root/sudo"
    echo "Run as the user who will use the kiosk: ./setup_autostart.sh"
    exit 1
fi

# Install required packages
echo "Installing required packages..."
sudo apt-get update
sudo apt-get install -y chromium-browser unclutter x11-xserver-utils

# Create autostart directory if it doesn't exist
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

# Make the kiosk script executable
chmod +x "$SCRIPT_DIR/start_kiosk.sh"

# Create desktop entry for autostart
echo "Creating autostart desktop entry..."
cat > "$AUTOSTART_DIR/pleat-saw-kiosk.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Pleat Saw HMI Kiosk
Comment=Auto-start Pleat Saw operator interface in kiosk mode
Exec=$SCRIPT_DIR/start_kiosk.sh
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
EOF

echo ""
echo "✓ Autostart configuration complete!"
echo ""
echo "The Pleat Saw HMI will now launch automatically on boot."
echo "The operator screen will open in fullscreen kiosk mode."
echo ""
echo "Navigation:"
echo "  • Main screen: http://localhost:5000/"
echo "  • Engineering: Click 'ENG' button"
echo "  • Manual: From Engineering page"
echo ""
echo "To disable autostart, delete:"
echo "  $AUTOSTART_DIR/pleat-saw-kiosk.desktop"
echo ""
echo "To exit kiosk mode: Alt+F4 or Ctrl+W"
echo ""
