# Python 3.13 Compatibility Fix

## Problem
Your Raspberry Pi has Python 3.13, and the `eventlet` library is **not compatible** with Python 3.13. This causes the error:

```
AttributeError: module 'ssl' has no attribute 'wrap_socket'
```

## Solution
Switch from `eventlet` to `threading` mode for Flask-SocketIO, which is fully compatible with Python 3.13.

---

## Quick Fix (Recommended)

### Option 1: Automated Fix Script

Copy the updated files to your Pi, then run:

```bash
cd ~/Documents/Pleat_Saw_V3/panel_node_rounddb_s3_minui/pleat_saw
sudo bash fix_python313.sh
```

This script will:
1. Stop the service
2. Update web_monitor.py to use threading instead of eventlet
3. Uninstall eventlet
4. Install simple-websocket (Python 3.13 compatible)
5. Restart the service
6. Display the dashboard URL

---

### Option 2: Manual Fix

If you prefer to do it manually:

#### Step 1: Stop the service
```bash
sudo systemctl stop pleat-saw
```

#### Step 2: Update web_monitor.py
```bash
cd /home/ambf1/pleat_saw/app/services
nano web_monitor.py
```

Find these lines near the top:
```python
import eventlet

# Monkey patch for eventlet compatibility
eventlet.monkey_patch()
```

**Comment them out or delete them:**
```python
# import eventlet  # Not compatible with Python 3.13
# eventlet.monkey_patch()
```

Find this line (around line 75):
```python
async_mode='eventlet'
```

**Change to:**
```python
async_mode='threading'
```

Save and exit (Ctrl+X, Y, Enter)

#### Step 3: Uninstall eventlet and install compatible packages
```bash
cd /home/ambf1/pleat_saw
source venv/bin/activate
pip uninstall -y eventlet
pip install simple-websocket==1.0.0
deactivate
```

#### Step 4: Restart the service
```bash
sudo systemctl restart pleat-saw
```

#### Step 5: Check status
```bash
sudo systemctl status pleat-saw
```

Should show: **"Active: active (running)"** with no errors.

#### Step 6: Access dashboard
Get your Pi's IP address:
```bash
hostname -I
```

Open browser to: `http://<your-pi-ip>:5000`

---

## Verification

### Check service is running:
```bash
systemctl is-active pleat-saw
# Should output: active
```

### Check port is listening:
```bash
sudo ss -tuln | grep 5000
# Should show: tcp LISTEN 0.0.0.0:5000
```

### Test local connection:
```bash
curl http://localhost:5000
# Should return HTML (not an error)
```

### Access from browser:
Open: `http://<pi-ip>:5000`
- Dashboard should load
- Connection indicator should be green "Connected"

---

## Why This Happened

**Eventlet** uses Python's `ssl.wrap_socket()` function, which was **removed in Python 3.13**. The developers haven't updated eventlet to support Python 3.13 yet.

**Flask-SocketIO** supports multiple async backends:
- `eventlet` (Not compatible with Python 3.13)
- `gevent` (Compatible but requires compilation)
- `threading` (✅ Compatible with all Python versions, no compilation)

We switched to `threading` mode which is:
- ✅ Compatible with Python 3.13
- ✅ No compilation required
- ✅ Works with simple-websocket
- ✅ Sufficient performance for our use case

---

## Troubleshooting

### If service still fails:

**View detailed logs:**
```bash
sudo journalctl -u pleat-saw -n 50
```

**Look for Python errors:**
```bash
sudo journalctl -u pleat-saw | grep -A 10 "Traceback"
```

**Verify Flask packages installed:**
```bash
/home/ambf1/pleat_saw/venv/bin/pip list | grep -E "Flask|socket"
```

Should show:
- Flask
- Flask-SocketIO
- python-socketio
- python-engineio
- simple-websocket

### If packages are missing:

```bash
cd /home/ambf1/pleat_saw
source venv/bin/activate
pip install Flask==3.0.0 Flask-SocketIO==5.3.5 python-socketio==5.10.0 python-engineio==4.8.0 simple-websocket==1.0.0
deactivate
sudo systemctl restart pleat-saw
```

---

## Alternative: Downgrade Python (Not Recommended)

If you absolutely need eventlet, you could downgrade to Python 3.11, but this is **not recommended** as:
- Python 3.13 has important security and performance improvements
- Our threading solution works perfectly
- Future Raspberry Pi OS updates will use Python 3.13+

---

## File Changes Summary

**Modified:**
- `app/services/web_monitor.py` - Removed eventlet, changed to threading mode
- `requirements.txt` - Replaced eventlet with simple-websocket

**No other files changed** - All functionality remains the same.

---

## Performance Impact

**Threading mode vs Eventlet:**
- ✅ Same functionality
- ✅ Same real-time update speed (10 Hz)
- ✅ Same WebSocket performance
- ✅ Slightly higher CPU usage (negligible on RPi 3/4)

For our use case (monitoring dashboard with 1-5 concurrent users), threading mode is perfectly adequate.

---

## Questions?

If the fix doesn't work, provide these details:
```bash
# 1. Python version
python3 --version

# 2. Service status
sudo systemctl status pleat-saw

# 3. Recent logs
sudo journalctl -u pleat-saw -n 50

# 4. Installed packages
/home/ambf1/pleat_saw/venv/bin/pip list
```
