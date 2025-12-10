# Web Monitor Connection Troubleshooting Guide

## Quick Diagnostic Steps

### Step 1: Run Diagnostic Script (Recommended)

On the Raspberry Pi, run:

```bash
cd /home/pi/pleat_saw
bash diagnose_web_monitor.sh
```

This will automatically check all common issues and provide specific guidance.

---

## Manual Troubleshooting

### Issue 1: Service Not Running

**Check service status:**
```bash
sudo systemctl status pleat-saw
```

**Expected:** "Active: active (running)"

**If NOT running:**
```bash
# Start the service
sudo systemctl start pleat-saw

# Check for errors
sudo journalctl -u pleat-saw -n 50
```

**Common errors:**
- **ModuleNotFoundError: No module named 'flask'** → Flask not installed
- **Permission denied** → File permissions issue
- **Config file errors** → YAML syntax error

---

### Issue 2: Flask Dependencies Missing

**Check if Flask is installed:**
```bash
/home/pi/pleat_saw/venv/bin/pip list | grep -i flask
```

**Should show:**
- Flask
- Flask-SocketIO
- python-socketio
- python-engineio
- eventlet

**If missing, install:**
```bash
cd /home/pi/pleat_saw
source venv/bin/activate
pip install Flask==3.0.0 Flask-SocketIO==5.3.5 python-socketio==5.10.0 python-engineio==4.8.0 eventlet==0.33.3
deactivate

# Restart service
sudo systemctl restart pleat-saw
```

---

### Issue 3: Web Monitor Not Enabled in Config

**Check configuration:**
```bash
grep -A 6 "web_monitor:" /home/pi/pleat_saw/config/system.yaml
```

**Should show:**
```yaml
web_monitor:
  enabled: true
  port: 5000
  host: 0.0.0.0
  update_rate_hz: 10
  require_auth: false
  debug: false
```

**If `enabled: false` or section missing:**
```bash
nano /home/pi/pleat_saw/config/system.yaml
```

Add or change to `enabled: true`, then:
```bash
sudo systemctl restart pleat-saw
```

---

### Issue 4: Port 5000 Not Listening

**Check if port is listening:**
```bash
sudo netstat -tuln | grep 5000
# OR
sudo ss -tuln | grep 5000
```

**Expected output:**
```
tcp  0  0  0.0.0.0:5000  0.0.0.0:*  LISTEN
```

**If NOT listening:**

1. **Check service logs for errors:**
   ```bash
   sudo journalctl -u pleat-saw -n 50 | grep -i -E "web|flask|error"
   ```

2. **Look for Python exceptions:**
   ```bash
   sudo journalctl -u pleat-saw -n 100 | grep -A 10 "Traceback"
   ```

3. **Common issues:**
   - Port already in use by another service
   - Web monitor files missing
   - Python import errors

---

### Issue 5: Web Files Missing

**Check web directory exists:**
```bash
ls -la /home/pi/pleat_saw/app/web/
```

**Should show:**
```
templates/
static/
```

**Check critical files:**
```bash
ls -la /home/pi/pleat_saw/app/web/templates/dashboard.html
ls -la /home/pi/pleat_saw/app/web/static/css/dashboard.css
ls -la /home/pi/pleat_saw/app/web/static/js/dashboard.js
ls -la /home/pi/pleat_saw/app/services/web_monitor.py
```

**If files missing:**

The web monitoring files weren't installed. You need to:

1. **Copy web directory from source:**
   ```bash
   # From your development machine
   scp -r /path/to/pleat_saw/app/web pi@<pi-ip>:/home/pi/pleat_saw/app/
   scp /path/to/pleat_saw/app/services/web_monitor.py pi@<pi-ip>:/home/pi/pleat_saw/app/services/
   ```

2. **Fix permissions:**
   ```bash
   sudo chown -R pi:pi /home/pi/pleat_saw
   ```

3. **Restart service:**
   ```bash
   sudo systemctl restart pleat-saw
   ```

---

### Issue 6: Firewall Blocking Port 5000

**Check if UFW firewall is active:**
```bash
sudo ufw status
```

**If active and port 5000 not allowed:**
```bash
sudo ufw allow 5000/tcp
sudo ufw reload
```

**Test connection again**

---

### Issue 7: Can Connect Locally but Not from Network

**If this works:**
```bash
curl http://localhost:5000
```

**But this doesn't work from another computer:**
- Browser to `http://<pi-ip>:5000`

**Possible causes:**

1. **Host binding issue** - Check config:
   ```bash
   grep "host:" /home/pi/pleat_saw/config/system.yaml
   ```

   Should be: `host: 0.0.0.0` (not `127.0.0.1`)

2. **Network firewall** - Check if your computer can reach the Pi:
   ```bash
   ping <pi-ip-address>
   ```

