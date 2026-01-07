// Pleat Saw Monitoring Dashboard - JavaScript

// Global state
let socket = null;
let currentOutputStates = {};
let currentInputOverrides = {};
const DEFAULT_M3_OFFSET = 220.0;
let keypadTargetInput = null;
let keypadValue = '0';
let keypadOverlay = null;
let keypadDisplay = null;
let keyboardTargetInput = null;
let keyboardValue = '';
let keyboardOriginalValue = '';
let keyboardOverlay = null;
let keyboardDisplay = null;
let keyboardShift = false;
let keyboardShiftButton = null;

function ensureKeypadElements() {
    if (!keypadOverlay) {
        keypadOverlay = document.getElementById('numpad-overlay');
    }
    if (!keypadDisplay) {
        keypadDisplay = document.getElementById('numpad-display');
    }
    return !!(keypadOverlay && keypadDisplay);
}

function ensureKeyboardElements() {
    if (!keyboardOverlay) {
        keyboardOverlay = document.getElementById('keyboard-overlay');
    }
    if (!keyboardDisplay) {
        keyboardDisplay = document.getElementById('keyboard-display');
    }
    return !!(keyboardOverlay && keyboardDisplay);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initWebSocket();
    fetchDiagnostics();  // Check for hardware connection issues
    fetchInputOverrides(); // Get current input override states
    fetchEngineeringParams(); // Load saved engineering parameters into input fields
    initTouchKeypad(); // Enable on-screen keypad for numeric fields
    initTouchKeyboard(); // Enable on-screen keyboard for text fields
    initWifiPanel(); // Setup WiFi scan panel
    logToConsole('Dashboard initialized', 'info');
});

// WebSocket Connection
function initWebSocket() {
    socket = io();

    socket.on('connect', function() {
        updateConnectionStatus(true);
        logToConsole('Connected to server', 'success');
    });

    socket.on('disconnect', function() {
        updateConnectionStatus(false);
        logToConsole('Disconnected from server', 'error');
    });

    socket.on('update', function(data) {
        updateDashboard(data);
    });

    socket.on('command_result', function(result) {
        if (result.success) {
            logToConsole(result.message || 'Command executed successfully', 'success');
        } else {
            logToConsole('Command failed: ' + (result.error || 'Unknown error'), 'error');
        }
    });

    socket.on('status', function(data) {
        logToConsole(data.message, 'info');
    });

    socket.on('nextion_log', function(data) {
        logToNextion(data.message, data.direction, data.timestamp);
    });

    socket.on('nextion_stats', function(data) {
        updateNextionStats(data);
    });
}

// Update connection status indicator
function updateConnectionStatus(connected) {
    const indicator = document.getElementById('connection-indicator');
    const text = document.getElementById('connection-text');

    if (connected) {
        indicator.className = 'status-dot connected';
        text.textContent = 'Connected';
    } else {
        indicator.className = 'status-dot disconnected';
        text.textContent = 'Disconnected';
    }
}

// Fetch and display diagnostic information
function fetchDiagnostics() {
    fetch('/api/diagnostics')
        .then(response => response.json())
        .then(data => {
            updateDiagnostics(data);
        })
        .catch(error => {
            console.error('Error fetching diagnostics:', error);
        });
}

// Update diagnostics panel with connection status and errors
function updateDiagnostics(data) {
    const panel = document.getElementById('diagnostics-panel');
    const errorsDiv = document.getElementById('init-errors');

    // Check if there are any errors or disconnected hardware
    const hasErrors = data.init_errors && data.init_errors.length > 0;
    const modbusDisconnected = data.connections && !data.connections.modbus.connected;
    const nextionDisconnected = data.connections && !data.connections.nextion.connected;
    const hasIssues = hasErrors || modbusDisconnected || nextionDisconnected;

    // Show/hide diagnostics panel
    if (hasIssues) {
        panel.style.display = 'block';
    } else {
        panel.style.display = 'none';
        return;  // No issues to display
    }

    // Display initialization errors
    if (hasErrors) {
        errorsDiv.innerHTML = '<strong style="color: #e74c3c;">Initialization Errors:</strong>';
        data.init_errors.forEach(error => {
            const errorItem = document.createElement('div');
            errorItem.className = 'error-item';
            errorItem.textContent = error;
            errorsDiv.appendChild(errorItem);
        });
    } else {
        errorsDiv.innerHTML = '';
    }

    // Update connection status indicators
    if (data.connections) {
        // Modbus connection
        const modbusIndicator = document.getElementById('conn-modbus');
        const modbusDesc = document.getElementById('conn-modbus-desc');
        if (data.connections.modbus.connected) {
            modbusIndicator.className = 'connection-indicator connected';
            modbusIndicator.textContent = 'Connected';
        } else {
            modbusIndicator.className = 'connection-indicator disconnected';
            modbusIndicator.textContent = 'Disconnected';
        }
        modbusDesc.textContent = data.connections.modbus.description;

        // Nextion connection
        const nextionIndicator = document.getElementById('conn-nextion');
        const nextionDesc = document.getElementById('conn-nextion-desc');
        if (data.connections.nextion.connected) {
            nextionIndicator.className = 'connection-indicator connected';
            nextionIndicator.textContent = 'Connected';
        } else {
            nextionIndicator.className = 'connection-indicator disconnected';
            nextionIndicator.textContent = 'Disconnected';
        }
        nextionDesc.textContent = data.connections.nextion.description;
    }

    // Log to console
    if (hasIssues) {
        logToConsole('Hardware connection issues detected - check diagnostics panel', 'warning');
    }
}

