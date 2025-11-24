# Pleat Saw Installer - Usage Guide

## Quick Reference

### Standard Installation (Auto-detect user)

```bash
# The installer will automatically detect the current user
sudo bash pleat_saw_install.sh
```

The installer will automatically use `$SUDO_USER` (the user who ran sudo).

### Specify Custom Username

If you get an error like "user 'pi' does not exist", specify your username:

```bash
# Replace 'yourusername' with your actual username
sudo bash pleat_saw_install.sh yourusername
```

### Find Your Username

If you're not sure what your username is:

```bash
# Show current username
whoami

# List all users on the system
cat /etc/passwd | grep /home | cut -d: -f1
```

Common usernames on Raspberry Pi:
- `pi` (default on older Raspberry Pi OS)
- Custom username (newer Raspberry Pi OS allows setting during first boot)

### Examples

#### Example 1: Standard installation as 'pi' user
```bash
cd /tmp/pleat_saw
sudo bash pleat_saw_install.sh
# Will install to: /home/pi/pleat_saw
```

#### Example 2: Installation for user 'john'
```bash
cd /tmp/pleat_saw
sudo bash pleat_saw_install.sh john
# Will install to: /home/john/pleat_saw
```

#### Example 3: Check your username first
```bash
whoami
# Output: myusername

cd /tmp/pleat_saw
sudo bash pleat_saw_install.sh myusername
# Will install to: /home/myusername/pleat_saw
```

## Troubleshooting

### Error: "User 'pi' does not exist"

**Problem**: The installer is trying to use the default 'pi' user, but your system has a different username.

**Solution**:
```bash
# Find your username
whoami

# Run installer with your username (replace 'yourusername')
sudo bash pleat_saw_install.sh yourusername
```

### Error: "This script must be run as root (use sudo)"

**Problem**: The installer needs root privileges to install system packages and configure services.

**Solution**:
```bash
# Add 'sudo' before the command
sudo bash pleat_saw_install.sh
```

### Error: "Permission denied" on installer script

**Problem**: The installer script doesn't have execute permissions.

**Solution**:
```bash
# Make the script executable
chmod +x pleat_saw_install.sh

# Then run it
sudo bash pleat_saw_install.sh
```

### Error: "Permission denied: '/home/username/pleat_saw/venv'"

**Problem**: The venv creation failed due to directory ownership issues.

**Solution**: This has been fixed in installer v1.2. If you have an older version:

```bash
# Download the latest installer, or manually fix ownership:
sudo chown -R yourusername:yourusername /home/yourusername/pleat_saw

# Then run the installer again
sudo bash pleat_saw_install.sh yourusername
```

**Note**: The latest installer (v1.2+) sets ownership correctly before creating the venv, so this error should not occur.

### Check Installation Directory

After installation, verify the location:

```bash
# Check what user was used
cat /var/log/pleat_saw_install.log | grep "Installation user:"

# List installation directory
ls -la /home/*/pleat_saw
```

## Reinstallation

If installation fails or you need to reinstall:

```bash
# The installer automatically backs up existing installations
# Backup will be saved to: /home/USERNAME/pleat_saw.backup.YYYYMMDD_HHMMSS

# Just run the installer again
sudo bash pleat_saw_install.sh yourusername
```

## Manual Cleanup (if needed)

To completely remove a failed installation:

```bash
# Stop service (if running)
sudo systemctl stop pleat-saw 2>/dev/null || true
sudo systemctl disable pleat-saw 2>/dev/null || true

# Remove files
sudo rm -rf /home/yourusername/pleat_saw
sudo rm -f /etc/systemd/system/pleat-saw.service
sudo rm -f /etc/udev/rules.d/99-pleatsaw-serial.rules

# Reload systemd
sudo systemctl daemon-reload
```

## Installation Log

The complete installation log is saved to:
```
/var/log/pleat_saw_install.log
```

View it with:
```bash
cat /var/log/pleat_saw_install.log
# Or for just the end:
tail -100 /var/log/pleat_saw_install.log
```

## Post-Installation

After successful installation:

1. **Review summary**:
   ```bash
   cat /home/yourusername/pleat_saw/INSTALLATION_INFO.txt
   ```

2. **Log out and back in** (required for group membership):
   ```bash
   exit
   # Then SSH back in
   ssh yourusername@raspberrypi.local

   # Verify dialout group membership
   groups | grep dialout
   ```

3. **Configure the application**:
   ```bash
   nano /home/yourusername/pleat_saw/config/system.yaml
   nano /home/yourusername/pleat_saw/config/motion.yaml
   ```

4. **Start the service**:
   ```bash
   sudo systemctl start pleat-saw
   sudo systemctl status pleat-saw
   ```

5. **View logs**:
   ```bash
   sudo journalctl -u pleat-saw -f
   ```

## Support

For additional help, see:
- [Installation Guide](docs/installation_guide.md)
- [Commissioning Checklist](docs/commissioning_checklist.md)
- [README](README.md)

Contact the controls engineering team for technical support.