3. **Network isolation** - Ensure Pi and your computer are on same network

4. **Router firewall** - Some routers block inter-device communication

---

### Issue 8: Getting HTTP 404 Error

**Symptoms:** Page loads but shows "404 Not Found"

**Cause:** Dashboard template file missing or Flask can't find it

**Fix:**
```bash
# Verify template exists
ls -la /home/pi/pleat_saw/app/web/templates/dashboard.html

# If missing, copy from source
# If present, check Flask template path in web_monitor.py

# Check logs for template errors
sudo journalctl -u pleat-saw -n 50 | grep -i template
```

---

### Issue 9: Getting HTTP 500 Error

**Symptoms:** Page tries to load but shows "500 Internal Server Error"

**Cause:** Python exception in Flask app

**Fix:**
```bash
# View detailed error
sudo journalctl -u pleat-saw -n 100 | grep -A 20 "Traceback"

# Common issues:
# - Missing Python dependencies
# - Error in web_monitor.py
# - Config file issue
```

---

### Issue 10: Connection Drops / Red "Disconnected" Indicator

**Symptoms:** Dashboard loads but shows red "Disconnected" in header

**Cause:** WebSocket connection failing

**Fix:**

1. **Check browser console (F12 → Console):**
   - Look for WebSocket errors
   - Check for CORS errors

2. **Verify Flask-SocketIO installed:**
   ```bash
   /home/pi/pleat_saw/venv/bin/pip list | grep -i socketio
   ```

3. **Check service logs:**
   ```bash
   sudo journalctl -u pleat-saw -f
   # Look for WebSocket connection messages
   ```

4. **Restart service:**
   ```bash
   sudo systemctl restart pleat-saw
   # Refresh browser page
   ```

---

## Complete Reinstall (Last Resort)

If nothing else works, reinstall with web monitoring:

```bash
# Stop service
sudo systemctl stop pleat-saw

# Backup current config
cp -r /home/pi/pleat_saw/config ~/pleat_saw_config_backup

# Remove old installation
sudo rm -rf /home/pi/pleat_saw

# Transfer new version from your computer
# (from development machine)
scp -r /path/to/pleat_saw pi@<pi-ip>:/home/pi/

# SSH to Pi
ssh pi@<pi-ip>

# Restore your config
cp ~/pleat_saw_config_backup/* /home/pi/pleat_saw/config/

# Run installer
cd /home/pi/pleat_saw
sudo bash pleat_saw_install.sh

# Service should start automatically
# Check status
sudo systemctl status pleat-saw

# Test dashboard
curl http://localhost:5000
```

---

## Verification Tests

Once you think it's working, verify:

### Test 1: Service Running
```bash
systemctl is-active pleat-saw
# Should output: active
```

### Test 2: Port Listening
```bash
sudo ss -tuln | grep 5000
# Should show: tcp LISTEN 0.0.0.0:5000
```

### Test 3: Local HTTP
```bash
curl http://localhost:5000
# Should return HTML (not error)
```

### Test 4: Network HTTP
From another computer on the network:
- Open browser to `http://<pi-ip>:5000`
- Should load dashboard with green "Connected"

### Test 5: Real-Time Updates
- Trigger a sensor
- Watch dashboard indicator change instantly
- Should update within ~100ms

---

## Getting Help

If still not working, collect this information:

```bash
# System info
uname -a
cat /etc/os-release

# Service status
sudo systemctl status pleat-saw

# Recent logs
sudo journalctl -u pleat-saw -n 100 > ~/pleat_saw_logs.txt

# Configuration
cat /home/pi/pleat_saw/config/system.yaml > ~/pleat_saw_config.txt

# Installed packages
/home/pi/pleat_saw/venv/bin/pip list > ~/pleat_saw_packages.txt

# Network info
hostname -I
ip addr show

# Port status
sudo netstat -tuln | grep 5000

# Web files check
ls -laR /home/pi/pleat_saw/app/web/ > ~/web_files.txt
```

Share these files with support:
- `pleat_saw_logs.txt`
- `pleat_saw_config.txt`
- `pleat_saw_packages.txt`
- `web_files.txt`

---

## Common Solutions Summary

| Symptom | Most Likely Cause | Solution |
|---------|------------------|----------|
| Service not running | Install/config error | `sudo systemctl start pleat-saw` |
| Port 5000 not listening | Flask not installed | Install Flask dependencies |
| 404 error | Template files missing | Copy web/ directory |
| 500 error | Python exception | Check logs for traceback |
| Can't connect from network | Firewall or host binding | Allow port 5000, check host: 0.0.0.0 |
| Red "Disconnected" | WebSocket not working | Check Flask-SocketIO installed |

---

**For immediate support, run the diagnostic script first:**
```bash
cd /home/pi/pleat_saw
bash diagnose_web_monitor.sh
```