// ===================== WiFi Panel =====================

function initWifiPanel() {
    const list = document.getElementById('wifi-networks');
    if (!list) {
        return;
    }
    scanWifi();
}

function scanWifi() {
    const current = document.getElementById('wifi-current');
    if (current) {
        current.textContent = 'Scanning...';
    }
    setWifiMessage('Scanning for networks...', 'info');

    fetch('/api/wifi/scan')
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                setWifiMessage(data.error || 'WiFi scan failed.', 'error');
                if (current) {
                    current.textContent = 'Scan failed';
                }
                renderWifiNetworks([]);
                return;
            }
            renderWifiNetworks(data.networks || []);
            setWifiMessage('', '');
        })
        .catch(error => {
            console.error('Error scanning WiFi:', error);
            setWifiMessage('WiFi scan failed.', 'error');
            if (current) {
                current.textContent = 'Scan failed';
            }
            renderWifiNetworks([]);
        });
}

function renderWifiNetworks(networks) {
    const list = document.getElementById('wifi-networks');
    const current = document.getElementById('wifi-current');
    if (!list) {
        return;
    }

    list.innerHTML = '';
    if (!networks || networks.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'wifi-empty';
        empty.textContent = 'No networks found.';
        list.appendChild(empty);
        if (current) {
            current.textContent = 'No networks detected';
        }
        return;
    }

    const active = networks.find(network => network.in_use);
    if (current) {
        if (active) {
            const activeName = active.ssid ? active.ssid : '<hidden>';
            current.textContent = `Connected: ${activeName}`;
        } else {
            current.textContent = 'Not connected';
        }
    }

    networks.forEach(network => {
        const row = document.createElement('div');
        row.className = 'wifi-network';
        if (network.in_use) {
            row.classList.add('active');
        }

        const ssid = network.ssid ? network.ssid : '<hidden>';
        const signal = network.signal !== null && network.signal !== undefined ? `${network.signal}%` : '--';
        const security = network.security ? network.security : 'OPEN';

        row.innerHTML = `
            <div>
                <div class="ssid">${ssid}</div>
                <div class="meta">${security}</div>
            </div>
            <div class="signal">${signal}</div>
        `;

        row.addEventListener('click', () => {
            const ssidInput = document.getElementById('wifi-ssid');
            const passwordInput = document.getElementById('wifi-password');
            if (ssidInput && network.ssid) {
                ssidInput.value = network.ssid;
                ssidInput.dispatchEvent(new Event('input', { bubbles: true }));
                if (passwordInput) {
                    passwordInput.focus();
                }
            }
        });

        list.appendChild(row);
    });
}

function connectWifi() {
    const ssidInput = document.getElementById('wifi-ssid');
    const passwordInput = document.getElementById('wifi-password');
    if (!ssidInput) {
        return;
    }

    const ssid = (ssidInput.value || '').trim();
    const password = passwordInput ? passwordInput.value || '' : '';

    if (!ssid) {
        setWifiMessage('SSID is required.', 'error');
        return;
    }

    setWifiMessage(`Connecting to ${ssid}...`, 'info');

    fetch('/api/wifi/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ssid, password })
    })
        .then(response => response.json().then(data => ({ status: response.status, data })))
        .then(result => {
            if (!result.data.success) {
                setWifiMessage(result.data.error || 'WiFi connection failed.', 'error');
                return;
            }
            setWifiMessage(result.data.message || 'WiFi connected.', 'success');
            setTimeout(scanWifi, 2000);
        })
        .catch(error => {
            console.error('Error connecting WiFi:', error);
            setWifiMessage('WiFi connection failed.', 'error');
        });
}

function clearWifiForm() {
    const ssidInput = document.getElementById('wifi-ssid');
    const passwordInput = document.getElementById('wifi-password');
    if (ssidInput) {
        ssidInput.value = '';
    }
    if (passwordInput) {
        passwordInput.value = '';
    }
    setWifiMessage('', '');
}

