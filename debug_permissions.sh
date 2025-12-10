#!/bin/bash
################################################################################
# Permission Debugging Script
# Run this on your Raspberry Pi to diagnose the permission issue
################################################################################

echo "===== SYSTEM INFORMATION ====="
uname -a
echo ""

echo "===== CURRENT USER ====="
whoami
id
echo ""

echo "===== HOME DIRECTORY PERMISSIONS ====="
ls -ld /home/ambf1
echo ""

echo "===== CHECKING IF /home/ambf1/pleat_saw EXISTS ====="
if [ -d /home/ambf1/pleat_saw ]; then
    echo "Directory exists:"
    ls -ld /home/ambf1/pleat_saw
    echo ""
    echo "Contents:"
    ls -la /home/ambf1/pleat_saw/
else
    echo "Directory does not exist"
fi
echo ""

echo "===== TESTING WRITE PERMISSIONS ====="
echo "Testing as root:"
sudo touch /home/ambf1/test_root.txt && echo "✓ Root can write" || echo "✗ Root cannot write"
sudo rm -f /home/ambf1/test_root.txt

echo "Testing as ambf1:"
sudo -u ambf1 touch /home/ambf1/test_ambf1.txt && echo "✓ ambf1 with sudo -u can write" || echo "✗ ambf1 with sudo -u cannot write"
sudo rm -f /home/ambf1/test_ambf1.txt

echo "Testing as ambf1 with su:"
su - ambf1 -c "touch /home/ambf1/test_su.txt" && echo "✓ ambf1 with su - can write" || echo "✗ ambf1 with su - cannot write"
sudo rm -f /home/ambf1/test_su.txt
echo ""

echo "===== PYTHON VENV TEST (as root) ====="
cd /tmp
rm -rf /tmp/test_venv_root
python3 -m venv /tmp/test_venv_root && echo "✓ Root can create venv in /tmp" || echo "✗ Root cannot create venv"
rm -rf /tmp/test_venv_root
echo ""

echo "===== PYTHON VENV TEST (as ambf1 with sudo -u) ====="
cd /tmp
rm -rf /tmp/test_venv_sudo
sudo -u ambf1 python3 -m venv /tmp/test_venv_sudo && echo "✓ ambf1 with sudo -u can create venv in /tmp" || echo "✗ ambf1 with sudo -u cannot create venv"
sudo rm -rf /tmp/test_venv_sudo
echo ""

echo "===== PYTHON VENV TEST (as ambf1 with su -) ====="
cd /tmp
rm -rf /tmp/test_venv_su
su - ambf1 -c "python3 -m venv /tmp/test_venv_su" && echo "✓ ambf1 with su - can create venv in /tmp" || echo "✗ ambf1 with su - cannot create venv"
sudo rm -rf /tmp/test_venv_su
echo ""

echo "===== CHECKING SELINUX/APPARMOR ====="
if command -v getenforce &> /dev/null; then
    echo "SELinux status:"
    getenforce
else
    echo "SELinux not installed"
fi

if command -v aa-status &> /dev/null; then
    echo "AppArmor status:"
    sudo aa-status 2>/dev/null | head -5
else
    echo "AppArmor not installed"
fi
echo ""

echo "===== DISK SPACE ====="
df -h /home
echo ""

echo "===== MOUNT OPTIONS FOR /home ====="
mount | grep /home || echo "No separate /home mount"
echo ""

echo "===== PYTHON VERSION AND VENV MODULE ====="
python3 --version
python3 -c "import venv; print('venv module:', venv.__file__)"
