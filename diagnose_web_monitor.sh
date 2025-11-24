#!/bin/bash
################################################################################
# Web Monitor Diagnostic Script
# Run this on the Raspberry Pi to diagnose connection issues
################################################################################

echo "=========================================================================="
echo "Pleat Saw Web Monitor Diagnostics"
echo "=========================================================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check 1: Service Status
echo "1. Checking service status..."
if systemctl is-active --quiet pleat-saw; then
    echo -e "${GREEN}✓ Service is running${NC}"
    systemctl status pleat-saw --no-pager | grep -E "Active:|Main PID:"
else
    echo -e "${RED}✗ Service is NOT running${NC}"
    echo "  Starting service..."
    sudo systemctl start pleat-saw
    sleep 3
    if systemctl is-active --quiet pleat-saw; then
        echo -e "${GREEN}✓ Service started successfully${NC}"
    else
        echo -e "${RED}✗ Service failed to start${NC}"
        echo "  View logs: sudo journalctl -u pleat-saw -n 50"
        exit 1
    fi
fi
echo ""

# Check 2: Web Monitor Configuration
echo "2. Checking web monitor configuration..."
if [ -f /home/pi/pleat_saw/config/system.yaml ]; then
    echo "  Configuration file exists"
    if grep -q "web_monitor:" /home/pi/pleat_saw/config/system.yaml; then
        echo -e "${GREEN}✓ web_monitor section found in config${NC}"
        echo "  Settings:"
        grep -A 6 "web_monitor:" /home/pi/pleat_saw/config/system.yaml | sed 's/^/    /'

        # Check if enabled
        if grep -A 6 "web_monitor:" /home/pi/pleat_saw/config/system.yaml | grep -q "enabled: true"; then
            echo -e "${GREEN}✓ Web monitor is enabled${NC}"
        else
            echo -e "${RED}✗ Web monitor is DISABLED${NC}"
            echo "  Enable it by editing /home/pi/pleat_saw/config/system.yaml"
            echo "  Set: web_monitor: enabled: true"
            exit 1
        fi
    else
        echo -e "${RED}✗ web_monitor section NOT found in config${NC}"
        echo "  The config file may be from an older version"
        echo "  Add the following to /home/pi/pleat_saw/config/system.yaml under 'services:':"
        echo ""
        echo "  web_monitor:"
        echo "    enabled: true"
        echo "    port: 5000"
        echo "    host: 0.0.0.0"
        echo "    update_rate_hz: 10"
        echo "    require_auth: false"
        echo "    debug: false"
        exit 1
    fi
else
    echo -e "${RED}✗ Configuration file not found${NC}"
    exit 1
fi
echo ""

# Check 3: Flask Dependencies
echo "3. Checking Flask dependencies..."
if [ -f /home/pi/pleat_saw/venv/bin/pip ]; then
    MISSING_DEPS=0
    for pkg in Flask Flask-SocketIO python-socketio python-engineio eventlet; do
        if /home/pi/pleat_saw/venv/bin/pip list 2>/dev/null | grep -iq "^$pkg "; then
            echo -e "${GREEN}✓ $pkg installed${NC}"
        else
            echo -e "${RED}✗ $pkg NOT installed${NC}"
            MISSING_DEPS=1
        fi
    done

    if [ $MISSING_DEPS -eq 1 ]; then
        echo ""
        echo "Installing missing dependencies..."
        /home/pi/pleat_saw/venv/bin/pip install Flask==3.0.0 Flask-SocketIO==5.3.5 python-socketio==5.10.0 python-engineio==4.8.0 eventlet==0.33.3
        echo "Restarting service..."
        sudo systemctl restart pleat-saw
        sleep 3
    fi
else
    echo -e "${RED}✗ Virtual environment not found${NC}"
    exit 1
fi
echo ""

# Check 4: Port Listening
echo "4. Checking if port 5000 is listening..."
sleep 2  # Give service time to start
if netstat -tuln 2>/dev/null | grep -q ":5000 "; then
    echo -e "${GREEN}✓ Port 5000 is listening${NC}"
    netstat -tuln | grep ":5000 " | sed 's/^/  /'