function setWifiMessage(message, level) {
    const messageEl = document.getElementById('wifi-message');
    if (!messageEl) {
        return;
    }
    messageEl.textContent = message || '';
    messageEl.className = 'wifi-message';
    if (level === 'success') {
        messageEl.classList.add('success');
    } else if (level === 'error') {
        messageEl.classList.add('error');
    }
}

// Update entire dashboard with new data
function updateDashboard(data) {
    if (data.system) {
        updateSystemStatus(data.system);
    }
    if (data.inputs) {
        updateInputs(data.inputs.inputs);
    }
    if (data.outputs) {
        updateOutputs(data.outputs.outputs);
    }
    if (data.motors) {
        updateMotors(data.motors);
    }
}

// Update system status panel
function updateSystemStatus(system) {
    const stateElem = document.getElementById('system-state');
    const safetyElem = document.getElementById('system-safety');
    const lightCurtainElem = document.getElementById('system-light-curtain');
    const pausedElem = document.getElementById('system-paused');
    const alarmElem = document.getElementById('system-alarm');
    const cycleElem = document.getElementById('cycle-count');
    const uptimeElem = document.getElementById('uptime');

    // State
    if (stateElem) {
        stateElem.textContent = system.state || 'UNKNOWN';
        stateElem.className = 'value state-' + (system.state || 'unknown').toLowerCase();
    }

    // Safety
    if (safetyElem) {
        safetyElem.textContent = system.safety || 'UNKNOWN';
        safetyElem.className = 'value safety-' + (system.safety === 'READY' ? 'ready' : 'not-ready');
    }

    // Light Curtain
    if (lightCurtainElem) {
        lightCurtainElem.textContent = system.light_curtain || 'UNKNOWN';
        lightCurtainElem.className = 'value safety-' + (system.light_curtain === 'OK' ? 'ready' : 'not-ready');
    }

    // Pause Status
    if (pausedElem) {
        pausedElem.textContent = system.paused || 'RUNNING';
        pausedElem.className = 'value ' + (system.paused === 'PAUSED' ? 'paused' : 'running');
        pausedElem.style.color = system.paused === 'PAUSED' ? 'var(--warning-color)' : 'var(--success-color)';
    }

    // Alarm
    if (alarmElem) {
        alarmElem.textContent = system.alarm || 'None';
        alarmElem.style.color = system.alarm ? 'var(--danger-color)' : 'var(--success-color)';
    }

    // Cycle count
    if (cycleElem) {
        cycleElem.textContent = system.cycle_count || 0;
    }

    // Uptime
    if (uptimeElem && system.uptime !== undefined) {
        uptimeElem.textContent = formatUptime(system.uptime);
    }
}

// Update inputs
function updateInputs(inputs) {
    if (!inputs) return;

    updateIOIndicator('input-start', inputs.start);
    updateIOIndicator('input-sensor2', inputs.sensor2);
    updateIOIndicator('input-sensor3', inputs.sensor3);
    updateIOIndicator('input-light-curtain', inputs.light_curtain, inputs.light_curtain ? 'OK' : 'BLOCKED');
    updateIOIndicator('input-safety', inputs.safety, inputs.safety ? 'READY' : 'NOT READY');
}

// Update outputs
function updateOutputs(outputs) {
    if (!outputs) return;

    currentOutputStates = outputs;

    updateIOIndicator('output-clamp', outputs.clamp);
    updateIOIndicator('output-air_jet', outputs.air_jet);
    updateIOIndicator('output-green_solid', outputs.green_solid);
    updateIOIndicator('output-green_flash', outputs.green_flash);
}

// Update a single I/O indicator
function updateIOIndicator(elemId, state, customText = null) {
    const elem = document.getElementById(elemId);
    if (!elem) return;

    if (state) {
        elem.className = 'io-indicator on';
        elem.textContent = customText || 'ON';
    } else {
        elem.className = 'io-indicator off';
        elem.textContent = customText || 'OFF';
    }
}

