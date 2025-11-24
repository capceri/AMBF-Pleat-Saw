# ESP32 Firmware Update Required - 115200 Baud

## Issue Found
The second RS485 channel (ttySC1) is connected and working at 115200 baud on the Pi, but the ESP32s are still programmed with 9600 baud firmware.

## What Was Fixed
Updated firmware source files:
- `/home/ambf1/pleat_saw/firmware/esp32a_axis12/src/main.cpp` - Changed MODBUS_BAUD from 9600 to 115200
- `/home/ambf1/pleat_saw/firmware/esp32b_backstop/src/main.cpp` - Changed MODBUS_BAUD from 9600 to 115200

## Current Status
✅ Pi software: Configured for dual RS485 channels (ttySC0 @ 9600, ttySC1 @ 115200)
✅ Firmware source: Updated to 115200 baud
⚠️ ESP32 boards: NEED TO BE RE-PROGRAMMED with new firmware

## Next Steps - REQUIRED

### Option 1: Upload from Pi using PlatformIO
```bash
# Install PlatformIO on Pi (if not already)
cd /home/ambf1/pleat_saw/firmware/esp32a_axis12
pio run -t upload

cd /home/ambf1/pleat_saw/firmware/esp32b_backstop
pio run -t upload
```

### Option 2: Upload from your computer
1. Copy the updated firmware files from Pi to your computer:
```bash
scp -r ambf1@192.168.68.109:/home/ambf1/pleat_saw/firmware /Users/ceripritch/Documents/Pleat\ Saw\ V3/panel_node_rounddb_s3_minui/pleat_saw/
```

2. Open Arduino IDE or PlatformIO on your computer

3. Upload ESP32-A firmware:
   - File: `firmware/esp32a_axis12/src/main.cpp`
   - Board: ESP32 Dev Module
   - Connect ESP32-A via USB and upload

4. Upload ESP32-B firmware:
   - File: `firmware/esp32b_backstop/src/main.cpp`
   - Board: ESP32 Dev Module
   - Connect ESP32-B via USB and upload

## Verification
After uploading both ESP32 firmwares:

1. Restart the Pi service:
```bash
sudo systemctl restart pleat-saw
```

2. Check the logs - you should see NO MORE "No Response" errors:
```bash
sudo journalctl -u pleat-saw -f
```

3. Open web dashboard: http://192.168.68.109:5000
   - ESP32-A and ESP32-B should show as "Online"
   - No communication errors

## Physical Connections
Ensure ESP32s are connected to the SECOND RS485 channel:
- ESP32-A TX/RX → Waveshare HAT Channel 1 (ttySC1)
- ESP32-B TX/RX → Waveshare HAT Channel 1 (ttySC1)
- N4D3E16 remains on Channel 0 (ttySC0) at 9600 baud

Date: 2025-10-31
Status: Firmware updated, upload pending
