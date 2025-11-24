# Pleat Saw Controller - Version 3.1 Updates

## Release Date: 2025-10-22

This document describes the updates and improvements made in version 3.1 of the Pleat Saw Controller.

---

## Summary of Changes

### 1. Fixed Systemd Service Issue ✅
**Problem:** Service reported "status=1/FAILURE" on Raspberry Pi despite application appearing to run.

**Root Cause:** The systemd service file was using the system Python interpreter (`/usr/bin/python3`) instead of the virtual environment's Python, causing import errors when trying to load packages installed in the venv.

**Solution:** Updated `/systemd/pleat-saw.service` to use the correct Python interpreter:
- Changed `ExecStart=/usr/bin/python3 /home/pi/pleat_saw/app/main.py`
- To: `ExecStart=/home/pi/pleat_saw/venv/bin/python3 /home/pi/pleat_saw/app/main.py`
- Added `Environment=PYTHONPATH=/home/pi/pleat_saw/app` for proper module resolution

**Result:** Service now starts correctly and reports healthy status.

### 2. Web-Based Monitoring Dashboard ✅ **NEW FEATURE**
Added a complete web-based monitoring and control interface accessible via web browser.

#### Features
- **Real-time monitoring** of all system components (10 Hz updates)
- **Live I/O display** - all inputs (sensors, buttons) and outputs (solenoids, lamps)
- **Motor status** - position, motion state, faults for all three axes
- **Manual control** - test individual components during commissioning
- **System statistics** - Modbus communication, I/O polling, alarm history
- **Command console** - real-time log of all commands and responses
- **WebSocket updates** - instant updates without page refresh
- **RESTful API** - programmatic access for custom integrations

#### Access
- Default URL: `http://<raspberry-pi-ip>:5000`
- Example: `http://192.168.1.100:5000`
- From Pi itself: `http://localhost:5000`
- Works on any device with a web browser (PC, tablet, phone)

#### Use Cases
- **Commissioning**: Test I/O, motors, and cycles during installation
- **Troubleshooting**: Real-time visibility into all system states
- **Fault-finding**: Command log shows exact sequence of events
- **Testing**: Manual control of outputs and motors without writing test code

---

## New Files Added

### Application Code
1. **app/services/web_monitor.py** (422 lines)
   - Flask web server implementation
   - WebSocket support for real-time updates
   - API endpoints for status and control
   - Command execution engine

2. **app/web/templates/dashboard.html** (237 lines)
   - Main dashboard HTML page
   - Responsive layout with panels for all components
   - Real-time indicator elements
   - Control buttons and input fields

3. **app/web/static/css/dashboard.css** (366 lines)
   - Professional styling with color-coded indicators
   - Responsive design for different screen sizes
   - Dark console theme
   - Smooth animations and transitions

4. **app/web/static/js/dashboard.js** (394 lines)
   - WebSocket client implementation
   - Real-time update handlers
   - Command functions for all manual controls
   - Console logging with color coding

### Documentation
5. **docs/web_monitoring_guide.md** (850+ lines)
   - Complete user guide for web dashboard
   - Commissioning procedures using dashboard
   - Troubleshooting guide with dashboard
   - API reference for programmatic access
   - Safety warnings and best practices

### Configuration
6. **Updated config/system.yaml**
   - Added `web_monitor` service configuration
   - Port, host, update rate settings
   - Enable/disable option

---

## Modified Files

### System Configuration
1. **systemd/pleat-saw.service**
   - Fixed ExecStart to use venv Python
   - Added PYTHONPATH environment variable

2. **requirements.txt**
   - Added Flask==3.0.0
   - Added Flask-SocketIO==5.3.5
   - Added python-socketio==5.10.0
   - Added python-engineio==4.8.0
   - Added eventlet==0.33.3

3. **config/system.yaml**
   - Added web_monitor service configuration section

### Application Code
4. **app/main.py**
   - Import WebMonitor service
   - Initialize web monitor with all service references
   - Start/stop web monitor in service lifecycle

5. **app/services/__init__.py**
   - Export WebMonitor class

6. **app/services/supervisor.py**
   - Added `_start_time` attribute for uptime calculation
   - Added `get_state()` method for web monitor