// Update motors
function updateMotors(motors) {
    if (!motors) return;

    // M1 Blade
    if (motors.m1_blade) {
        const m1 = motors.m1_blade;
        updateIOIndicator('m1-running', m1.running, m1.running ? 'YES' : 'NO');
        updateIOIndicator('m1-fault', m1.fault, m1.fault ? 'YES' : 'NO');
        updateIOIndicator('m1-ready', m1.ready, m1.ready ? 'YES' : 'NO');
    }

    // M2 Fixture
    if (motors.m2_fixture) {
        const m2 = motors.m2_fixture;
        updateIOIndicator('m2-motion', m2.in_motion, m2.in_motion ? 'YES' : 'NO');
        updateIOIndicator('m2-at-s2', m2.at_s2, m2.at_s2 ? 'YES' : 'NO');
        updateIOIndicator('m2-at-s3', m2.at_s3, m2.at_s3 ? 'YES' : 'NO');
        updateIOIndicator('m2-fault', m2.fault, m2.fault ? 'YES' : 'NO');
    }

    // M3 Backstop
    if (motors.m3_backstop) {
        const m3 = motors.m3_backstop;
        const offset = typeof m3.offset_mm === 'number' ? m3.offset_mm : DEFAULT_M3_OFFSET;
        const rawPos = typeof m3.raw_position_mm === 'number'
            ? m3.raw_position_mm
            : (typeof m3.position_mm === 'number' ? m3.position_mm - offset : 0);
        const displayPos = typeof m3.position_mm === 'number' ? m3.position_mm : rawPos + offset;
        const posElem = document.getElementById('m3-position');
        if (posElem) {
            posElem.textContent = displayPos.toFixed(3) + ' mm';
        }
        const rawElem = document.getElementById('m3-position-raw');
        if (rawElem) {
            rawElem.textContent = rawPos.toFixed(3) + ' mm';
        }
        const offsetInput = document.getElementById('m3-offset');
        const keypadActive = keypadOverlay && keypadOverlay.classList && keypadOverlay.classList.contains('show');
        if (offsetInput && document.activeElement !== offsetInput && !(keypadActive && keypadTargetInput === offsetInput)) {
            offsetInput.value = offset.toFixed(3);
        }
        updateIOIndicator('m3-motion', m3.in_motion, m3.in_motion ? 'YES' : 'NO');
        updateIOIndicator('m3-at-target', m3.at_target, m3.at_target ? 'YES' : 'NO');
        updateIOIndicator('m3-homed', m3.homed, m3.homed ? 'YES' : 'NO');
        updateIOIndicator('m3-fault', m3.fault, m3.fault ? 'YES' : 'NO');
    }
}

// Update statistics (called separately via periodic fetch)
function updateStatistics(stats) {
    if (!stats) return;

    if (stats.modbus) {
        setTextContent('stat-modbus-reads', stats.modbus.read_count || 0);
        setTextContent('stat-modbus-writes', stats.modbus.write_count || 0);
        setTextContent('stat-modbus-errors', stats.modbus.error_count || 0);
    }

    if (stats.io) {
        setTextContent('stat-io-polls', stats.io.poll_count || 0);
        setTextContent('stat-io-changes', stats.io.change_count || 0);
    }

    if (stats.supervisor) {
        setTextContent('stat-alarms', stats.supervisor.total_alarms || 0);
    }
}

// Periodically fetch statistics and input overrides
setInterval(function() {
    fetch('/api/statistics')
        .then(response => response.json())
        .then(data => updateStatistics(data))
        .catch(err => console.error('Failed to fetch statistics:', err));
}, 1000);

setInterval(function() {
    fetchInputOverrides();
}, 500);

// Command Functions

function sendCommand(command, params = {}) {
    if (!socket || !socket.connected) {
        logToConsole('Not connected to server', 'error');
        return;
    }

    socket.emit('command', {
        command: command,
        params: params
    });

    logToConsole('Sent command: ' + command, 'info');
}

function startCycle() {
    sendCommand('start_cycle');
}

function stopCycle() {
    if (confirm('Execute Emergency Stop?')) {
        sendCommand('stop_cycle');
    }
}

function resetAlarms() {
    sendCommand('reset_alarms');
}

function toggleOutput(outputName) {
    const currentState = currentOutputStates[outputName] || false;
    sendCommand('set_output', {
        name: outputName,
        state: !currentState
    });
}

function startM1() {
    const rpm = parseInt(document.getElementById('m1-rpm').value);
    if (rpm < 5 || rpm > 3500) {
        logToConsole('RPM must be between 5 and 3500', 'error');
        return;
    }
    sendCommand('m1_start', { rpm: rpm });
}

function stopM1() {
    sendCommand('m1_stop');
}

function jogM1Pulses() {
    const rpm = parseInt(document.getElementById('m1-rpm').value);
    const pulses = parseInt(document.getElementById('m1-pulses').value);
    if (rpm < 5 || rpm > 3500) {
        logToConsole('RPM must be between 5 and 3500', 'error');
        return;
    }
    if (isNaN(pulses) || pulses <= 0) {
        logToConsole('Pulse count must be greater than zero', 'error');
        return;
    }
    sendCommand('m1_jog_pulses', { rpm: rpm, pulses: pulses });
}

function jogM2Forward() {
    const vel = parseInt(document.getElementById('m2-vel').value);
    if (vel < 10 || vel > 400) {
        logToConsole('Velocity must be between 10 and 400 mm/s', 'error');
        return;
    }
    sendCommand('m2_jog_forward', { vel: vel });
}

function jogM2Reverse() {
    const vel = parseInt(document.getElementById('m2-vel').value);
    if (vel < 10 || vel > 400) {
        logToConsole('Velocity must be between 10 and 400 mm/s', 'error');
        return;
    }
    sendCommand('m2_jog_reverse', { vel: vel });
}

