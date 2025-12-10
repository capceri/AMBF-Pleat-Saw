#!/bin/bash
# Pleat Saw Kiosk Mode Startup Script
# This script launches Chromium in kiosk mode pointing to the operator HMI

# Wait for the Flask server to be ready
echo "Waiting for Flask server to start..."
for i in {1..30}; do
    if curl -s http://localhost:5000 > /dev/null; then
        echo "Flask server is ready!"
        break
    fi
    sleep 1
done

# Disable screen blanking and power management
xset s off
xset -dpms
xset s noblank

# Hide mouse cursor after 5 seconds of inactivity
unclutter -idle 5 &

# Start Chromium in kiosk mode
chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-translate \
    --no-first-run \
    --start-fullscreen \
    --check-for-update-interval=31536000 \
    --disable-features=TranslateUI \
    --app=http://localhost:5000
