"""
ESP32 USB Auto-Detection Service

Scans USB serial ports and identifies ESP32A vs ESP32B by querying their ID.
Handles dynamic port enumeration (ports can change on reboot).
"""

import logging
import serial
import time
import glob
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class ESP32USBDetector:
    """Auto-detect and map ESP32 modules on USB ports."""

    def __init__(self, timeout_s: float = 1.0):
        """
        Initialize detector.
        
        Args:
            timeout_s: Timeout for ID query response
        """
        self.timeout_s = timeout_s
        self.esp32a_port: Optional[str] = None
        self.esp32b_port: Optional[str] = None

    def scan_and_identify(self) -> Dict[str, Optional[str]]:
        """
        Scan all /dev/ttyUSB* ports and identify ESP32 modules.
        
        Returns:
            Dictionary with 'esp32a' and 'esp32b' port assignments
        """
        logger.info("Scanning for ESP32 modules on USB...")
        
        # Find all USB serial ports
        usb_ports = sorted(glob.glob('/dev/ttyUSB*'))
        
        if not usb_ports:
            logger.warning("No /dev/ttyUSB* devices found")
            return {'esp32a': None, 'esp32b': None}
        
        logger.info(f"Found USB ports: {usb_ports}")
        
        # Reset detection
        self.esp32a_port = None
        self.esp32b_port = None
        
        # Query each port
        for port in usb_ports:
            module_id = self._query_module_id(port)
            
            if module_id == 'ESP32A':
                self.esp32a_port = port
                logger.info(f"✓ ESP32A detected on {port}")
            elif module_id == 'ESP32B':
                self.esp32b_port = port
                logger.info(f"✓ ESP32B detected on {port}")
            else:
                logger.debug(f"Unknown device on {port} (ID: {module_id})")
        
        # Log results
        if self.esp32a_port:
            logger.info(f"ESP32A mapped to: {self.esp32a_port}")
        else:
            logger.warning("ESP32A not detected")
            
        if self.esp32b_port:
            logger.info(f"ESP32B mapped to: {self.esp32b_port}")
        else:
            logger.warning("ESP32B not detected")
        
        return {
            'esp32a': self.esp32a_port,
            'esp32b': self.esp32b_port
        }

    def _query_module_id(self, port: str) -> Optional[str]:
        """
        Query a single port for its module ID.
        
        Args:
            port: Serial port path (e.g., /dev/ttyUSB0)
            
        Returns:
            Module ID string ('ESP32A', 'ESP32B') or None
        """
        try:
            # Open serial port
            ser = serial.Serial(
                port=port,
                baudrate=115200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout_s
            )
            
            # Give device time to initialize (if just opened)
            time.sleep(0.1)
            
            # Flush any existing data
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            
            # Send ID query
            ser.write(b'I\n')
            ser.flush()
            
            # Read response with timeout
            start_time = time.time()
            response_lines = []
            
            while time.time() - start_time < self.timeout_s:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        response_lines.append(line)
                        logger.debug(f"{port}: RX '{line}'")
                        
                        # Look for ID response
                        if line.startswith('ID:'):
                            module_id = line.split(':', 1)[1].strip()
                            ser.close()
                            return module_id
                else:
                    time.sleep(0.05)
            
            ser.close()
            logger.debug(f"{port}: No ID response (got: {response_lines})")
            return None
            
        except serial.SerialException as e:
            logger.debug(f"{port}: Serial error: {e}")
            return None
        except Exception as e:
            logger.warning(f"{port}: Unexpected error during ID query: {e}")
            return None

    def get_esp32a_port(self) -> Optional[str]:
        """Get detected ESP32A port."""
        return self.esp32a_port

    def get_esp32b_port(self) -> Optional[str]:
        """Get detected ESP32B port."""
        return self.esp32b_port


# ========== Standalone Test ==========

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    
    detector = ESP32USBDetector()
    result = detector.scan_and_identify()
    
    print("\n========== Detection Results ==========")
    print(f"ESP32A: {result['esp32a'] or 'NOT FOUND'}")
    print(f"ESP32B: {result['esp32b'] or 'NOT FOUND'}")
    print("=======================================")