function jogM2Pulses(forward) {
    const vel = parseInt(document.getElementById('m2-vel').value);
    const pulses = parseInt(document.getElementById('m2-pulses').value);
    if (vel < 10 || vel > 400) {
        logToConsole('Velocity must be between 10 and 400 mm/s', 'error');
        return;
    }
    if (isNaN(pulses) || pulses <= 0) {
        logToConsole('Pulse count must be greater than zero', 'error');
        return;
    }
    const command = forward ? 'm2_jog_pulses_forward' : 'm2_jog_pulses_reverse';
    sendCommand(command, { pulses: pulses, vel: vel });
}

function stopM2() {
    sendCommand('m2_stop');
}

function gotoM3() {
    const target = parseFloat(document.getElementById('m3-target').value);
    if (target < 0 || target > 1000) {
        logToConsole('Target must be between 0 and 1000 mm', 'error');
        return;
    }
    sendCommand('m3_goto', { position: target });
}

function homeM3() {
    sendCommand('m3_home');
}

function stopM3() {
    sendCommand('m3_stop');
}

function updateM3Offset() {
    const offset = parseFloat(document.getElementById('m3-offset').value);
    if (isNaN(offset) || offset < 0) {
        logToConsole('Offset must be zero or positive', 'error');
        return;
    }
    sendCommand('set_m3_offset', { offset_mm: offset });
}

// Input Override Functions

function fetchInputOverrides() {
    fetch('/api/input_overrides')
        .then(response => response.json())
        .then(data => {
            if (data.overrides) {
                currentInputOverrides = data.overrides;
                updateInputOverrideUI();
            }
        })
        .catch(error => {
            console.error('Error fetching input overrides:', error);
        });
}

function fetchEngineeringParams() {
    fetch('/api/engineering_params')
        .then(response => response.json())
        .then(data => {
            // Populate M1 auto RPM input field
            if (data.m1_rpm !== undefined) {
                document.getElementById('m1-auto-rpm').value = data.m1_rpm;
            }

            // Populate M2 auto velocity input fields
            if (data.m2_vel_fwd_mm_s !== undefined) {
                document.getElementById('m2-auto-vel-fwd').value = data.m2_vel_fwd_mm_s;
            }
            if (data.m2_vel_rev_mm_s !== undefined) {
                document.getElementById('m2-auto-vel-rev').value = data.m2_vel_rev_mm_s;
            }

            // Populate M2 timeout input fields
            if (data.m2_fwd_timeout !== undefined) {
                document.getElementById('m2-timeout-fwd').value = data.m2_fwd_timeout;
            }
            if (data.m2_rev_timeout !== undefined) {
                document.getElementById('m2-timeout-rev').value = data.m2_rev_timeout;
            }

            if (data.m3_offset_mm !== undefined) {
                const offsetInput = document.getElementById('m3-offset');
                if (offsetInput && document.activeElement !== offsetInput) {
                    offsetInput.value = parseFloat(data.m3_offset_mm).toFixed(3);
                }
            } else {
                const offsetInput = document.getElementById('m3-offset');
                if (offsetInput && document.activeElement !== offsetInput) {
                    offsetInput.value = DEFAULT_M3_OFFSET.toFixed(3);
                }
            }

            logToConsole('Engineering parameters loaded', 'info');
        })
        .catch(error => {
            console.error('Error fetching engineering parameters:', error);
            logToConsole('Failed to load engineering parameters, using defaults', 'warning');
        });
}

function updateInputOverrideUI() {
    for (const [inputName, overrideState] of Object.entries(currentInputOverrides)) {
        const buttonElem = document.getElementById(`toggle-${inputName}`);
        const indicatorElem = document.getElementById(`override-${inputName}`);

        if (!buttonElem || !indicatorElem) continue;

        if (overrideState !== null) {
            // Override is active
            indicatorElem.style.display = 'inline';
            buttonElem.className = 'btn-small btn-toggle override-active';
            buttonElem.textContent = overrideState ? getForceOnText(inputName) : getForceOffText(inputName);
        } else {
            // No override
            indicatorElem.style.display = 'none';
            buttonElem.className = 'btn-small btn-toggle';
            buttonElem.textContent = getForceOnText(inputName);
        }
    }
}

function getForceOnText(inputName) {
    switch (inputName) {
        case 'start': return 'Force ON';
        case 'sensor2': return 'Force ON';
        case 'sensor3': return 'Force ON';
        case 'light_curtain': return 'Force OK';
        case 'safety': return 'Force READY';
        default: return 'Force ON';
    }
}

