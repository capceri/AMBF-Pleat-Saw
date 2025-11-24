#!/bin/bash
################################################################################
# Fix for Python 3.13 Compatibility Issue
# This script fixes the eventlet incompatibility with Python 3.13
################################################################################

echo "=========================================================================="
echo "Fixing Python 3.13 Compatibility (Eventlet → Threading)"
echo "=========================================================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect user
if [ -n "$SUDO_USER" ]; then
    USER="$SUDO_USER"
else
    USER=$(whoami)
fi

INSTALL_DIR="/home/$USER/pleat_saw"

echo "User: $USER"
echo "Install Directory: $INSTALL_DIR"
echo ""

# Step 1: Stop service
echo "1. Stopping pleat-saw service..."
sudo systemctl stop pleat-saw
echo -e "${GREEN}✓ Service stopped${NC}"
echo ""

# Step 2: Update web_monitor.py
echo "2. Updating web_monitor.py..."
WEB_MONITOR="$INSTALL_DIR/app/services/web_monitor.py"

if [ -f "$WEB_MONITOR" ]; then
    # Remove eventlet import and monkey patch
    sed -i 's/^import eventlet$/# import eventlet  # Not compatible with Python 3.13/' "$WEB_MONITOR"
    sed -i 's/^eventlet.monkey_patch()$/# eventlet.monkey_patch()  # Not needed with threading mode/' "$WEB_MONITOR"

    # Change async_mode from eventlet to threading
    sed -i "s/async_mode='eventlet'/async_mode='threading'/" "$WEB_MONITOR"

    echo -e "${GREEN}✓ web_monitor.py updated${NC}"
else
    echo -e "${RED}✗ web_monitor.py not found${NC}"
    exit 1
fi
echo ""

# Step 3: Uninstall eventlet
echo "3. Removing eventlet (incompatible with Python 3.13)..."
cd "$INSTALL_DIR"
source venv/bin/activate
pip uninstall -y eventlet
deactivate
echo -e "${GREEN}✓ Eventlet removed${NC}"
echo ""

# Step 4: Install simple-websocket (Python 3.13 compatible)
echo "4. Installing simple-websocket (Python 3.13 compatible)..."
source venv/bin/activate
pip install simple-websocket==1.0.0
deactivate
echo -e "${GREEN}✓ simple-websocket installed${NC}"
echo ""

# Step 5: Verify Flask-SocketIO
echo "5. Verifying Flask-SocketIO installation..."
source venv/bin/activate
if pip list | grep -q "Flask-SocketIO"; then
    echo -e "${GREEN}✓ Flask-SocketIO installed${NC}"
else
    echo "Installing Flask-SocketIO..."
    pip install Flask==3.0.0 Flask-SocketIO==5.3.5 python-socketio==5.10.0 python-engineio==4.8.0
    echo -e "${GREEN}✓ Flask packages installed${NC}"
fi
deactivate
echo ""

# Step 6: Start service
echo "6. Starting pleat-saw service..."
sudo systemctl start pleat-saw
sleep 3
echo ""

# Step 7: Check status
echo "7. Checking service status..."
if systemctl is-active --quiet pleat-saw; then
    echo -e "${GREEN}✓ Service is running!${NC}"
    systemctl status pleat-saw --no-pager | grep -E "Active:|Main PID:"
    echo ""

    # Get IP address
    IP_ADDR=$(hostname -I | awk '{print $1}')
    echo -e "${GREEN}=========================================================================="
    echo "SUCCESS! Web dashboard should now be accessible at:"
    echo ""
    echo "  http://$IP_ADDR:5000"
    echo ""
    echo "==========================================================================${NC}"
else
    echo -e "${RED}✗ Service failed to start${NC}"
    echo ""
    echo "Checking logs for errors..."
    sudo journalctl -u pleat-saw -n 30
    exit 1
fi
echo ""

echo "Fix complete!"
