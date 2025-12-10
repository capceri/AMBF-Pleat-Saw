#!/usr/bin/env python3
"""
Pleat Saw Controller - Main Application
Raspberry Pi master controller for pleat saw machine.
"""

import signal
import sys
import time
import argparse
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from utils import get_config
from services import (
    setup_logging,
    EventLogger,
    ModbusMaster,
    IOPoller,
    AxisGateway,
    NextionBridge,
    Supervisor,
    WebMonitor
)


class PleatSawController:
    """Main application controller."""

    def __init__(self, config_dir: str = None, dry_run: bool = False):
        """
        Initialize Pleat Saw controller.

        Args:
            config_dir: Path to configuration directory
            dry_run: Enable dry-run mode (mocked Modbus)
        """
        self.config = get_config(config_dir)
        self.dry_run = dry_run or self.config.get('dry_run', False)

        # Services - Dual RS485 Channels
        self.modbus_io: ModbusMaster = None      # Channel 0: I/O module (9600 baud)
        self.modbus_motors: ModbusMaster = None  # Channel 1: ESP32s (115200 baud)
        self.io: IOPoller = None
        self.axis: AxisGateway = None
        self.hmi: NextionBridge = None
        self.supervisor: Supervisor = None
        self.web_monitor: WebMonitor = None
        self.event_logger: EventLogger = None

        # Shutdown flag
        self._shutdown_requested = False

        # Initialization errors (for diagnostics)
        self.init_errors = []

    def setup_logging(self):
        """Configure application logging."""
        log_config = self.config.system.get('logging', {})

        setup_logging(
            level=log_config.get('level', 'INFO'),
            log_dir=log_config.get('log_dir'),
            max_bytes=log_config.get('max_bytes', 10485760),
            backup_count=log_config.get('backup_count', 5),
            console_output=log_config.get('console_output', True),
        )

        # Event logger
        log_dir = log_config.get('log_dir')
        if log_dir:
            self.event_logger = EventLogger(log_dir)

    def initialize_services(self) -> bool:
        """
        Initialize all services.

        Returns:
            True if all services initialized successfully
        """
        import logging
        logger = logging.getLogger(__name__)

        # Track initialization errors for diagnostics
        init_errors = []

        try:
            # Modbus Channel 0: I/O Module (9600 baud)
            logger.info("Initializing Modbus I/O channel (9600 baud)...")
            rs485_io_config = self.config.system['rs485_io']

            self.modbus_io = ModbusMaster(
                port=rs485_io_config['port'],
                baud=rs485_io_config['baud'],
                timeout=rs485_io_config.get('timeout_s', 0.5),
                retry_count=rs485_io_config.get('retry_count', 3),
                port_candidates=[rs485_io_config['port']],
            )

            if not self.dry_run:
                if not self.modbus_io.connect():
                    error_msg = f"Failed to connect Modbus I/O on {rs485_io_config['port']}"
                    logger.error(error_msg)
                    init_errors.append(error_msg)
                else:
                    logger.info(f"Modbus I/O connected: {self.modbus_io.detected_port} @ {rs485_io_config['baud']} baud")
            else:
                logger.warning("DRY RUN MODE: Modbus I/O mocked")

            # Modbus Channel 1: Motor Controllers (115200 baud)
            logger.info("Initializing Modbus Motors channel (115200 baud)...")
            rs485_motors_config = self.config.system['rs485_motors']

            self.modbus_motors = ModbusMaster(
                port=rs485_motors_config['port'],
                baud=rs485_motors_config['baud'],
                timeout=rs485_motors_config.get('timeout_s', 0.5),
                retry_count=rs485_motors_config.get('retry_count', 3),
                port_candidates=[rs485_motors_config['port']],
            )

            if not self.dry_run:
                if not self.modbus_motors.connect():
                    error_msg = f"Failed to connect Modbus Motors on {rs485_motors_config['port']}"
                    logger.error(error_msg)
                    init_errors.append(error_msg)
                else:
                    logger.info(f"Modbus Motors connected: {self.modbus_motors.detected_port} @ {rs485_motors_config['baud']} baud")
            else:
                logger.warning("DRY RUN MODE: Modbus Motors mocked")

            # I/O poller (uses Channel 0: I/O Modbus at 9600 baud)
            logger.info("Initializing I/O poller...")
            io_config = self.config.system['services']['io_poller']

            self.io = IOPoller(
                modbus=self.modbus_io,
                slave_id=self.config.system['rs485_io']['ids']['io'],
                input_map=self.config.io_map['inputs'],
                output_map=self.config.io_map['outputs'],
                poll_rate_hz=io_config.get('poll_rate_hz', 100.0),
            )

            # Axis gateway (uses Channel 1: Motors Modbus at 115200 baud)
            logger.info("Initializing axis gateway...")
            axis_config = self.config.system['services']['axis_gateway']

            self.axis = AxisGateway(
                modbus=self.modbus_motors,
                esp32a_id=self.config.system['rs485_motors']['ids']['esp32a'],
                esp32b_id=self.config.system['rs485_motors']['ids']['esp32b'],
                heartbeat_check_s=axis_config.get("heartbeat_check_s", 2.0),
                m3_usb_port="/dev/ttyUSB0",
                io_poller=self.io,
            )

            # Nextion HMI bridge
            nextion_config = self.config.system["nextion"]
            hmi_config = self.config.system["services"]["nextion_bridge"]

            self.hmi = NextionBridge(
                port=nextion_config["port"],
                baud=nextion_config["baud"],
                timeout=nextion_config.get("timeout_s", 0.1),
                update_rate_hz=hmi_config.get("update_rate_hz", 10.0),
                debounce_ms=nextion_config.get("debounce_ms", 100),
            )

            if not self.dry_run:
                if not self.hmi.connect():
                    error_msg = f"Failed to connect Nextion on {nextion_config['port']}"
                    logger.warning(error_msg)
                    init_errors.append(error_msg)
            logger.info("Nextion HMI disabled - not part of project")
            self.hmi = None
            # nextion_config = self.config.system['nextion']
            # hmi_config = self.config.system['services']['nextion_bridge']
            #
            # self.hmi = NextionBridge(
            #     port=nextion_config['port'],
            #     baud=nextion_config['baud'],
            #     timeout=nextion_config.get('timeout_s', 0.1),
            #     update_rate_hz=hmi_config.get('update_rate_hz', 10.0),
            #     debounce_ms=nextion_config.get('debounce_ms', 100),
            # )
            #
            # if not self.dry_run:
            #     if not self.hmi.connect():
            #         error_msg = f"Failed to connect Nextion on {nextion_config['port']}"
            #         logger.warning(error_msg)
            #         init_errors.append(error_msg)
            #         # Continue anyway - web monitor can show the error
            # else:
            #     logger.warning("DRY RUN MODE: Nextion mocked")

            # Supervisor state machine
            logger.info("Initializing supervisor...")
            supervisor_config = self.config.system['services']['supervisor']

            self.supervisor = Supervisor(
                io=self.io,
                axis=self.axis,
                hmi=self.hmi,
                config={
                    'motion': self.config.motion,
                    'system': self.config.system,
                },
                loop_rate_hz=supervisor_config.get('loop_rate_hz', 50.0),
            )

            # Register HMI command callback - DISABLED (Nextion not used)
            # if self.hmi:
            #     self.hmi.register_callback('cmd', self.supervisor.handle_hmi_command)
            #
            #     # Register HMI setpoint callbacks (ESP32-compatible)
            #     def make_setpoint_handler(key):
            #         return lambda value: self.supervisor.handle_hmi_setpoint(key, value)
            #
            #     self.hmi.register_callback('m1.rpm', make_setpoint_handler('m1.rpm'))
            #     self.hmi.register_callback('m2.vel_fwd', make_setpoint_handler('m2.vel_fwd'))
            #     self.hmi.register_callback('m2.vel_rev', make_setpoint_handler('m2.vel_rev'))
            #     self.hmi.register_callback('m3.goto_in', make_setpoint_handler('m3.goto_in'))
            #     self.hmi.register_callback('m3.goto_mm', make_setpoint_handler('m3.goto_mm'))

            # Web monitoring dashboard
            web_config = self.config.system['services'].get('web_monitor', {})
            if web_config.get('enabled', True):
                logger.info("Initializing web monitor...")
                self.web_monitor = WebMonitor(
                    io_poller=self.io,
                    axis_gateway=self.axis,
                    supervisor=self.supervisor,
                    nextion_bridge=self.hmi,
                    modbus_master=self.modbus_motors,  # Use motors channel for web commands
                    config=self.config,
                    port=web_config.get('port', 5000),
                    host=web_config.get('host', '0.0.0.0'),
                    update_rate_hz=web_config.get('update_rate_hz', 10.0),
                )
                # Pass initialization errors to web monitor for diagnostics
                self.web_monitor.set_init_errors(init_errors)

            # Store initialization errors for web monitor to display
            self.init_errors = init_errors

            if init_errors:
                logger.warning(f"Services initialized with {len(init_errors)} error(s):")
                for error in init_errors:
                    logger.warning(f"  - {error}")
                logger.info("Web monitor will remain available for diagnostics")
            else:
                logger.info("All services initialized successfully")

            return True  # Always return True so web monitor starts

        except Exception as e:
            logger.error(f"Critical error during initialization: {e}")
            # Even on critical error, try to continue for diagnostics
            self.init_errors = init_errors + [f"Critical error: {str(e)}"]
            logger.warning("Attempting to start web monitor for diagnostics...")
            return True  # Try to start web monitor anyway

    def start_services(self):
        """Start all services."""
        import logging
        logger = logging.getLogger(__name__)

        logger.info("Starting services...")

        if self.config.system['services']['io_poller']['enabled']:
            self.io.start()

        if self.config.system['services']['axis_gateway']['enabled']:
            self.axis.start()

        # Nextion HMI disabled
        # if self.config.system['services']['nextion_bridge']['enabled']:
        #     self.hmi.start()

        if self.config.system['services']['supervisor']['enabled']:
            self.supervisor.start()

        if self.web_monitor and self.config.system['services'].get('web_monitor', {}).get('enabled', True):
            self.web_monitor.start()

        logger.info("All services started")

    def stop_services(self):
        """Stop all services."""
        import logging
        logger = logging.getLogger(__name__)

        logger.info("Stopping services...")

        if self.supervisor:
            self.supervisor.stop()

        if self.web_monitor:
            self.web_monitor.stop()

        # Nextion HMI disabled
        # if self.hmi:
        #     self.hmi.stop()
        #     self.hmi.disconnect()

        if self.axis:
            self.axis.stop()

        if self.io:
            self.io.stop()

        if self.modbus_io:
            self.modbus_io.disconnect()

        if self.modbus_motors:
            self.modbus_motors.disconnect()

        logger.info("All services stopped")

    def run(self):
        """Main run loop."""
        import logging
        logger = logging.getLogger(__name__)

        logger.info("Pleat Saw Controller starting...")

        if not self.initialize_services():
            logger.error("Initialization failed, exiting")
            return 1

        self.start_services()

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("Pleat Saw Controller running (press Ctrl+C to exit)")

        # Main loop - just keep alive, services run in their own threads
        try:
            while not self._shutdown_requested:
                time.sleep(1.0)

                # Periodic statistics logging (every 60 seconds)
                if int(time.time()) % 60 == 0:
                    self._log_statistics()

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")

        finally:
            self.stop_services()
            logger.info("Pleat Saw Controller stopped")

        return 0

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"Signal {signum} received, shutting down...")
        self._shutdown_requested = True

    def _log_statistics(self):
        """Log periodic statistics."""
        import logging
        logger = logging.getLogger(__name__)

        if self.modbus_io:
            modbus_io_stats = self.modbus_io.get_statistics()
            logger.debug(f"Modbus I/O stats: {modbus_io_stats}")

        if self.modbus_motors:
            modbus_motors_stats = self.modbus_motors.get_statistics()
            logger.debug(f"Modbus Motors stats: {modbus_motors_stats}")

        if self.io:
            io_stats = self.io.get_statistics()
            logger.debug(f"I/O stats: {io_stats}")

        if self.supervisor:
            sup_stats = self.supervisor.get_statistics()
            logger.info(f"Supervisor stats: {sup_stats}")


def main():
    """Application entry point."""
    parser = argparse.ArgumentParser(description='Pleat Saw Controller')

    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration directory',
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Enable dry-run mode (mock Modbus)',
    )

    args = parser.parse_args()

    # Create and run controller
    controller = PleatSawController(
        config_dir=args.config,
        dry_run=args.dry_run,
    )

    controller.setup_logging()

    return controller.run()


if __name__ == '__main__':
    sys.exit(main())