function getForceOffText(inputName) {
    switch (inputName) {
        case 'start': return 'Force OFF';
        case 'sensor2': return 'Force OFF';
        case 'sensor3': return 'Force OFF';
        case 'light_curtain': return 'Force BLOCKED';
        case 'safety': return 'Force NOT READY';
        default: return 'Force OFF';
    }
}

function toggleInputOverride(inputName) {
    const currentOverride = currentInputOverrides[inputName];
    let newState;

    if (currentOverride === null) {
        // No override currently, set to ON/READY/OK
        newState = true;
    } else if (currentOverride === true) {
        // Currently forced ON, toggle to OFF
        newState = false;
    } else {
        // Currently forced OFF, disable override
        newState = null;
    }

    sendCommand('set_input_override', {
        name: inputName,
        state: newState
    });

    // Update local state immediately for responsive UI
    currentInputOverrides[inputName] = newState;
    updateInputOverrideUI();
}

function clearAllInputOverrides() {
    if (confirm('Clear all input overrides and return to hardware values?')) {
        sendCommand('clear_input_overrides');

        // Clear local state
        for (const inputName in currentInputOverrides) {
            currentInputOverrides[inputName] = null;
        }
        updateInputOverrideUI();

        logToConsole('All input overrides cleared', 'info');
    }
}


// Update Auto Cycle Parameters

function updateM1AutoRpm() {
    const rpm = parseInt(document.getElementById('m1-auto-rpm').value);
    if (rpm >= 5 && rpm <= 3500) {
        sendCommand('set_m1_rpm', { rpm: rpm });
    }
}

function updateM2AutoFwdVelocity() {
    const vel = parseInt(document.getElementById('m2-auto-vel-fwd').value);
    if (vel >= 10 && vel <= 400) {
        sendCommand('set_m2_fwd_velocity', { vel: vel });
        logToConsole(`M2 auto forward velocity set to ${vel} mm/s`, 'success');
    } else {
        logToConsole('Forward velocity must be between 10 and 400 mm/s', 'error');
    }
}

function updateM2AutoRevVelocity() {
    const vel = parseInt(document.getElementById('m2-auto-vel-rev').value);
    if (vel >= 10 && vel <= 400) {
        sendCommand('set_m2_rev_velocity', { vel: vel });
        logToConsole(`M2 auto reverse velocity set to ${vel} mm/s`, 'success');
    } else {
        logToConsole('Reverse velocity must be between 10 and 400 mm/s', 'error');
    }
}
// Utility Functions

function formatUptime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

function setTextContent(elemId, value) {
    const elem = document.getElementById(elemId);
    if (elem) {
        elem.textContent = value;
    }
}

function logToConsole(message, type = 'info') {
    const consoleElem = document.getElementById('console');
    if (!consoleElem) return;

    const timestamp = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = 'console-entry ' + type;
    entry.innerHTML = `<span class="console-timestamp">[${timestamp}]</span>${message}`;

    consoleElem.appendChild(entry);
    consoleElem.scrollTop = consoleElem.scrollHeight;

    // Limit to 100 entries
    while (consoleElem.children.length > 100) {
        consoleElem.removeChild(consoleElem.firstChild);
    }
}

function logToNextion(message, direction, timestamp) {
    const nextionLog = document.getElementById('nextion-log');
    if (!nextionLog) return;

    const time = timestamp ? new Date(timestamp * 1000).toLocaleTimeString() : new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = 'console-entry';

    // Color code by direction: TX = green, RX = blue
    const arrow = direction === 'TX' ? '→' : '←';
    const color = direction === 'TX' ? '#4CAF50' : '#2196F3';

    entry.innerHTML = `<span class="console-timestamp">[${time}]</span><span style="color: ${color}; font-weight: bold;">${arrow} ${direction}:</span> ${message}`;

    nextionLog.appendChild(entry);
    nextionLog.scrollTop = nextionLog.scrollHeight;

    // Limit to 100 entries
    while (nextionLog.children.length > 100) {
        nextionLog.removeChild(nextionLog.firstChild);
    }
}

function updateNextionStats(data) {
    const txCount = document.getElementById('nextion-tx-count');
    const rxCount = document.getElementById('nextion-rx-count');
    const errors = document.getElementById('nextion-errors');
    const status = document.getElementById('nextion-status');

    if (txCount) txCount.textContent = data.tx_count || 0;
    if (rxCount) rxCount.textContent = data.rx_count || 0;
    if (errors) errors.textContent = data.parse_errors || 0;
    if (status) {
        status.textContent = data.connected ? 'CONNECTED' : 'DISCONNECTED';
        status.style.color = data.connected ? 'var(--success-color)' : 'var(--error-color)';
    }
}

// ===================== On-screen Keypad =====================

