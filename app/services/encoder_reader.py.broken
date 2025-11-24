"""
AS5600 Magnetic Encoder Reader via I2C

Reads AS5600 encoder on Raspberry Pi I2C bus for M3 backstop position tracking.
Implements multi-turn tracking with 12-bit resolution (4096 counts per revolution).
"""

import logging
import threading
import time
from typing import Optional
from smbus2 import SMBus

logger = logging.getLogger(__name__)


class AS5600EncoderReader:
    """AS5600 12-bit magnetic rotary position sensor reader via I2C."""
    
    # AS5600 I2C address and registers
    AS5600_ADDR = 0x36
    RAW_ANGLE_REG = 0x0C  # 12-bit raw angle (0-4095)
    
    # Encoder parameters (from ESP32B firmware)
    COUNTS_PER_REV = 4096  # 12-bit resolution
    MM_PER_REV = 5.0       # Lead screw: 5mm per revolution
    MM_PER_COUNT = MM_PER_REV / COUNTS_PER_REV  # ~0.00122 mm/count
    
    def __init__(self, i2c_bus: int = 1, read_interval_ms: int = 100):
        """
        Initialize AS5600 encoder reader.
        
        Args:
            i2c_bus: I2C bus number (default 1 for /dev/i2c-1)
            read_interval_ms: Encoder read interval in milliseconds
        """
        self.i2c_bus_num = i2c_bus
        self.read_interval_s = read_interval_ms / 1000.0
        
        # Multi-turn tracking state
        self.encoder_detected = False
        self.prev_raw_angle = 0
        self.accum_counts = 0
        self.position_mm = 0.0
        self.first_read = True
        
        # Threading
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        
        # I2C bus
        self.bus = None
        
    def start(self):
        """Start encoder reading thread."""
        logger.info(f"Starting AS5600 encoder reader on I2C bus {self.i2c_bus_num}...")
        
        try:
            # Open I2C bus
            self.bus = SMBus(self.i2c_bus_num)
            
            # Test if AS5600 is responding
            if self._detect_encoder():
                self.encoder_detected = True
                logger.info(f"✓ AS5600 detected at 0x{self.AS5600_ADDR:02X}, initial angle: {self.prev_raw_angle}")
            else:
                logger.warning(f"✗ AS5600 NOT detected on I2C bus {self.i2c_bus_num}")
                logger.warning("  Encoder reading disabled - check wiring:")
                logger.warning(f"  - AS5600 VCC → Pi 3.3V")
                logger.warning(f"  - AS5600 GND → Pi GND")
                logger.warning(f"  - AS5600 SDA → Pi GPIO2 (Pin 3)")
                logger.warning(f"  - AS5600 SCL → Pi GPIO3 (Pin 5)")
                return
            
            # Start reading thread
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._read_loop, daemon=True, name="AS5600Reader")
            self._thread.start()
            
            logger.info(f"AS5600 encoder reader started (interval={int(self.read_interval_s*1000)}ms)")
            
        except Exception as e:
            logger.error(f"Failed to start AS5600 encoder reader: {e}")
            self.encoder_detected = False
            
    def stop(self):
        """Stop encoder reading thread."""
        logger.info("Stopping AS5600 encoder reader...")
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            
        if self.bus:
            self.bus.close()
            
        logger.info("AS5600 encoder reader stopped")
        
    def _detect_encoder(self) -> bool:
        """
        Detect if AS5600 is responding on I2C bus.
        
        Returns:
            True if AS5600 detected, False otherwise
        """
        try:
            # Try to read raw angle register
            raw_angle = self._read_raw_angle()
            
            if raw_angle is not None and 0 <= raw_angle <= 4095:
                self.prev_raw_angle = raw_angle
                self.first_read = True
                return True
            else:
                return False
                
        except Exception as e:
            logger.warning(f"AS5600 detection failed: {e}")
            return False
            
    def _read_raw_angle(self) -> Optional[int]:
        """
        Read 12-bit raw angle from AS5600 (0-4095).
        
        Returns:
            Raw angle value or None on error
        """
        try:
            # Read 2 bytes from RAW_ANGLE register
            msb = self.bus.read_byte_data(self.AS5600_ADDR, self.RAW_ANGLE_REG)
            lsb = self.bus.read_byte_data(self.AS5600_ADDR, self.RAW_ANGLE_REG + 1)
            
            # Combine MSB and LSB, mask to 12 bits
            raw = ((msb << 8) | lsb) & 0x0FFF
            return raw
            
        except Exception as e:
            logger.warning(f"Failed to read AS5600 angle: {e}")
            return None
            
    def _update_position(self):
        """Update multi-turn position from encoder reading."""
        raw = self._read_raw_angle()
        
        if raw is None:
            return  # Read failed, keep previous position
            
        with self._lock:
            if self.first_read:
                # First reading - initialize without accumulation
                self.first_read = False
                self.prev_raw_angle = raw
                return
                
            # Calculate delta with wrap-around handling
            delta = raw - self.prev_raw_angle
            
            # Handle wrap-around (crossing 0/4095 boundary)
            if delta > 2048:
                delta -= 4096  # Wrapped backward (4095 → 0)
            elif delta < -2048:
                delta += 4096  # Wrapped forward (0 → 4095)
                
            # Accumulate counts (multi-turn tracking)
            self.accum_counts += delta
            self.prev_raw_angle = raw
            
            # Convert to mm
            self.position_mm = float(self.accum_counts) * self.MM_PER_COUNT
            # DEBUG: Log position updates            if abs(delta) > 0:                import logging                logging.getLogger(__name__).info(f"Position update: delta={delta}, accum={self.accum_counts}, pos={self.position_mm:.4f}mm")
            
    def _read_loop(self):
        """Background thread for continuous encoder reading."""
        logger.info("AS5600 encoder reading loop started")
        
        while not self._stop_event.is_set():
            try:
                self._update_position()
                time.sleep(self.read_interval_s)
                
            except Exception as e:
                logger.error(f"Error in AS5600 read loop: {e}")
                time.sleep(1.0)  # Back off on error
                
        logger.info("AS5600 encoder reading loop stopped")
        
    def get_position_mm(self) -> float:
        """
        Get current encoder position in millimeters.
        
        Returns:
            Position in mm (multi-turn accumulated)
        """
        with self._lock:
            return self.position_mm
            
    def home(self):
        """Reset accumulated position to zero (homing)."""
        with self._lock:
            self.accum_counts = 0
            self.position_mm = 0.0
            logger.info("AS5600 encoder homed (position reset to 0.0 mm)")
            
    def is_detected(self) -> bool:
        """Check if encoder was detected at startup."""
        return self.encoder_detected