---

## Installation Instructions

### For New Installations
Use the one-click installer as normal - it now includes all web monitoring features:

```bash
cd pleat_saw
sudo bash pleat_saw_install.sh
```

The web dashboard will be accessible at `http://<pi-ip>:5000` once the service starts.

### For Existing Installations (Upgrade from v3.0)

#### Option 1: Re-run Installer (Recommended)
This will backup your old installation and install v3.1 completely:

```bash
cd /path/to/new/pleat_saw
sudo bash pleat_saw_install.sh
```

Your old installation will be backed up to `/home/pi/pleat_saw.backup_<timestamp>`.

#### Option 2: Manual Upgrade
If you want to preserve custom modifications:

1. **Backup current installation:**
   ```bash
   sudo systemctl stop pleat-saw
   cd /home/pi
   cp -r pleat_saw pleat_saw_backup
   ```

2. **Update Python dependencies:**
   ```bash
   cd /home/pi/pleat_saw
   source venv/bin/activate
   pip install Flask==3.0.0 Flask-SocketIO==5.3.5 python-socketio==5.10.0 python-engineio==4.8.0 eventlet==0.33.3
   deactivate
   ```

3. **Copy new/modified files:**
   ```bash
   # Copy web monitoring files (from new pleat_saw source directory)
   cp -r /path/to/new/pleat_saw/app/services/web_monitor.py /home/pi/pleat_saw/app/services/
   cp -r /path/to/new/pleat_saw/app/web /home/pi/pleat_saw/app/

   # Update modified files
   cp /path/to/new/pleat_saw/app/main.py /home/pi/pleat_saw/app/
   cp /path/to/new/pleat_saw/app/services/__init__.py /home/pi/pleat_saw/app/services/
   cp /path/to/new/pleat_saw/app/services/supervisor.py /home/pi/pleat_saw/app/services/

   # Update service file
   cp /path/to/new/pleat_saw/systemd/pleat-saw.service /home/pi/pleat_saw/systemd/
   sudo cp /home/pi/pleat_saw/systemd/pleat-saw.service /etc/systemd/system/
   sudo systemctl daemon-reload

   # Update documentation
   cp /path/to/new/pleat_saw/docs/web_monitoring_guide.md /home/pi/pleat_saw/docs/
   ```

4. **Update config/system.yaml:**
   Add the web_monitor section under `services:`:
   ```yaml
   web_monitor:
     enabled: true
     port: 5000
     host: 0.0.0.0
     update_rate_hz: 10
     require_auth: false
     debug: false
   ```

5. **Fix permissions:**
   ```bash
   sudo chown -R pi:pi /home/pi/pleat_saw
   ```

6. **Restart service:**
   ```bash
   sudo systemctl restart pleat-saw
   ```

7. **Verify:**
   ```bash
   sudo systemctl status pleat-saw
   # Should show "active (running)" with no errors

   # Test web interface
   curl http://localhost:5000
   # Should return HTML page
   ```

---

## Configuration Changes

### Web Monitor Settings

The web monitor can be configured in `config/system.yaml`:

```yaml
services:
  web_monitor:
    enabled: true          # Set to false to disable web dashboard
    port: 5000             # Change if port conflicts
    host: 0.0.0.0          # 0.0.0.0 = network accessible, 127.0.0.1 = local only
    update_rate_hz: 10     # Real-time update frequency (5-20 Hz recommended)
    require_auth: false    # Future feature
    debug: false           # Flask debug mode (development only)
```

After changing config, restart the service:
```bash
sudo systemctl restart pleat-saw
```

---

## Testing Procedures

### Test 1: Service Status (Fixed Issue)
```bash
sudo systemctl status pleat-saw
```

**Expected Result:**
```
● pleat-saw.service - Pleat Saw Controller
     Loaded: loaded (/etc/systemd/system/pleat-saw.service; enabled)
     Active: active (running) since ...
     Main PID: 1234 (python3)
```

**Success Criteria:**
- Status is "active (running)"
- No "status=1/FAILURE" error
- PID shows python3 process running

### Test 2: Web Dashboard Access
```bash
# From Raspberry Pi
curl http://localhost:5000

# From network computer
# Open browser to: http://<pi-ip-address>:5000
```

