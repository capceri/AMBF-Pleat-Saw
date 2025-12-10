"""
Unit tests for supervisor state machine.
Tests state transitions, timeouts, and safety interlocks.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.supervisor import Supervisor, State


@pytest.fixture
def mock_io():
    """Mock IOPoller."""
    io = Mock()
    io.get_input = Mock(return_value=True)
    io.set_output = Mock(return_value=True)
    io.set_outputs = Mock(return_value=True)
    return io


@pytest.fixture
def mock_axis():
    """Mock AxisGateway."""
    axis = Mock()
    axis.m1_start = Mock(return_value=True)
    axis.m1_stop = Mock(return_value=True)
    axis.m1_get_status = Mock(return_value={'running': True, 'fault': False, 'ready': True})
    axis.m2_set_velocity = Mock(return_value=True)
    axis.m2_feed_forward = Mock(return_value=True)
    axis.m2_feed_reverse = Mock(return_value=True)
    axis.m2_stop = Mock(return_value=True)
    axis.m2_get_status = Mock(return_value={'in_motion': False, 'at_s2': False, 'at_s3': False, 'fault': False, 'homed': True})
    axis.m3_get_position = Mock(return_value=100.0)
    axis.emergency_stop_all = Mock()
    return axis


@pytest.fixture
def mock_hmi():
    """Mock NextionBridge."""
    hmi = Mock()
    hmi.update_multiple = Mock()
    hmi.update_position_mm = Mock()
    return hmi


@pytest.fixture
def test_config():
    """Test configuration."""
    return {
        'motion': {
            'm1_blade': {
                'rpm_default': 3500,
                'ramp_ms': 200,
                'timeout_start_s': 3.0,
            },
            'm2_fixture': {
                'default_speed_mm_s': 120.0,
                'default_accel_mm_s2': 2000.0,
                'timeout_fwd_s': 5.0,
                'timeout_rev_s': 5.0,
            },
            'cycle': {
                'dwell_after_s3_s': 1.5,
                'air_jet_s': 1.0,
                'saw_spindown_s': 0.5,
                'clamp_confirm_s': 0.1,
            },
        },
        'system': {
            'safety': {
                'watchdog_timeout_s': 1.0,
            },
        },
    }


@pytest.fixture
def supervisor(mock_io, mock_axis, mock_hmi, test_config):
    """Create supervisor instance for testing."""
    return Supervisor(mock_io, mock_axis, mock_hmi, test_config, loop_rate_hz=50.0)


def test_init_state(supervisor):
    """Test initial state."""
    assert supervisor.state == State.INIT


def test_transition_to(supervisor):
    """Test state transition."""
    supervisor._transition_to(State.IDLE)
    assert supervisor.state == State.IDLE
    assert supervisor.prev_state == State.INIT


def test_safety_ok_initially(supervisor, mock_io):
    """Test safety check with safety OK."""
    mock_io.get_input.return_value = True
    supervisor._check_safety()
    assert supervisor.safety_ok == True


def test_safety_drop_triggers_estop(supervisor, mock_io, mock_axis):
    """Test that safety drop triggers emergency stop."""
    # Set initial safety OK
    mock_io.get_input.return_value = True
    supervisor._check_safety()
    assert supervisor.safety_ok == True

    # Move to active state
    supervisor._transition_to(State.FEED_FWD)

    # Drop safety
    mock_io.get_input.return_value = False
    supervisor._check_safety()

    # Should have triggered emergency stop
    mock_axis.emergency_stop_all.assert_called_once()
    assert supervisor.state == State.ESTOP
    assert supervisor.current_alarm == "SAFETY_ESTOP"


def test_alarm_latched(supervisor):
    """Test alarm latching."""
    supervisor._raise_alarm("TEST_ALARM")

    assert supervisor.current_alarm == "TEST_ALARM"
    assert supervisor.alarm_latched == True
    assert supervisor.state == State.ALARM


def test_reset_alarms_with_safety_ok(supervisor, mock_io):
    """Test resetting alarms when safety is OK."""
    # Set safety OK
    mock_io.get_input.return_value = True
    supervisor._check_safety()

    # Raise alarm
    supervisor._raise_alarm("TEST_ALARM")
    assert supervisor.alarm_latched == True

    # Reset alarms
    result = supervisor.reset_alarms()

    assert result == True
    assert supervisor.alarm_latched == False
    assert supervisor.current_alarm == ""
    assert supervisor.state == State.IDLE


def test_reset_alarms_with_safety_not_ok(supervisor, mock_io):
    """Test resetting alarms when safety is not OK."""
    # Set safety not OK
    mock_io.get_input.return_value = False
    supervisor._check_safety()

    # Raise alarm
    supervisor._raise_alarm("TEST_ALARM")

    # Try to reset alarms
    result = supervisor.reset_alarms()

    # Should fail
    assert result == False
    assert supervisor.alarm_latched == True


def test_state_idle_to_precheck_on_start(supervisor, mock_io):
    """Test transition from IDLE to PRECHECK on start button."""
    supervisor._transition_to(State.IDLE)

    # Simulate start button press
    mock_io.get_input.side_effect = lambda name: name == 'start'

    supervisor._state_idle()

    assert supervisor.state == State.PRECHECK


def test_precheck_passes_with_safety_ok(supervisor, mock_io):
    """Test PRECHECK passes when safety is OK."""
    # Set safety OK
    mock_io.get_input.return_value = True
    supervisor._check_safety()

    supervisor._transition_to(State.PRECHECK)
    supervisor._state_precheck()

    assert supervisor.state == State.START_SPINDLE


def test_precheck_fails_without_safety(supervisor, mock_io):
    """Test PRECHECK fails when safety is not OK."""
    # Set safety not OK
    mock_io.get_input.return_value = False
    supervisor._check_safety()

    supervisor._transition_to(State.PRECHECK)
    supervisor._state_precheck()

    assert supervisor.state == State.ALARM
    assert supervisor.current_alarm == "PRECHECK_SAFETY_NOT_READY"


def test_cycle_complete_increments_stats(supervisor):
    """Test that completing a cycle increments stats."""
    initial_count = supervisor.stats['cycles_complete']

    supervisor._transition_to(State.COMPLETE)
    supervisor._state_complete()

    assert supervisor.stats['cycles_complete'] == initial_count + 1
    assert supervisor.state == State.IDLE


def test_emergency_stop_sets_safe_outputs(supervisor, mock_io, mock_axis):
    """Test emergency stop sets outputs to safe state."""
    supervisor._emergency_stop()

    # Check that safe outputs were set
    mock_io.set_outputs.assert_called_once()
    safe_states = mock_io.set_outputs.call_args[0][0]

    assert safe_states['clamp'] == False
    assert safe_states['air_jet'] == False
    assert safe_states['green_solid'] == False
    assert safe_states['green_flash'] == False

    # Check motors stopped
    mock_axis.emergency_stop_all.assert_called_once()
