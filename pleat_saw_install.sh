#!/bin/bash
################################################################################
# Pleat Saw Controller - One-Click Installer
#
# This script performs a complete installation of the Pleat Saw Controller
# on a Raspberry Pi, including:
#   - System dependencies (Python 3.11, pip, git)
#   - Python virtual environment setup
#   - Python package dependencies
#   - Serial port permissions
#   - Systemd service installation and configuration
#   - Directory structure setup
#   - Configuration file deployment
#
# Usage:
#   sudo bash pleat_saw_install.sh [username]
#
#   If no username is provided, will use $SUDO_USER or prompt for input
#
# Requirements:
#   - Raspberry Pi OS (Bookworm or later recommended)
#   - Root/sudo privileges
#   - Internet connection for package downloads
#
# Author: Pleat Saw Controls Team
# Version: 1.4
# Last Updated: 2025-10-21
#
# Changelog:
#   v1.4 - Simplified: Always create venv as root, then fix ownership (bulletproof)
#   v1.3 - Robust venv creation with multiple fallback methods, better error handling
#   v1.2 - Fixed permission denied error when creating venv (partial fix)
#   v1.1 - Added automatic username detection
#   v1.0 - Initial release
################################################################################

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Determine target user
# Priority: 1) Command line argument, 2) SUDO_USER, 3) Prompt user
if [ -n "$1" ]; then
    USER="$1"
elif [ -n "$SUDO_USER" ]; then
    USER="$SUDO_USER"
else
    # Not running with sudo, or no SUDO_USER set
    read -p "Enter the username for installation (default: pi): " USER
    USER=${USER:-pi}
fi

GROUP="$USER"
INSTALL_DIR="/home/$USER/pleat_saw"

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo -e "${BLUE}"
    echo "=============================================================================="
    echo "$1"
    echo "=============================================================================="
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

check_user_exists() {
    if ! id "$USER" &>/dev/null; then
        print_error "User '$USER' does not exist"
        exit 1
    fi
}

################################################################################
# Installation Steps
################################################################################

step_1_system_update() {
    print_header "Step 1: Updating System Packages"

    apt-get update
    print_success "Package lists updated"
}

step_2_install_dependencies() {
    print_header "Step 2: Installing System Dependencies"

    # Install Python 3.11 and development tools
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        git \
        build-essential \
        libffi-dev \
        libssl-dev

    print_success "System dependencies installed"

    # Verify Python version
    PYTHON_VERSION=$(python3 --version)
    print_info "Python version: $PYTHON_VERSION"
}

step_3_create_directories() {
    print_header "Step 3: Creating Directory Structure"

    # Backup existing installation if present
    if [ -d "$INSTALL_DIR" ]; then
        BACKUP_DIR="${INSTALL_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
        print_warning "Existing installation found. Backing up to: $BACKUP_DIR"
        mv "$INSTALL_DIR" "$BACKUP_DIR"
    fi

    # Create main directory with proper permissions from the start
    mkdir -p "$INSTALL_DIR"
    print_success "Created: $INSTALL_DIR"

    # Create subdirectories
    mkdir -p "$INSTALL_DIR/app"
    mkdir -p "$INSTALL_DIR/app/services"
    mkdir -p "$INSTALL_DIR/app/utils"
    mkdir -p "$INSTALL_DIR/app/tests"
    mkdir -p "$INSTALL_DIR/config"
    mkdir -p "$INSTALL_DIR/logs"
    mkdir -p "$INSTALL_DIR/data"

    # Set ownership and permissions explicitly
    chown -R "$USER:$GROUP" "$INSTALL_DIR"
    chmod -R u+rwX,g+rX,o+rX "$INSTALL_DIR"

    # Verify ownership was set correctly
    ACTUAL_OWNER=$(stat -c '%U' "$INSTALL_DIR" 2>/dev/null || stat -f '%Su' "$INSTALL_DIR" 2>/dev/null)
    if [ "$ACTUAL_OWNER" != "$USER" ]; then
        print_error "Failed to set ownership. Directory owned by: $ACTUAL_OWNER (expected: $USER)"
        exit 1
    fi

    print_success "Directory structure created and ownership verified"
}