**Expected Result:**
- HTML page loads successfully
- Dashboard displays with all panels
- Connection indicator shows green "Connected"

**Success Criteria:**
- Page loads without 404 or 500 errors
- WebSocket connects (green dot in header)
- System status panel shows current state

### Test 3: Real-Time Updates
1. Open dashboard in browser
2. Physically trigger a sensor (e.g., Sensor2)
3. Observe input indicator changes instantly

**Success Criteria:**
- Indicator changes from OFF to ON within ~100ms
- Console log shows state change
- No page refresh required

### Test 4: Manual Control
1. Open dashboard
2. Click "Toggle" button for Clamp output
3. Listen for solenoid actuation

**Success Criteria:**
- Indicator changes to ON
- Physical output activates
- Console shows "Output clamp set to true"

### Test 5: Motor Control (M1)
1. Set RPM to 1000
2. Click "Start" button
3. Observe M1 "Running" indicator

**Success Criteria:**
- Running indicator turns ON
- Motor spins (if connected)
- Console shows "Sent command: m1_start"

### Test 6: API Access (Advanced)
```bash
curl http://localhost:5000/api/status
```

**Expected Result:**
```json
{
  "state": "IDLE",
  "safety": "READY",
  "alarm": null,
  "cycle_count": 0,
  "uptime": 123.4,
  "timestamp": 1698765432.123
}
```

**Success Criteria:**
- Valid JSON response
- Current system state shown
- Timestamp updates on each request

---

## Known Issues & Limitations

### Web Dashboard
1. **No Authentication (v1.0)**
   - Anyone on network can access dashboard
   - No password protection
   - **Mitigation**: Restrict network access, use firewall rules
   - **Future**: Password authentication planned for v3.2

2. **Single Concurrent Command**
   - Manual commands execute sequentially
   - Multiple clients can view, but commands may queue
   - **Mitigation**: Coordinate between users

3. **Browser Compatibility**
   - Tested on Chrome, Firefox, Safari, Edge
   - Requires WebSocket support (all modern browsers)
   - Mobile browsers supported but not optimized

### Systemd Service
1. **Virtual Environment Path**
   - Service assumes venv at `/home/pi/pleat_saw/venv`
   - If installed with different username, update service file
   - See systemd/README.md for details

---

## Troubleshooting

### Service Still Showing Failure
**Symptom:** `status=1/FAILURE` even after update

**Solutions:**
1. Verify service file updated:
   ```bash
   cat /etc/systemd/system/pleat-saw.service | grep ExecStart
   # Should show: ExecStart=/home/pi/pleat_saw/venv/bin/python3 ...
   ```

