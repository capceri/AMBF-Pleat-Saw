// Pleat Saw Monitoring Dashboard - JavaScript

// Global state
let socket = null;
let currentOutputStates = {};
let currentInputOverrides = {};
let keypadTargetInput = null;
let keypadCurrentValue = '';

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initWebSocket();
    fetchDiagnostics();  // Check for hardware connection issues
    fetchInputOverrides(); // Get current input override states
    fetchEngineeringParams(); // Load saved engineering parameters into input fields
    initNumericKeypad(); // Enable on-screen keypad for numeric fields
        setupM2DeadmanButtons();
    logToConsole('Dashboard initialized', 'info');
});

function setupM2DeadmanButtons() {
    const fwdBtn = document.getElementById('m2-feed-fwd');
    const revBtn = document.getElementById('m2-feed-rev');

    const registerDeadman = (btn, onPress) => {
        if (!btn || !onPress) return;
        const handleDown = (e) => {
            e.preventDefault();
            onPress();
        };
        const handleUp = (e) => {
            e.preventDefault();
            stopM2();
        };
        ['pointerdown', 'mousedown', 'touchstart'].forEach(evt => btn.addEventListener(evt, handleDown));
        ['pointerup', 'pointerleave', 'mouseup', 'touchend', 'touchcancel'].forEach(evt => btn.addEventListener(evt, handleUp));
    };

    registerDeadman(fwdBtn, jogM2Forward);
    registerDeadman(revBtn, jogM2Reverse);
}

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
        const posElem = document.getElementById('m3-position');
        if (posElem && m3.position_mm !== undefined) {
            posElem.textContent = m3.position_mm.toFixed(3) + ' mm';
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
    // Persist the selected RPM so it survives reboot
    sendCommand('set_m1_rpm', { rpm: rpm });
    sendCommand('m1_start', { rpm: rpm });
}

function stopM1() {
    sendCommand('m1_stop');
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

function homeM2() {
    sendCommand('m2_home');
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
                const manualRpmInput = document.getElementById('m1-rpm');
                if (manualRpmInput) {
                    manualRpmInput.value = data.m1_rpm;
                }
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

function initNumericKeypad() {
    const keypad = document.getElementById('keypad-container');
    const backdrop = document.getElementById('keypad-backdrop');

    if (!keypad || !backdrop) {
        return;
    }

    document.querySelectorAll('.touch-keypad').forEach(input => {
        input.setAttribute('readonly', 'readonly');
        input.setAttribute('inputmode', 'none');
        input.style.cursor = 'pointer';

        const triggerOpen = (event) => {
            event.preventDefault();
            event.stopPropagation();
            input.blur();
            openKeypad(input);
        };

        input.addEventListener('click', triggerOpen);
        input.addEventListener('mousedown', triggerOpen);
        input.addEventListener('pointerdown', triggerOpen);
        input.addEventListener('touchstart', triggerOpen, { passive: false });
        input.addEventListener('focus', triggerOpen);
    });

    keypad.querySelectorAll('.keypad-btn').forEach(btn => {
        const value = btn.dataset.value;
        const action = btn.dataset.action;
        btn.addEventListener('click', () => {
            if (typeof value !== 'undefined') {
                handleKeypadValue(value);
            } else if (action) {
                handleKeypadAction(action);
            }
        });
    });

    backdrop.addEventListener('click', () => closeKeypad(true));
}

function openKeypad(input) {
    const container = document.getElementById('keypad-container');
    const backdrop = document.getElementById('keypad-backdrop');
    if (!container || !backdrop) {
        return;
    }

    if (!container.classList.contains('hidden') && keypadTargetInput === input) {
        return;
    }

    keypadTargetInput = input;
    keypadCurrentValue = input.value ? input.value.toString() : '';
    updateKeypadDisplay();

    backdrop.classList.remove('hidden');
    container.classList.remove('hidden');
}

function closeKeypad(cancelled = false) {
    const backdrop = document.getElementById('keypad-backdrop');
    const container = document.getElementById('keypad-container');
    if (backdrop) backdrop.classList.add('hidden');
    if (container) container.classList.add('hidden');

    keypadTargetInput = null;
    keypadCurrentValue = '';
}

function handleKeypadValue(value) {
    if (!keypadTargetInput) {
        return;
    }

    if (value === '.' && keypadCurrentValue.includes('.')) {
        return;
    }

    keypadCurrentValue += value;
    updateKeypadDisplay();
}

function handleKeypadAction(action) {
    switch (action) {
        case 'clear':
            keypadCurrentValue = '';
            updateKeypadDisplay();
            break;
        case 'back':
            keypadCurrentValue = keypadCurrentValue.slice(0, -1);
            updateKeypadDisplay();
            break;
        case 'sign':
            if (keypadCurrentValue.startsWith('-')) {
                keypadCurrentValue = keypadCurrentValue.substring(1);
            } else if (keypadCurrentValue.length > 0) {
                keypadCurrentValue = '-' + keypadCurrentValue;
            }
            updateKeypadDisplay();
            break;
        case 'ok':
            applyKeypadValue();
            closeKeypad();
            break;
        case 'cancel':
            closeKeypad(true);
            break;
        default:
            break;
    }
}

function updateKeypadDisplay() {
    const display = document.getElementById('keypad-display');
    if (!display) {
        return;
    }
    display.textContent = keypadCurrentValue === '' ? '0' : keypadCurrentValue;
}

function applyKeypadValue() {
    if (!keypadTargetInput) {
        return;
    }

    let valueToApply = keypadCurrentValue.trim();
    if (valueToApply === '' || valueToApply === '-' || valueToApply === '.' || valueToApply === '-.') {
        valueToApply = keypadTargetInput.min || '0';
    }

    keypadTargetInput.value = valueToApply;
    keypadTargetInput.dispatchEvent(new Event('input', { bubbles: true }));
    keypadTargetInput.dispatchEvent(new Event('change', { bubbles: true }));
}