function initTouchKeypad() {
    console.log('[KEYPAD] Initializing touch keypad...');
    ensureKeypadElements();
    const keypadButtons = document.querySelectorAll('.numpad-btn[data-num]');
    const keypadClear = document.getElementById('numpad-clear');
    const keypadEnter = document.getElementById('numpad-enter');
    const keypadCancel = document.getElementById('numpad-cancel');

    console.log('[KEYPAD] Found overlay:', !!keypadOverlay, 'display:', !!keypadDisplay);
    console.log('[KEYPAD] Found buttons:', keypadButtons.length);

    if (!keypadOverlay || !keypadDisplay) {
        console.error('[KEYPAD] Missing required elements - aborting initialization');
        return;
    }

    const inputs = document.querySelectorAll('.touch-keypad');
    console.log('[KEYPAD] Found', inputs.length, 'touch-keypad inputs');

    inputs.forEach((input, index) => {
        input.setAttribute('readonly', 'readonly');
        input.setAttribute('inputmode', 'none');
        input.style.cursor = 'pointer';

        const open = (event) => {
            console.log('[KEYPAD] Input clicked:', input.id);
            event.preventDefault();
            event.stopPropagation();
            openInputKeypad(input);
        };

        input.addEventListener('click', open);
        input.addEventListener('touchstart', open, { passive: false });
        input.addEventListener('focus', open);
        console.log('[KEYPAD] Attached handlers to input', index + 1, ':', input.id);
    });

    keypadButtons.forEach(button => {
        button.addEventListener('click', (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            handleNumpadDigit(button.getAttribute('data-num'));
        });
    });

    if (keypadClear) {
        keypadClear.addEventListener('click', (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            handleNumpadClear();
        });
    }

    if (keypadEnter) {
        keypadEnter.addEventListener('click', (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            commitNumpadValue();
        });
    }

    if (keypadCancel) {
        keypadCancel.addEventListener('click', (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            closeInputKeypad();
        });
    }

    keypadOverlay.addEventListener('click', (e) => {
        if (e.target === keypadOverlay) {
            closeInputKeypad();
        }
    });

    // Fallback event delegation for dynamically added inputs
    document.addEventListener('click', (e) => {
        const target = e.target;
        if (target && target.classList && target.classList.contains('touch-keypad')) {
            e.preventDefault();
            e.stopPropagation();
            openInputKeypad(target);
        }
    }, true);
}

function openInputKeypad(input) {
    if (!ensureKeypadElements()) {
        console.error('[KEYPAD] Cannot open keypad - elements missing');
        return;
    }
    console.log('[KEYPAD] Opening keypad for input:', input.id, 'value:', input.value);
    keypadTargetInput = input;
    const currentVal = input.value ? input.value.toString() : '';
    keypadValue = currentVal.replace(/^0+/, '');
    if (keypadValue === '') {
        keypadValue = '';
    }
    updateNumpadDisplay();
    keypadOverlay.classList.add('show');
    console.log('[KEYPAD] Overlay classes:', keypadOverlay.className);
}

function closeInputKeypad() {
    if (keypadOverlay) {
        keypadOverlay.classList.remove('show');
    }
    keypadTargetInput = null;
    keypadValue = '0';
}

function handleNumpadDigit(digit) {
    if (!keypadTargetInput) {
        return;
    }

    if (digit === '.') {
        if (!keypadValue.includes('.')) {
            keypadValue += '.';
        }
    } else {
        if (keypadValue === '0' || keypadValue === '') {
            keypadValue = digit;
        } else if (keypadValue.length < 12) {
            keypadValue += digit;
        }
    }

    updateNumpadDisplay();
}

function handleNumpadClear() {
    if (keypadValue.length > 1) {
        keypadValue = keypadValue.slice(0, -1);
    } else {
        keypadValue = '0';
    }
    updateNumpadDisplay();
}

function updateNumpadDisplay() {
    if (!keypadDisplay) {
        return;
    }
    keypadDisplay.textContent = keypadValue;
}

function commitNumpadValue() {
    if (!keypadTargetInput) {
        closeInputKeypad();
        return;
    }

    let finalValue = keypadValue;
    if (finalValue === '' || finalValue === '-' || finalValue === '.' || finalValue === '-.') {
        finalValue = '0';
    }

    keypadTargetInput.value = finalValue;
    keypadTargetInput.dispatchEvent(new Event('input', { bubbles: true }));
    keypadTargetInput.dispatchEvent(new Event('change', { bubbles: true }));

    // Auto-apply offset so it doesn't revert on live updates
    if (keypadTargetInput.id === 'm3-offset') {
        updateM3Offset();
    }

    closeInputKeypad();
}

// ===================== On-screen Keyboard =====================

