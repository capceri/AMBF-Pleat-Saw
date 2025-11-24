"""
I/O poller service for N4D3E16 module.
Polls inputs at high frequency and provides output control.
"""

import logging
import time
import threading
from typing import Optional, Dict, Callable
from services.modbus_master import ModbusMaster
from utils.bits import bits_to_dict, dict_to_bits, get_changed_bits


logger = logging.getLogger(__name__)


class IOPoller:
    """
    High-speed I/O polling service for N4D3E16 module.
    Reads inputs at configurable rate and manages outputs.
    """

    # N4D3E16 Modbus register addresses
    ADDR_INPUT_PACKED = 0x00C0      # All inputs bit-packed (IN1..IN16)
    ADDR_OUTPUT_PACKED = 0x0070     # All outputs bit-packed (CH1..CH16)
    ADDR_INPUT_BASE = 0x0081        # Per-input registers (0x0081..0x0090)
    ADDR_OUTPUT_BASE = 0x0001       # Per-output registers (0x0001..0x0010)

    def __init__(
        self,
        modbus: ModbusMaster,
        slave_id: int,
        input_map: Dict[str, int],
        output_map: Dict[str, int],
        poll_rate_hz: float = 100.0
    ):
        """
        Initialize I/O poller.

        Args:
            modbus: ModbusMaster instance
            slave_id: N4D3E16 slave ID (typically 1)
            input_map: Dictionary mapping input names to bit indices
            output_map: Dictionary mapping output names to bit indices
            poll_rate_hz: Input polling frequency in Hz
        """
        self.modbus = modbus
        self.slave_id = slave_id
        self.input_map = input_map
        self.output_map = output_map
        self.poll_rate_hz = poll_rate_hz
        self.poll_interval = 1.0 / poll_rate_hz

        # Current I/O states
        self.inputs: Dict[str, bool] = {name: False for name in input_map.keys()}
        self.outputs: Dict[str, bool] = {name: False for name in output_map.keys()}

        # Input overrides for fault diagnosis (diagnostic mode)
        self.input_overrides: Dict[str, Optional[bool]] = {name: None for name in input_map.keys()}

        # Previous input state for edge detection
        self._prev_input_raw = 0

        # Output shadow register (to avoid read-before-write)
        self._output_raw = 0

        # Change callbacks
        self._input_callbacks: Dict[str, list] = {name: [] for name in input_map.keys()}

        # Threading
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Statistics
        self.stats = {
            'poll_count': 0,
            'input_changes': 0,
            'output_writes': 0,
            'errors': 0,
        }

    def start(self):
        """Start the I/O polling thread."""
        if self._running:
            logger.warning("IOPoller already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info(f"IOPoller started: {self.poll_rate_hz} Hz")

    def stop(self):
        """Stop the I/O polling thread."""
        if not self._running:
            return

        self._running = False

        if self._thread:
            self._thread.join(timeout=2.0)

        logger.info("IOPoller stopped")

    def _poll_loop(self):
        """Main polling loop (runs in separate thread)."""
        next_poll = time.monotonic()

        while self._running:
            try:
                # Poll inputs
                self._poll_inputs()

                # Sleep until next poll time (compensate for execution time)
                now = time.monotonic()
                sleep_time = next_poll - now

                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    # We're running behind schedule
                    logger.debug(f"IOPoller loop overrun: {-sleep_time:.3f}s")

                next_poll += self.poll_interval

            except Exception as e:
                logger.error(f"IOPoller loop error: {e}")
                self.stats['errors'] += 1
                time.sleep(0.01)  # Brief delay to avoid tight error loop

    def _poll_inputs(self):
        """Poll all inputs from N4D3E16."""
        # Read bit-packed input register
        result = self.modbus.read_holding_registers(
            self.slave_id,
            self.ADDR_INPUT_PACKED,
            count=1
        )

        if result is None or len(result) == 0:
            self.stats['errors'] += 1
            return

        input_raw = result[0]
        self.stats['poll_count'] += 1

        # Convert to named dictionary
        with self._lock:
            raw_inputs = bits_to_dict(input_raw, self.input_map)

            # Apply input overrides for diagnostic purposes
            self.inputs = {}
            for name, raw_value in raw_inputs.items():
                if self.input_overrides[name] is not None:
                    # Use override value
                    self.inputs[name] = self.input_overrides[name]
                else:
                    # Use actual hardware value
                    self.inputs[name] = raw_value

            # Detect changes and trigger callbacks (based on final processed inputs)
            current_processed_raw = dict_to_bits(self.inputs, self.input_map)
            if current_processed_raw != self._prev_input_raw:
                changed = get_changed_bits(self._prev_input_raw, current_processed_raw)

                for bit_index, new_state in changed.items():
                    # Find input name for this bit
                    for name, index in self.input_map.items():
                        if index == bit_index:
                            self.stats['input_changes'] += 1
                            self._trigger_callbacks(name, new_state)
                            break

                self._prev_input_raw = current_processed_raw

    def get_input(self, name: str) -> Optional[bool]:
        """
        Get current state of a named input.

        Args:
            name: Input name (e.g., "start", "sensor2")

        Returns:
            Input state (True/False), or None if name not found
        """
        with self._lock:
            return self.inputs.get(name)

    def get_all_inputs(self) -> Dict[str, bool]:
        """Get current state of all inputs."""
        with self._lock:
            return self.inputs.copy()

    def set_output(self, name: str, state: bool) -> bool:
        """
        Set state of a named output.

        Args:
            name: Output name (e.g., "clamp", "air_jet")
            state: Desired state (True=ON, False=OFF)

        Returns:
            True if write successful
        """
        if name not in self.output_map:
            logger.error(f"Unknown output: {name}")
            return False

        with self._lock:
            # Update shadow register
            bit_index = self.output_map[name]
            if state:
                self._output_raw |= (1 << bit_index)
            else:
                self._output_raw &= ~(1 << bit_index)

            # Write to device
            success = self.modbus.write_register(
                self.slave_id,
                self.ADDR_OUTPUT_PACKED,
                self._output_raw
            )

            if success:
                self.outputs[name] = state
                self.stats['output_writes'] += 1
            else:
                self.stats['errors'] += 1

            return success

    def set_outputs(self, states: Dict[str, bool]) -> bool:
        """
        Set multiple outputs at once (more efficient than individual writes).

        Args:
            states: Dictionary mapping output names to desired states

        Returns:
            True if write successful
        """
        with self._lock:
            # Update shadow register for all requested outputs
            for name, state in states.items():
                if name not in self.output_map:
                    logger.warning(f"Unknown output in batch: {name}")
                    continue

                bit_index = self.output_map[name]
                if state:
                    self._output_raw |= (1 << bit_index)
                else:
                    self._output_raw &= ~(1 << bit_index)

            # Single write
            success = self.modbus.write_register(
                self.slave_id,
                self.ADDR_OUTPUT_PACKED,
                self._output_raw
            )

            if success:
                for name, state in states.items():
                    if name in self.output_map:
                        self.outputs[name] = state
                self.stats['output_writes'] += 1
            else:
                self.stats['errors'] += 1

            return success

    def get_output(self, name: str) -> Optional[bool]:
        """Get current commanded state of an output."""
        with self._lock:
            return self.outputs.get(name)

    def get_all_outputs(self) -> Dict[str, bool]:
        """Get current commanded state of all outputs."""
        with self._lock:
            return self.outputs.copy()

    def set_all_outputs_safe(self, safe_states: Dict[str, bool]) -> bool:
        """
        Set all outputs to safe states (used during emergency stop).

        Args:
            safe_states: Dictionary of safe output states

        Returns:
            True if write successful
        """
        logger.info(f"Setting outputs to safe state: {safe_states}")
        return self.set_outputs(safe_states)

    def register_input_callback(self, name: str, callback: Callable[[bool], None]):
        """
        Register a callback for input state changes.

        Args:
            name: Input name to monitor
            callback: Function to call on change, receives new state as argument
        """
        if name not in self.input_map:
            logger.error(f"Cannot register callback for unknown input: {name}")
            return

        with self._lock:
            self._input_callbacks[name].append(callback)

    def _trigger_callbacks(self, name: str, new_state: bool):
        """Trigger all callbacks for an input change."""
        callbacks = self._input_callbacks.get(name, [])

        for callback in callbacks:
            try:
                callback(new_state)
            except Exception as e:
                logger.error(f"Error in input callback for {name}: {e}")

    def set_input_override(self, name: str, state: Optional[bool]) -> bool:
        """
        Set input override for diagnostic purposes.

        Args:
            name: Input name to override
            state: Override state (True/False) or None to disable override

        Returns:
            True if override was set successfully
        """
        if name not in self.input_map:
            logger.error(f"Cannot override unknown input: {name}")
            return False

        with self._lock:
            self.input_overrides[name] = state

        if state is None:
            logger.info(f"Input override disabled for {name}")
        else:
            logger.info(f"Input override set for {name}: {state}")

        return True

    def clear_all_input_overrides(self):
        """Clear all input overrides and return to hardware values."""
        with self._lock:
            self.input_overrides = {name: None for name in self.input_map.keys()}
        logger.info("All input overrides cleared")

    def get_input_overrides(self) -> Dict[str, Optional[bool]]:
        """Get current input override states."""
        with self._lock:
            return self.input_overrides.copy()

    def get_input_with_override_info(self, name: str) -> Dict[str, any]:
        """
        Get input state with override information.

        Returns:
            Dict with 'value', 'overridden', and 'override_value' keys
        """
        with self._lock:
            override = self.input_overrides.get(name)
            return {
                'value': self.inputs.get(name, False),
                'overridden': override is not None,
                'override_value': override
            }

    def get_statistics(self) -> dict:
        """Get I/O statistics."""
        return self.stats.copy()

    def reset_statistics(self):
        """Reset I/O statistics."""
        self.stats = {
            'poll_count': 0,
            'input_changes': 0,
            'output_writes': 0,
            'errors': 0,
        }

    def __repr__(self) -> str:
        status = "running" if self._running else "stopped"
        return f"<IOPoller slave={self.slave_id}, rate={self.poll_rate_hz}Hz, {status}>"
