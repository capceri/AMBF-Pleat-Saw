"""
Modbus RTU master service for Pleat Saw controller.
Manages communication with N4D3E16 I/O module and ESP32 slaves over RS-485.
"""

import logging
import os
import time
from typing import Optional, List, Tuple
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException


logger = logging.getLogger(__name__)


class ModbusMaster:
    """
    Modbus RTU master for RS-485 communication.
    Handles all read/write operations with retry logic and error handling.
    """

    def __init__(self, port: str, baud: int = 9600, timeout: float = 0.5, retry_count: int = 3, port_candidates: Optional[List[str]] = None):
        """
        Initialize Modbus master.

        Args:
            port: Primary serial port path (e.g., /dev/ttyUSB0)
            baud: Baud rate (default 9600)
            timeout: Transaction timeout in seconds
            retry_count: Number of retries on communication error
            port_candidates: List of device paths to try (auto-detection)
        """
        self.port = port
        self.port_candidates = port_candidates or [port]
        self.detected_port = None
        self.baud = baud
        self.timeout = timeout
        self.retry_count = retry_count

        self.client: Optional[ModbusSerialClient] = None
        self.is_connected = False

        # Inter-transaction delay to prevent RS485 bus collisions
        self._last_transaction_time = 0.0
        self._inter_transaction_delay = 0.008  # 8ms delay between transactions (for 19200 baud)

        # Statistics
        self.stats = {
            'reads': 0,
            'writes': 0,
            'errors': 0,
            'retries': 0,
            'connection_attempts': 0,
        }

    def _port_exists(self, port: str) -> bool:
        """Check if a serial port device exists."""
        return os.path.exists(port)

    def _enforce_inter_transaction_delay(self):
        """Enforce minimum delay between Modbus transactions to prevent bus collisions."""
        now = time.time()
        elapsed = now - self._last_transaction_time
        if elapsed < self._inter_transaction_delay:
            time.sleep(self._inter_transaction_delay - elapsed)
        self._last_transaction_time = time.time()

    def connect(self) -> bool:
        """
        Establish connection to RS-485 bus.
        Tries multiple device paths if candidates are provided.

        Returns:
            True if connected successfully
        """
        self.stats['connection_attempts'] += 1

        # Try each port candidate
        for port in self.port_candidates:
            if not self._port_exists(port):
                logger.debug(f"Device {port} does not exist, skipping")
                continue

            logger.info(f"Attempting Modbus connection to {port}")

            try:
                self.client = ModbusSerialClient(
                    port=port,
                    baudrate=self.baud,
                    bytesize=8,
                    parity='N',
                    stopbits=1,
                    timeout=self.timeout,
                )

                if self.client.connect():
                    self.is_connected = True
                    self.detected_port = port
                    logger.info(f"Modbus connected: {port} @ {self.baud} baud")
                    return True
                else:
                    logger.debug(f"Connection failed to {port}")
                    if self.client:
                        self.client.close()

            except Exception as e:
                logger.debug(f"Modbus connection error on {port}: {e}")
                if self.client:
                    try:
                        self.client.close()
                    except:
                        pass
                continue

        # No devices worked
        logger.error(f"Failed to connect to Modbus on any device: {self.port_candidates}")
        self.is_connected = False
        return False

    def disconnect(self):
        """Close Modbus connection."""
        if self.client:
            self.client.close()
            self.is_connected = False
            logger.info("Modbus disconnected")

    def read_holding_registers(self, slave_id: int, address: int, count: int = 1) -> Optional[List[int]]:
        """
        Read holding registers (function code 03).

        Args:
            slave_id: Modbus slave ID (1-247)
            address: Starting register address
            count: Number of registers to read

        Returns:
            List of register values, or None on error
        """
        if not self.is_connected:
            logger.error("Modbus not connected")
            return None

        # Enforce inter-transaction delay to prevent bus collisions
        self._enforce_inter_transaction_delay()

        for attempt in range(self.retry_count + 1):
            try:
                response = self.client.read_holding_registers(
                    address=address,
                    count=count,
                    slave=slave_id
                )

                if response.isError():
                    logger.warning(f"Modbus read error (slave {slave_id}, addr 0x{address:04X}): {response}")
                    if attempt < self.retry_count:
                        self.stats['retries'] += 1
                        time.sleep(0.01)  # Brief delay before retry
                        continue
                    else:
                        self.stats['errors'] += 1
                        return None

                self.stats['reads'] += 1
                return response.registers

            except ModbusException as e:
                logger.warning(f"Modbus exception (slave {slave_id}, addr 0x{address:04X}): {e}")
                if attempt < self.retry_count:
                    self.stats['retries'] += 1
                    time.sleep(0.01)
                    continue
                else:
                    self.stats['errors'] += 1
                    return None

            except Exception as e:
                logger.error(f"Unexpected error reading Modbus (slave {slave_id}, addr 0x{address:04X}): {e}")
                self.stats['errors'] += 1
                return None

        return None

    def write_register(self, slave_id: int, address: int, value: int) -> bool:
        """
        Write single holding register (function code 06).

        Args:
            slave_id: Modbus slave ID (1-247)
            address: Register address
            value: 16-bit unsigned value (0-65535)

        Returns:
            True if write successful
        """
        if not self.is_connected:
            logger.error("Modbus not connected")
            return False

        # Enforce inter-transaction delay to prevent bus collisions
        self._enforce_inter_transaction_delay()

        for attempt in range(self.retry_count + 1):
            try:
                response = self.client.write_register(
                    address=address,
                    value=value,
                    slave=slave_id
                )

                if response.isError():
                    logger.warning(f"Modbus write error (slave {slave_id}, addr 0x{address:04X}): {response}")
                    if attempt < self.retry_count:
                        self.stats['retries'] += 1
                        time.sleep(0.01)
                        continue
                    else:
                        self.stats['errors'] += 1
                        return False

                self.stats['writes'] += 1
                return True

            except ModbusException as e:
                logger.warning(f"Modbus exception (slave {slave_id}, addr 0x{address:04X}): {e}")
                if attempt < self.retry_count:
                    self.stats['retries'] += 1
                    time.sleep(0.01)
                    continue
                else:
                    self.stats['errors'] += 1
                    return False

            except Exception as e:
                logger.error(f"Unexpected error writing Modbus (slave {slave_id}, addr 0x{address:04X}): {e}")
                self.stats['errors'] += 1
                return False

        return False

    def write_registers(self, slave_id: int, address: int, values: List[int]) -> bool:
        """
        Write multiple holding registers (function code 16).

        Args:
            slave_id: Modbus slave ID (1-247)
            address: Starting register address
            values: List of 16-bit unsigned values

        Returns:
            True if write successful
        """
        if not self.is_connected:
            logger.error("Modbus not connected")
            return False

        # Enforce inter-transaction delay to prevent bus collisions
        self._enforce_inter_transaction_delay()

        for attempt in range(self.retry_count + 1):
            try:
                response = self.client.write_registers(
                    address=address,
                    values=values,
                    slave=slave_id
                )

                if response.isError():
                    logger.warning(f"Modbus write error (slave {slave_id}, addr 0x{address:04X}): {response}")
                    if attempt < self.retry_count:
                        self.stats['retries'] += 1
                        time.sleep(0.01)
                        continue
                    else:
                        self.stats['errors'] += 1
                        return False

                self.stats['writes'] += 1
                return True

            except ModbusException as e:
                logger.warning(f"Modbus exception (slave {slave_id}, addr 0x{address:04X}): {e}")
                if attempt < self.retry_count:
                    self.stats['retries'] += 1
                    time.sleep(0.01)
                    continue
                else:
                    self.stats['errors'] += 1
                    return False

            except Exception as e:
                logger.error(f"Unexpected error writing Modbus (slave {slave_id}, addr 0x{address:04X}): {e}")
                self.stats['errors'] += 1
                return False

        return False

    def write_int32(self, slave_id: int, address: int, value: int) -> bool:
        """
        Write a 32-bit signed integer as two consecutive registers (low, high).

        Args:
            slave_id: Modbus slave ID
            address: Starting register address (low word at address, high at address+1)
            value: 32-bit signed integer

        Returns:
            True if write successful
        """
        # Split into low and high words
        if value < 0:
            value = (1 << 32) + value  # Convert to unsigned

        low = value & 0xFFFF
        high = (value >> 16) & 0xFFFF

        return self.write_registers(slave_id, address, [low, high])

    def read_int32(self, slave_id: int, address: int) -> Optional[int]:
        """
        Read a 32-bit signed integer from two consecutive registers (low, high).

        Args:
            slave_id: Modbus slave ID
            address: Starting register address (low word at address, high at address+1)

        Returns:
            32-bit signed integer, or None on error
        """
        regs = self.read_holding_registers(slave_id, address, count=2)

        if regs is None or len(regs) != 2:
            return None

        low, high = regs
        value = (high << 16) | low

        # Convert to signed
        if value & 0x80000000:
            value = value - (1 << 32)

        return value

    def get_statistics(self) -> dict:
        """Get communication statistics."""
        return self.stats.copy()

    def reset_statistics(self):
        """Reset communication statistics."""
        self.stats = {
            'reads': 0,
            'writes': 0,
            'errors': 0,
            'retries': 0,
        }

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        return f"<ModbusMaster {self.port} @ {self.baud} baud, {status}>"