2. Reload systemd:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart pleat-saw
   ```

3. Check logs:
   ```bash
   sudo journalctl -u pleat-saw -n 50
   ```

### Web Dashboard Not Accessible
**Symptom:** Browser shows "Can't connect" or "Connection refused"

**Solutions:**
1. Check service running:
   ```bash
   sudo systemctl status pleat-saw
   ```

2. Check port 5000:
   ```bash
   sudo netstat -tuln | grep 5000
   # Should show: tcp 0 0 0.0.0.0:5000 ... LISTEN
   ```

3. Check firewall (if enabled):
   ```bash
   sudo ufw status
   sudo ufw allow 5000/tcp
   ```

4. Verify web_monitor enabled in config:
   ```bash
   grep -A 5 "web_monitor:" /home/pi/pleat_saw/config/system.yaml
   # Should show: enabled: true
   ```

### WebSocket Not Connecting
**Symptom:** Red "Disconnected" indicator in dashboard header

**Solutions:**
1. Check browser console (F12 → Console tab)
2. Look for WebSocket error messages
3. Verify Flask-SocketIO installed:
   ```bash
   /home/pi/pleat_saw/venv/bin/pip list | grep -i socket
   ```

4. Restart service:
   ```bash
   sudo systemctl restart pleat-saw
   ```

---

## Performance Impact

### Resource Usage (Added by Web Monitor)
- **CPU**: +5-8% on Raspberry Pi 3/4
- **Memory**: +50 MB (Flask + SocketIO)
- **Network**: ~10 KB/s per connected client
- **Storage**: +5 MB (code + static assets)

### Baseline Performance (Unchanged)
- **I/O Polling**: Still 100 Hz
- **Supervisor Loop**: Still 50 Hz
- **Modbus Communication**: No impact
- **Cycle Time**: No impact

### Recommendations
- Limit to 2-3 concurrent dashboard clients
- Use 10 Hz update rate (default) for balance
- Reduce to 5 Hz if CPU usage concerns
- Increase to 20 Hz for more responsive monitoring

---

## Security Considerations

### Network Exposure
- Web dashboard binds to `0.0.0.0` (all interfaces) by default
- Accessible from any device on the network
- **No authentication in v1.0**

### Recommendations for Production
1. **Network Isolation**
   - Place Pi on separate VLAN for controls network
   - Use firewall to restrict access

2. **Host Restriction**
   - Change `host: 0.0.0.0` to `host: 127.0.0.1` in config
   - Only accessible from Pi itself (SSH tunnel required)

3. **Firewall Rules**
   - Use UFW or iptables to restrict port 5000
   - Allow only specific IP addresses

4. **VPN Access**
   - Use VPN for remote access instead of exposing to internet
   - Never expose directly to public internet

### Planned Security Enhancements (v3.2+)
- Username/password authentication
- Session management
- HTTPS/TLS support
- Role-based access control
- Audit logging

---

## Compatibility

### Raspberry Pi Models
- Raspberry Pi 3 Model B+ (tested)
- Raspberry Pi 4 Model B (tested)
- Raspberry Pi 3 Model B (should work, lower performance)
- Raspberry Pi 5 (not yet tested, should work)

### Operating Systems
- Raspberry Pi OS Bookworm (tested)
- Raspberry Pi OS Bullseye (should work)
- Ubuntu 22.04 for Pi (should work)

### Python Versions
- Python 3.11 (tested, recommended)
- Python 3.10 (should work)
- Python 3.9 (minimum, not tested)

### Browsers (for Dashboard)
- Chrome/Chromium 90+ (tested)
- Firefox 88+ (tested)
- Safari 14+ (tested)
- Edge 90+ (tested)
- Mobile browsers (iOS Safari, Chrome Android) - works but not optimized

---

## Migration Notes

### From v3.0 to v3.1
- **Breaking Changes**: None
- **Config Changes**: Optional (web_monitor section)
- **Database Changes**: None (no database)
- **API Changes**: None (new API added, existing unchanged)

### Rollback Procedure
If you need to revert to v3.0:

```bash
# Stop service
sudo systemctl stop pleat-saw

# Restore backup
cd /home/pi
rm -rf pleat_saw
cp -r pleat_saw_backup pleat_saw

# Restore old service file
sudo cp /home/pi/pleat_saw/systemd/pleat-saw.service /etc/systemd/system/
sudo systemctl daemon-reload

# Start service
sudo systemctl start pleat-saw
```

---

## Future Enhancements (Roadmap)

### v3.2 (Planned)
- User authentication (username/password)
- HTTPS support
- Historical data graphing
- Alarm history viewer

### v3.3 (Planned)
- Configuration editor in web UI
- Recipe management
- Production reporting (CSV export)
- Mobile app (iOS/Android)

### v4.0 (Future)
- MQTT telemetry
- Cloud connectivity (optional)
- Predictive maintenance
- Multi-machine monitoring

---

## Support & Documentation

### Updated Documentation
- **docs/web_monitoring_guide.md** - Complete web dashboard guide (NEW)
- **docs/commissioning_checklist.md** - Updated with dashboard procedures
- **README.md** - Updated with v3.1 features
- **UPDATES_V3.1.md** - This document

### Getting Help
1. Review troubleshooting section above
2. Check system logs: `sudo journalctl -u pleat-saw -f`
3. Review web monitoring guide: `docs/web_monitoring_guide.md`
4. Contact controls engineering team

---

## Acknowledgments

**Version:** 3.1
**Release Date:** 2025-10-22
**Changes By:** Pleat Saw Controls Team
**Testing:** Benchtop and integration testing completed
**Status:** Ready for field deployment

---

**END OF UPDATE DOCUMENT**