else
    if ss -tuln 2>/dev/null | grep -q ":5000 "; then
        echo -e "${GREEN}✓ Port 5000 is listening${NC}"
        ss -tuln | grep ":5000 " | sed 's/^/  /'
    else
        echo -e "${RED}✗ Port 5000 is NOT listening${NC}"
        echo "  This means the web server didn't start"
        echo "  Checking logs for errors..."
        echo ""
        sudo journalctl -u pleat-saw -n 30 | grep -i -E "error|exception|web|flask"
        exit 1
    fi
fi
echo ""

# Check 5: Web Files Exist
echo "5. Checking web files exist..."
if [ -d /home/pi/pleat_saw/app/web ]; then
    echo -e "${GREEN}✓ Web directory exists${NC}"
    if [ -f /home/pi/pleat_saw/app/web/templates/dashboard.html ]; then
        echo -e "${GREEN}✓ Dashboard HTML exists${NC}"
    else
        echo -e "${RED}✗ Dashboard HTML missing${NC}"
    fi
    if [ -d /home/pi/pleat_saw/app/web/static ]; then
        echo -e "${GREEN}✓ Static files directory exists${NC}"
    else
        echo -e "${RED}✗ Static files directory missing${NC}"
    fi
else
    echo -e "${RED}✗ Web directory NOT found${NC}"
    echo "  The web monitoring files may not have been installed"
    echo "  Re-run the installer or copy the web directory manually"
    exit 1
fi
echo ""

# Check 6: Local Connection Test
echo "6. Testing local connection..."
if command -v curl &> /dev/null; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" == "200" ]; then
        echo -e "${GREEN}✓ Local connection successful (HTTP $HTTP_CODE)${NC}"
    else
        echo -e "${RED}✗ Local connection failed (HTTP $HTTP_CODE)${NC}"
        if [ "$HTTP_CODE" == "000" ]; then
            echo "  Could not connect to server"
        fi
    fi
else
    echo -e "${YELLOW}⚠ curl not installed, skipping local test${NC}"
fi
echo ""

# Check 7: Network Info
echo "7. Network information..."
IP_ADDR=$(hostname -I | awk '{print $1}')
echo "  Raspberry Pi IP Address: $IP_ADDR"
echo "  Dashboard URL: http://$IP_ADDR:5000"
echo ""

# Check 8: Firewall
echo "8. Checking firewall..."
if command -v ufw &> /dev/null; then
    if ufw status 2>/dev/null | grep -q "Status: active"; then
        echo -e "${YELLOW}⚠ UFW firewall is active${NC}"
        if ufw status | grep -q "5000"; then
            echo -e "${GREEN}✓ Port 5000 is allowed${NC}"
        else
            echo -e "${RED}✗ Port 5000 is NOT allowed${NC}"
            echo "  Run: sudo ufw allow 5000/tcp"
        fi
    else
        echo -e "${GREEN}✓ UFW firewall is inactive${NC}"
    fi
else
    echo "  UFW not installed (firewall may not be active)"
fi
echo ""

# Check 9: Recent Service Logs
echo "9. Recent service logs (last 20 lines)..."
echo "=========================================================================="
sudo journalctl -u pleat-saw -n 20 --no-pager
echo "=========================================================================="
echo ""

# Summary
echo "=========================================================================="
echo "DIAGNOSTIC SUMMARY"
echo "=========================================================================="
echo ""
echo "If the service is running and port 5000 is listening:"
echo "  1. Try accessing from Pi: http://localhost:5000"
echo "  2. Try accessing from network: http://$IP_ADDR:5000"
echo ""
echo "If you can't connect from network computer:"
echo "  • Check firewall on Raspberry Pi"
echo "  • Check firewall on your computer"
echo "  • Verify both devices are on same network"
echo "  • Try pinging the Pi: ping $IP_ADDR"
echo ""
echo "To view live logs:"
echo "  sudo journalctl -u pleat-saw -f"
echo ""
echo "To restart service:"
echo "  sudo systemctl restart pleat-saw"
echo ""
echo "To check detailed Python errors:"
echo "  sudo journalctl -u pleat-saw -n 100 | grep -A 10 'Traceback'"
echo ""