function initTouchKeyboard() {
    ensureKeyboardElements();
    keyboardShiftButton = document.getElementById('keyboard-shift');
    const keyButtons = document.querySelectorAll('.keyboard-btn[data-key]');
    const keyboardBackspace = document.getElementById('keyboard-backspace');
    const keyboardClear = document.getElementById('keyboard-clear');
    const keyboardEnter = document.getElementById('keyboard-enter');
    const keyboardCancel = document.getElementById('keyboard-cancel');
    const keyboardSpace = document.getElementById('keyboard-space');

    if (!keyboardOverlay || !keyboardDisplay) {
        console.error('[KEYBOARD] Missing required elements - aborting initialization');
        return;
    }

    const inputs = document.querySelectorAll('.touch-keyboard');
    inputs.forEach((input) => {
        input.setAttribute('readonly', 'readonly');
        input.setAttribute('inputmode', 'none');
        input.style.cursor = 'pointer';

        const open = (event) => {
            event.preventDefault();
            event.stopPropagation();
            openTouchKeyboard(input);
        };

        input.addEventListener('click', open);
        input.addEventListener('touchstart', open, { passive: false });
        input.addEventListener('focus', open);
    });

    keyButtons.forEach(button => {
        button.addEventListener('click', (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            handleKeyboardKey(button.getAttribute('data-key'));
        });
    });

    if (keyboardBackspace) {
        keyboardBackspace.addEventListener('click', (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            handleKeyboardBackspace();
        });
    }

    if (keyboardClear) {
        keyboardClear.addEventListener('click', (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            clearKeyboardValue();
        });
    }

    if (keyboardEnter) {
        keyboardEnter.addEventListener('click', (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            commitKeyboardValue();
        });
    }

    if (keyboardCancel) {
        keyboardCancel.addEventListener('click', (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            cancelKeyboard();
        });
    }

    if (keyboardShiftButton) {
        keyboardShiftButton.addEventListener('click', (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            toggleKeyboardShift();
        });
    }

    if (keyboardSpace) {
        keyboardSpace.addEventListener('click', (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            handleKeyboardKey(' ');
        });
    }

    keyboardOverlay.addEventListener('click', (e) => {
        if (e.target === keyboardOverlay) {
            cancelKeyboard();
        }
    });

    document.addEventListener('click', (e) => {
        const target = e.target;
        if (target && target.classList && target.classList.contains('touch-keyboard')) {
            e.preventDefault();
            e.stopPropagation();
            openTouchKeyboard(target);
        }
    }, true);
}

function openTouchKeyboard(input) {
    if (!ensureKeyboardElements()) {
        return;
    }
    keyboardTargetInput = input;
    keyboardOriginalValue = input.value || '';
    keyboardValue = keyboardOriginalValue;
    keyboardShift = false;
    updateKeyboardShiftVisual();
    updateKeyboardDisplay();
    keyboardOverlay.classList.add('show');
}

function closeTouchKeyboard() {
    if (keyboardOverlay) {
        keyboardOverlay.classList.remove('show');
    }
    keyboardTargetInput = null;
    keyboardValue = '';
    keyboardOriginalValue = '';
}

function toggleKeyboardShift() {
    keyboardShift = !keyboardShift;
    updateKeyboardShiftVisual();
}

function updateKeyboardShiftVisual() {
    if (keyboardShiftButton) {
        if (keyboardShift) {
            keyboardShiftButton.classList.add('active');
        } else {
            keyboardShiftButton.classList.remove('active');
        }
    }
}

function handleKeyboardKey(key) {
    if (!keyboardTargetInput) {
        return;
    }
    let nextChar = key;
    if (keyboardShift && key.length === 1 && key >= 'a' && key <= 'z') {
        nextChar = key.toUpperCase();
    }
    keyboardValue += nextChar;
    updateKeyboardDisplay();
}

function handleKeyboardBackspace() {
    if (!keyboardTargetInput) {
        return;
    }
    if (keyboardValue.length > 0) {
        keyboardValue = keyboardValue.slice(0, -1);
    }
    updateKeyboardDisplay();
}

function clearKeyboardValue() {
    keyboardValue = '';
    updateKeyboardDisplay();
}

function updateKeyboardDisplay() {
    if (!keyboardDisplay) {
        return;
    }
    keyboardDisplay.textContent = keyboardValue;
    if (keyboardTargetInput) {
        keyboardTargetInput.value = keyboardValue;
        keyboardTargetInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
}

function commitKeyboardValue() {
    if (!keyboardTargetInput) {
        closeTouchKeyboard();
        return;
    }
    keyboardTargetInput.value = keyboardValue;
    keyboardTargetInput.dispatchEvent(new Event('input', { bubbles: true }));
    keyboardTargetInput.dispatchEvent(new Event('change', { bubbles: true }));
    closeTouchKeyboard();
}

function cancelKeyboard() {
    if (keyboardTargetInput) {
        keyboardTargetInput.value = keyboardOriginalValue;
        keyboardTargetInput.dispatchEvent(new Event('input', { bubbles: true }));
        keyboardTargetInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
    closeTouchKeyboard();
}