step_4_copy_files() {
    print_header "Step 4: Copying Application Files"

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Copy Python application
    if [ -d "$SCRIPT_DIR/app" ]; then
        cp -r "$SCRIPT_DIR/app"/* "$INSTALL_DIR/app/"
        print_success "Python application copied"
    else
        print_error "Source directory 'app' not found in $SCRIPT_DIR"
        exit 1
    fi

    # Copy configuration files
    if [ -d "$SCRIPT_DIR/config" ]; then
        cp -r "$SCRIPT_DIR/config"/* "$INSTALL_DIR/config/"
        print_success "Configuration files copied"
    else
        print_warning "Config directory not found, skipping"
    fi

    # Copy requirements.txt
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
        print_success "requirements.txt copied"
    else
        print_error "requirements.txt not found in $SCRIPT_DIR"
        exit 1
    fi

    # Copy documentation
    if [ -d "$SCRIPT_DIR/docs" ]; then
        cp -r "$SCRIPT_DIR/docs" "$INSTALL_DIR/"
        print_success "Documentation copied"
    fi

    # Copy systemd service files
    if [ -d "$SCRIPT_DIR/systemd" ]; then
        cp -r "$SCRIPT_DIR/systemd" "$INSTALL_DIR/"
        print_success "Systemd files copied"
    fi

    # Reset ownership after copying (files may be owned by root)
    chown -R "$USER:$GROUP" "$INSTALL_DIR"
    print_success "File ownership set to $USER:$GROUP"
}

step_5_setup_virtualenv() {
    print_header "Step 5: Setting Up Python Virtual Environment"

    # Remove any existing venv directory from failed attempts
    if [ -d "$INSTALL_DIR/venv" ]; then
        print_warning "Removing existing venv directory"
        rm -rf "$INSTALL_DIR/venv"
    fi

    # Verify the parent directory exists and has correct permissions
    print_info "Verifying directory permissions..."
    ls -ld "$INSTALL_DIR" || true

    # Show who owns the directory
    print_info "Directory owner: $(stat -c '%U:%G' "$INSTALL_DIR" 2>/dev/null || stat -f '%Su:%Sg' "$INSTALL_DIR" 2>/dev/null)"

    # SIMPLIFIED APPROACH: Always create as root, then fix ownership
    # This is the most reliable method across all systems
    print_info "Creating virtual environment..."

    # Create venv as root (this will always work)
    if ! python3 -m venv "$INSTALL_DIR/venv" --system-site-packages; then
        # Try without system-site-packages if that fails
        print_warning "Retrying without --system-site-packages..."
        python3 -m venv "$INSTALL_DIR/venv"
    fi

    # Verify venv was created
    if [ ! -f "$INSTALL_DIR/venv/bin/python3" ]; then
        print_error "Virtual environment creation failed"
        print_error "Please check:"
        print_error "  1. Python3 is installed: python3 --version"
        print_error "  2. python3-venv package: sudo apt-get install python3-venv"
        print_error "  3. Disk space: df -h /home"
        exit 1
    fi

    # Now fix ownership of everything
    print_info "Setting ownership to $USER:$GROUP..."
    chown -R "$USER:$GROUP" "$INSTALL_DIR/venv"
    chmod -R u+rwX,go+rX "$INSTALL_DIR/venv"

    print_success "Virtual environment created"

    # Upgrade pip - run as root, then fix ownership
    print_info "Upgrading pip..."
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip --quiet
    chown -R "$USER:$GROUP" "$INSTALL_DIR/venv"

    print_success "pip upgraded"
}

step_6_install_python_packages() {
    print_header "Step 6: Installing Python Dependencies"

    # Install from requirements.txt
    print_info "Installing Python packages (this may take a few minutes)..."

    # Install as root, then fix ownership (most reliable)
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet

    # Fix ownership after installation
    chown -R "$USER:$GROUP" "$INSTALL_DIR/venv"

    print_success "Python packages installed"

    # List installed packages
    print_info "Installed packages:"
    "$INSTALL_DIR/venv/bin/pip" list | grep -E "(pymodbus|pyserial|pyyaml|pytest)" || true
}

step_7_configure_serial_permissions() {
    print_header "Step 7: Configuring Serial Port Permissions"

    # Add user to dialout group for serial port access
    if groups "$USER" | grep -q "\bdialout\b"; then
        print_info "User '$USER' already in 'dialout' group"
    else
        usermod -a -G dialout "$USER"
        print_success "Added '$USER' to 'dialout' group"
    fi

    # Create udev rule for serial ports
    cat > /etc/udev/rules.d/99-pleatsaw-serial.rules <<EOF
# Pleat Saw Controller - Serial Port Rules
# RS-485 Modbus devices
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", MODE="0666", GROUP="dialout"

# Nextion HMI
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE="0666", GROUP="dialout"
EOF

    print_success "udev rules created"

    # Reload udev rules
    udevadm control --reload-rules
    udevadm trigger
    print_success "udev rules reloaded"
}

step_8_install_systemd_service() {
    print_header "Step 8: Installing Systemd Service"

    # Create systemd service file
    cat > /etc/systemd/system/pleat-saw.service <<EOF
[Unit]
Description=Pleat Saw Controller
After=network.target

[Service]
Type=simple
User=$USER
Group=$GROUP
WorkingDirectory=$INSTALL_DIR/app
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/app/main.py
Restart=always
RestartSec=10

# Environment
Environment=PYTHONUNBUFFERED=1

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    print_success "Systemd service file created"

    # Reload systemd
    systemctl daemon-reload
    print_success "Systemd daemon reloaded"

    # Enable service to start on boot
    systemctl enable pleat-saw.service
    print_success "Service enabled for auto-start on boot"
}

step_9_set_permissions() {
    print_header "Step 9: Setting File Permissions"

    # Set ownership
    chown -R "$USER:$GROUP" "$INSTALL_DIR"
    print_success "Ownership set to $USER:$GROUP"

    # Set directory permissions
    find "$INSTALL_DIR" -type d -exec chmod 755 {} \;
    print_success "Directory permissions set"

    # Set file permissions
    find "$INSTALL_DIR" -type f -exec chmod 644 {} \;
    print_success "File permissions set"

    # Make Python files executable
    find "$INSTALL_DIR/app" -name "*.py" -exec chmod 755 {} \;
    print_success "Python files made executable"

    # Ensure logs directory is writable
    chmod 775 "$INSTALL_DIR/logs"
    print_success "Logs directory permissions set"
}

step_10_run_tests() {
    print_header "Step 10: Running Unit Tests"

    if [ -d "$INSTALL_DIR/app/tests" ]; then
        print_info "Running test suite..."
        # Run tests as root (venv is configured, ownership is correct)
        if "$INSTALL_DIR/venv/bin/pytest" "$INSTALL_DIR/app/tests/" -v 2>&1; then
            print_success "All tests passed"
        else
            print_warning "Some tests failed (this may be OK if hardware is not connected)"
        fi
    else
        print_warning "No tests found, skipping"
    fi
}

step_11_create_config_summary() {
    print_header "Step 11: Creating Configuration Summary"

    cat > "$INSTALL_DIR/INSTALLATION_INFO.txt" <<EOF
Pleat Saw Controller - Installation Summary
============================================

Installation Date: $(date)
Installation Path: $INSTALL_DIR
Python Version: $(python3 --version)
User: $USER
Group: $GROUP

Directory Structure:
--------------------
$INSTALL_DIR/
├── app/                  # Python application
│   ├── main.py          # Entry point
│   ├── services/        # Background services
│   ├── utils/           # Utility modules
│   └── tests/           # Unit tests
├── config/              # YAML configuration files
├── logs/                # Application logs
├── data/                # Runtime data
├── venv/                # Python virtual environment
└── systemd/             # Systemd service files

Service Management:
-------------------
Start service:     sudo systemctl start pleat-saw
Stop service:      sudo systemctl stop pleat-saw
Restart service:   sudo systemctl restart pleat-saw
Service status:    sudo systemctl status pleat-saw
View logs:         sudo journalctl -u pleat-saw -f

Configuration Files:
--------------------
System config:     $INSTALL_DIR/config/system.yaml
I/O mapping:       $INSTALL_DIR/config/io_map.yaml
Motion params:     $INSTALL_DIR/config/motion.yaml

Log Files:
----------
Application log:   $INSTALL_DIR/logs/pleat_saw.log
Event log (CSV):   $INSTALL_DIR/logs/events.csv
System journal:    sudo journalctl -u pleat-saw

Testing:
--------
Run unit tests:    $INSTALL_DIR/venv/bin/pytest $INSTALL_DIR/app/tests/ -v
Dry-run mode:      $INSTALL_DIR/venv/bin/python $INSTALL_DIR/app/main.py --dry-run

Next Steps:
-----------
1. Review and edit configuration files in $INSTALL_DIR/config/
2. Configure RS-485 serial port in config/system.yaml
3. Configure Nextion HMI serial port in config/system.yaml
4. Verify I/O mapping in config/io_map.yaml
5. Tune motion parameters in config/motion.yaml
6. Connect hardware (RS-485 bus, Nextion HMI)
7. Start the service: sudo systemctl start pleat-saw
8. Follow commissioning checklist: $INSTALL_DIR/docs/commissioning_checklist.md

Support:
--------
Documentation: $INSTALL_DIR/docs/
ESP32 Firmware: Upload from firmware/ directory using PlatformIO
Nextion HMI:    See NEXTION_PROMPT.md for HMI programming guide

For technical support, contact the controls engineering team.
EOF

    chown "$USER:$GROUP" "$INSTALL_DIR/INSTALLATION_INFO.txt"
    print_success "Installation summary created"
}

################################################################################
# Main Installation Flow
################################################################################

main() {
    print_header "Pleat Saw Controller - One-Click Installer"

    print_info "This script will install the Pleat Saw Controller to: $INSTALL_DIR"
    print_info "Installation user: $USER"
    echo ""

    # Pre-flight checks
    check_root
    check_user_exists

    # Run installation steps
    step_1_system_update
    step_2_install_dependencies
    step_3_create_directories
    step_4_copy_files
    step_5_setup_virtualenv
    step_6_install_python_packages
    step_7_configure_serial_permissions
    step_8_install_systemd_service
    step_9_set_permissions
    step_10_run_tests
    step_11_create_config_summary

    # Installation complete
    print_header "Installation Complete!"

    echo -e "${GREEN}"
    echo "✓ Pleat Saw Controller has been successfully installed to: $INSTALL_DIR"
    echo ""
    echo "Next Steps:"
    echo "  1. Review installation summary: cat $INSTALL_DIR/INSTALLATION_INFO.txt"
    echo "  2. Edit configuration files in: $INSTALL_DIR/config/"
    echo "  3. Start the service: sudo systemctl start pleat-saw"
    echo "  4. Check service status: sudo systemctl status pleat-saw"
    echo "  5. View logs: sudo journalctl -u pleat-saw -f"
    echo ""
    echo "IMPORTANT: You may need to log out and back in for group membership changes to take effect."
    echo "After logging back in, run: groups | grep dialout"
    echo ""
    echo "For detailed commissioning steps, see: $INSTALL_DIR/docs/commissioning_checklist.md"
    echo -e "${NC}"

    print_info "Installation log saved to: /var/log/pleat_saw_install.log"
}

# Run main installation
main 2>&1 | tee /var/log/pleat_saw_install.log

exit 0
