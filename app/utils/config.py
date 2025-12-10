"""
Configuration loader for Pleat Saw controller.
Loads and validates YAML configuration files.
"""

import os
import yaml
from typing import Any, Dict, Optional
from pathlib import Path


class Config:
    """Central configuration manager."""

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize configuration loader.

        Args:
            config_dir: Path to config directory. If None, auto-detect relative to app root.
        """
        if config_dir is None:
            # Auto-detect: assume we're in app/utils, so config is ../../config
            app_root = Path(__file__).parent.parent.parent
            config_dir = app_root / "config"

        self.config_dir = Path(config_dir)

        if not self.config_dir.exists():
            raise FileNotFoundError(f"Config directory not found: {self.config_dir}")

        # Load all config files
        self.system = self._load_yaml("system.yaml")
        self.io_map = self._load_yaml("io_map.yaml")
        self.motion = self._load_yaml("motion.yaml")

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """Load a YAML file from config directory."""
        filepath = self.config_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(f"Config file not found: {filepath}")

        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)

        if data is None:
            raise ValueError(f"Empty or invalid YAML file: {filepath}")

        return data

    def get(self, path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Examples:
            config.get("rs485.baud")  -> 9600
            config.get("motion.m1_blade.rpm_max")  -> 6000

        Args:
            path: Dot-separated path to config value
            default: Default value if path not found

        Returns:
            Configuration value or default
        """
        parts = path.split('.')

        # Determine which config dict to search
        if parts[0] in ["rs485", "nextion", "safety", "logging", "services", "dry_run", "simulate_sensors"]:
            data = self.system
        elif parts[0] in ["inputs", "outputs"]:
            data = self.io_map
        elif parts[0] in ["m1_blade", "m2_fixture", "m3_backstop", "cycle", "hmi", "limits"]:
            data = self.motion
        else:
            return default

        # Navigate through nested dicts
        try:
            for part in parts:
                data = data[part]
            return data
        except (KeyError, TypeError):
            return default

    def get_io_bit(self, name: str, io_type: str) -> Optional[int]:
        """
        Get bit index for an input or output by name.

        Args:
            name: Input/output name (e.g., "start", "clamp")
            io_type: "input" or "output"

        Returns:
            Bit index (0-15) or None if not found
        """
        if io_type == "input":
            return self.io_map.get("inputs", {}).get(name)
        elif io_type == "output":
            return self.io_map.get("outputs", {}).get(name)
        else:
            return None

    def get_modbus_id(self, device: str) -> Optional[int]:
        """
        Get Modbus device ID.

        Args:
            device: Device name ("io", "esp32a", "esp32b")

        Returns:
            Modbus slave ID or None
        """
        return self.system.get("rs485", {}).get("ids", {}).get(device)

    def save_motion_config(self):
        """Save current motion configuration back to YAML (for HMI setpoint persistence)."""
        filepath = self.config_dir / "motion.yaml"
        with open(filepath, 'w') as f:
            yaml.dump(self.motion, f, default_flow_style=False, sort_keys=False)

    def __repr__(self) -> str:
        return f"<Config dir={self.config_dir}>"


# Global singleton instance (lazy-loaded)
_config_instance: Optional[Config] = None


def get_config(config_dir: Optional[str] = None) -> Config:
    """
    Get the global configuration instance (singleton pattern).

    Args:
        config_dir: Override config directory (only used on first call)

    Returns:
        Config instance
    """
    global _config_instance

    if _config_instance is None:
        _config_instance = Config(config_dir=config_dir)

    return _config_instance
