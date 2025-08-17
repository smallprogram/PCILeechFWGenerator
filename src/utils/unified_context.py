# pyright: ignore[reportOptionalMemberAccess]
"""
Unified context building and template compatibility utilities.

This module provides a single, consistent approach to building template contexts
that work seamlessly with Jinja2 templates, avoiding the dict vs attribute access issues.
"""

import logging
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .validation_constants import CRITICAL_TEMPLATE_CONTEXT_KEYS, KNOWN_DEVICE_TYPES


def get_package_version() -> str:
    """
    Get the package version dynamically.

    Tries multiple methods to get the version:
    1. From __version__.py in the src directory
    2. From setuptools_scm if available
    3. Falls back to a default version

    Returns:
        str: The package version
    """
    try:
        # First try to get from __version__.py
        src_dir = Path(__file__).parent.parent
        version_file = src_dir / "__version__.py"

        if version_file.exists():
            # Read the version file
            version_dict = {}
            with open(version_file, "r") as f:
                exec(f.read(), version_dict)
            return version_dict.get("__version__", "2.0.0")

        # Fallback: try setuptools_scm
        try:
            from setuptools_scm import get_version

            return get_version(root="../..")
        except Exception as e:
            logging.debug(f"Error getting version from setuptools_scm: {e}")
            pass

        # Fallback: try importlib.metadata (Python 3.8+)
        try:
            from importlib.metadata import version

            return version("PCILeechFWGenerator")
        except ImportError:
            pass

        # Final fallback
        return "2.0.0"

    except Exception:
        # If all else fails, return default
        return "2.0.0"


class TemplateObject:
    """
    A simple object that allows both dictionary and attribute access.

    This solves the Jinja2 template compatibility issue where templates
    expect object.attribute syntax but we're passing dictionaries.
    """

    def __init__(self, data: Dict[str, Any]):
        """Initialize with dictionary data."""
        # Store the original dict for key access
        self._data = data

        # Set attributes for dot notation access
        for key, value in data.items():
            # Ensure key is a string
            if isinstance(key, str):
                clean_key = key
            elif hasattr(key, "name"):
                clean_key = key.name
            elif hasattr(key, "value"):
                clean_key = str(key.value)
            else:
                clean_key = str(key)

            # Process value
            if isinstance(value, dict):
                # Recursively convert nested dicts to TemplateObjects
                setattr(self, clean_key, TemplateObject(value))
            elif isinstance(value, list):
                # Handle lists that might contain dicts
                processed_list = []
                for item in value:
                    if isinstance(item, dict):
                        processed_list.append(TemplateObject(item))
                    else:
                        processed_list.append(item)
                setattr(self, clean_key, processed_list)
            else:
                # Convert enum values to their string representation
                if hasattr(value, "value"):
                    clean_value = value.value
                elif hasattr(value, "name"):
                    clean_value = value.name
                else:
                    clean_value = value
                setattr(self, clean_key, clean_value)

    def __getitem__(self, key):
        """Allow dictionary-style access."""
        return self._data[key]

    def __setitem__(self, key, value):
        """Allow dictionary-style assignment."""
        self._data[key] = value
        setattr(self, key, value)

    def __contains__(self, key):
        """Allow 'in' operator."""
        return key in self._data

    def get(self, key, default=None):
        """Allow dict.get() style access."""
        return self._data.get(key, default)

    def __getattr__(self, name):
        """Fallback for attribute access - check the internal dictionary."""
        if name in self._data:
            return self._data[name]
        # Provide safe defaults for commonly accessed template variables
        if name in [
            "counter_width",
            "process_variation",
            "temperature_coefficient",
            "voltage_variation",
        ]:
            return getattr(self._get_safe_defaults(), name, None)
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def _get_safe_defaults(self):
        """Return object with safe defaults for common template variables."""

        class SafeDefaults:
            counter_width = 32
            process_variation = 0.1
            temperature_coefficient = 0.05
            voltage_variation = 0.03

        return SafeDefaults()

    def keys(self):
        """Allow iteration over keys."""
        return self._data.keys()

    def values(self):
        """Allow iteration over values."""
        return self._data.values()

    def items(self):
        """Allow iteration over items."""
        return self._data.items()

    def to_dict(self) -> Dict[str, Any]:
        """Convert back to a regular dictionary, including all attributes."""
        result = self._data.copy()
        # Also include attributes that were set directly on the object
        for key in dir(self):
            if not key.startswith("_") and key not in [
                "get",
                "keys",
                "values",
                "items",
                "to_dict",
            ]:
                value = getattr(self, key)
                if not callable(value):
                    result[key] = value

        # Convert nested TemplateObjects to regular dicts to avoid namespace confusion
        for key, value in result.items():
            if isinstance(value, TemplateObject):
                # Convert nested TemplateObjects to regular dicts
                result[key] = value.to_dict()

        return result


@dataclass
class UnifiedDeviceConfig:
    """Unified device configuration that contains all fields needed by templates."""

    # Device identifiers
    vendor_id: str
    device_id: str
    subsystem_vendor_id: str
    subsystem_device_id: str
    class_code: str
    revision_id: str

    # Active device config
    enabled: bool = True
    timer_period: int = 1000
    timer_enable: bool = True
    msi_vector_width: int = 5
    msi_64bit_addr: bool = True

    # Interrupt configuration
    num_sources: int = 1
    default_priority: int = 4
    interrupt_mode: str = "intx"
    interrupt_vectors: int = 1

    # MSI-X configuration
    num_msix: int = 4
    msix_table_bir: int = 0
    msix_table_offset: int = 0x1000
    msix_pba_bir: int = 0
    msix_pba_offset: int = 0x2000

    # PCIe configuration
    completer_id: int = 0x0000

    # Device classification
    device_class: str = "generic"
    is_network: bool = False
    is_storage: bool = False
    is_display: bool = False


class UnifiedContextBuilder:
    """
    Unified context builder that creates template-compatible contexts.

    This replaces the multiple context builders with a single, consistent approach.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the unified context builder."""
        self.logger = logger or logging.getLogger(__name__)

    def create_active_device_config(
        self,
        vendor_id: str,
        device_id: str,
        subsystem_vendor_id: Optional[str] = None,
        subsystem_device_id: Optional[str] = None,
        class_code: str = "000000",
        revision_id: str = "00",
        interrupt_strategy: str = "intx",
        interrupt_vectors: int = 1,
        **kwargs,
    ) -> TemplateObject:
        """
        Create a unified active device configuration that works with all templates.

        Args:
            vendor_id: PCI vendor ID
            device_id: PCI device ID
            subsystem_vendor_id: Subsystem vendor ID (defaults to vendor_id)
            subsystem_device_id: Subsystem device ID (defaults to device_id)
            class_code: PCI class code
            revision_id: PCI revision ID
            interrupt_strategy: Interrupt strategy ("intx", "msi", "msix")
            interrupt_vectors: Number of interrupt vectors
            **kwargs: Additional configuration overrides

        Returns:
            TemplateObject with all required fields for templates
        """

        # Set defaults for subsystem IDs with proper validation
        if not subsystem_vendor_id:
            subsystem_vendor_id = vendor_id
        if not subsystem_device_id:
            subsystem_device_id = device_id

        # Validate required parameters
        if not vendor_id or not device_id:
            raise ValueError("vendor_id and device_id are required")

        # Determine device class from class code
        device_class = self._get_device_class(class_code)
        is_network = class_code.startswith("02")
        is_storage = class_code.startswith("01")
        is_display = class_code.startswith("03")

        # Create unified config
        config = UnifiedDeviceConfig(
            vendor_id=vendor_id,
            device_id=device_id,
            subsystem_vendor_id=subsystem_vendor_id,
            subsystem_device_id=subsystem_device_id,
            class_code=class_code,
            revision_id=revision_id,
            interrupt_mode=interrupt_strategy,
            interrupt_vectors=interrupt_vectors,
            device_class=device_class,
            is_network=is_network,
            is_storage=is_storage,
            is_display=is_display,
            num_sources=max(1, interrupt_vectors),
            num_msix=max(1, interrupt_vectors) if interrupt_strategy == "msix" else 4,
            **kwargs,  # Allow overrides
        )

        # Convert to TemplateObject for template compatibility
        return TemplateObject(asdict(config))

    def create_generation_metadata(
        self, device_signature: Optional[str] = None, **kwargs
    ) -> TemplateObject:
        """
        Create generation metadata for templates.

        Args:
            device_signature: Unique device signature
            **kwargs: Additional metadata

        Returns:
            TemplateObject with generation metadata
        """
        from .metadata import build_generation_metadata

        # Extract device_bdf from kwargs to avoid conflicts
        device_bdf = kwargs.pop("device_bdf", "unknown")

        # Use the centralized metadata utility
        metadata = build_generation_metadata(
            device_bdf=device_bdf, device_signature=device_signature, **kwargs
        )

        # Add timestamp and friendly names for compatibility with existing templates
        # Keep both `generated_at` (canonical) and `generated_time` for older templates.
        metadata["timestamp"] = metadata.get("generated_at")
        metadata["generated_time"] = metadata.get("generated_at")
        # Provide a pretty-printed time string if available, else fallback to str()
        try:
            generated_at = metadata.get("generated_at")
            if generated_at is not None and hasattr(generated_at, "isoformat"):
                pretty = generated_at.isoformat()
            else:
                pretty = str(generated_at if generated_at is not None else "")
        except Exception:
            pretty = str(metadata.get("generated_at", ""))
        metadata["generated_time_pretty"] = pretty

        # Add generator/version fields for older templates
        metadata["generator"] = "PCILeechFWGenerator"
        metadata["generator_version"] = metadata.get(
            "generator_version", get_package_version()
        )
        metadata["version"] = metadata["generator_version"]

        return TemplateObject(metadata)

    def create_board_config(
        self,
        board_name: str = "generic",
        fpga_part: str = "xc7a35t",
        fpga_family: str = "artix7",
        **kwargs,
    ) -> TemplateObject:
        """
        Create board configuration for templates.

        Args:
            board_name: Board name
            fpga_part: FPGA part number
            fpga_family: FPGA family
            **kwargs: Additional board configuration

        Returns:
            TemplateObject with board configuration
        """
        config = {
            "name": board_name,
            "fpga_part": fpga_part,
            "fpga_family": fpga_family,
            "pcie_ip_type": "xdma",
            "sys_clk_freq_mhz": 100,
            "max_lanes": 4,
            "supports_msi": True,
            "supports_msix": True,
            **kwargs,
        }

        return TemplateObject(config)

    def create_template_logic_flags(
        self,
        enable_clock_domain_logic: bool = False,
        enable_device_specific_ports: bool = False,
        enable_interrupt_logic: bool = True,
        enable_read_logic: bool = True,
        enable_register_logic: bool = True,
        **kwargs,
    ) -> TemplateObject:
        """
        Create template logic flags for advanced templates.

        Args:
            enable_clock_domain_logic: Enable clock domain logic
            enable_device_specific_ports: Enable device-specific ports
            enable_interrupt_logic: Enable interrupt logic
            enable_read_logic: Enable read logic
            enable_register_logic: Enable register logic
            **kwargs: Additional logic flags

        Returns:
            TemplateObject with logic flags
        """
        flags = {
            "clock_domain_logic": enable_clock_domain_logic,
            "device_specific_ports": enable_device_specific_ports,
            "interrupt_logic": enable_interrupt_logic,
            "read_logic": enable_read_logic,
            "register_logic": enable_register_logic,
            **kwargs,
        }

        return TemplateObject(flags)

    def create_performance_config(
        self,
        counter_width: int = 32,
        enable_transaction_counters: bool = False,
        enable_bandwidth_monitoring: bool = False,
        enable_latency_tracking: bool = False,
        enable_latency_measurement: bool = False,
        enable_error_counting: bool = False,
        enable_error_rate_tracking: bool = False,
        enable_performance_grading: bool = False,
        enable_perf_outputs: bool = False,
        **kwargs,
    ) -> TemplateObject:
        """
        Create performance configuration for templates.

        Args:
            counter_width: Width of performance counters
            enable_transaction_counters: Enable transaction counters
            enable_bandwidth_monitoring: Enable bandwidth monitoring
            enable_latency_tracking: Enable latency tracking
            enable_latency_measurement: Enable latency measurement
            enable_error_counting: Enable error counting
            enable_error_rate_tracking: Enable error rate tracking
            enable_performance_grading: Enable performance grading
            enable_perf_outputs: Enable performance outputs
            **kwargs: Additional performance configuration

        Returns:
            TemplateObject with performance configuration
        """
        config = {
            "counter_width": counter_width,
            "enable_transaction_counters": enable_transaction_counters,
            "enable_bandwidth_monitoring": enable_bandwidth_monitoring,
            "enable_latency_tracking": enable_latency_tracking,
            "enable_latency_measurement": enable_latency_measurement,
            "enable_error_counting": enable_error_counting,
            "enable_error_rate_tracking": enable_error_rate_tracking,
            "enable_performance_grading": enable_performance_grading,
            "enable_perf_outputs": enable_perf_outputs,
            # Signal availability flags for performance counter template
            "error_signals_available": kwargs.get("error_signals_available", False),
            "network_signals_available": kwargs.get("network_signals_available", False),
            "storage_signals_available": kwargs.get("storage_signals_available", False),
            "graphics_signals_available": kwargs.get(
                "graphics_signals_available", False
            ),
            "audio_signals_available": kwargs.get("audio_signals_available", False),
            "media_signals_available": kwargs.get("media_signals_available", False),
            "processor_signals_available": kwargs.get(
                "processor_signals_available", False
            ),
            "usb_signals_available": kwargs.get("usb_signals_available", False),
            "generic_signals_available": kwargs.get("generic_signals_available", True),
            # Performance tuning parameters
            "bandwidth_sample_period": kwargs.get("bandwidth_sample_period", 100000),
            "transfer_width": kwargs.get("transfer_width", 4),
            "bandwidth_shift": kwargs.get("bandwidth_shift", 10),
            "min_operations_for_error_rate": kwargs.get(
                "min_operations_for_error_rate", 100
            ),
            "avg_packet_size": kwargs.get("avg_packet_size", 1500),
            # Performance thresholds
            "high_performance_threshold": kwargs.get(
                "high_performance_threshold", 1000
            ),
            "medium_performance_threshold": kwargs.get(
                "medium_performance_threshold", 100
            ),
            "high_bandwidth_threshold": kwargs.get("high_bandwidth_threshold", 100),
            "medium_bandwidth_threshold": kwargs.get("medium_bandwidth_threshold", 50),
            "low_latency_threshold": kwargs.get("low_latency_threshold", 10),
            "medium_latency_threshold": kwargs.get("medium_latency_threshold", 50),
            "low_error_threshold": kwargs.get("low_error_threshold", 1),
            "medium_error_threshold": kwargs.get("medium_error_threshold", 5),
            **kwargs,
        }

        return TemplateObject(config)

    def create_power_management_config(
        self,
        enable_power_management: bool = True,
        clk_hz: int = 100_000_000,
        transition_timeout_ns: int = 10_000_000,
        enable_pme: bool = True,
        enable_wake_events: bool = False,
        transition_cycles: Optional[Dict[str, int]] = None,
        **kwargs,
    ) -> TemplateObject:
        """
        Create power management configuration for templates.

        Args:
            enable_power_management: Enable power management features
            clk_hz: Clock frequency in Hz
            transition_timeout_ns: Transition timeout in nanoseconds
            enable_pme: Enable Power Management Events
            enable_wake_events: Enable wake events
            transition_cycles: Dict with transition cycle counts
            **kwargs: Additional power management configuration

        Returns:
            TemplateObject with power management configuration
        """
        if transition_cycles is None:
            transition_cycles = {
                "d0_to_d1": 100,
                "d1_to_d0": 200,
                "d0_to_d3": 500,
                "d3_to_d0": 1000,
            }

        config = {
            "enable_power_management": enable_power_management,
            "clk_hz": clk_hz,
            "transition_timeout_ns": transition_timeout_ns,
            "enable_pme": enable_pme,
            "enable_wake_events": enable_wake_events,
            "transition_cycles": TemplateObject(transition_cycles),
            # Add flag to indicate if interface signals are available
            "has_interface_signals": kwargs.get("has_interface_signals", False),
            **kwargs,
        }

        return TemplateObject(config)

    def create_error_handling_config(
        self,
        enable_error_detection: bool = True,
        enable_error_logging: bool = True,
        enable_auto_retry: bool = True,
        max_retry_count: int = 3,
        error_recovery_cycles: int = 100,
        error_log_depth: int = 256,
        **kwargs,
    ) -> TemplateObject:
        """
        Create error handling configuration for templates.

        Args:
            enable_error_detection: Enable error detection
            enable_error_logging: Enable error logging
            enable_auto_retry: Enable automatic retry
            max_retry_count: Maximum retry count
            error_recovery_cycles: Error recovery cycles
            error_log_depth: Error log depth
            **kwargs: Additional error handling configuration

        Returns:
            TemplateObject with error handling configuration
        """
        config = {
            "enable_error_detection": enable_error_detection,
            "enable_error_logging": enable_error_logging,
            "enable_auto_retry": enable_auto_retry,
            "max_retry_count": max_retry_count,
            "error_recovery_cycles": error_recovery_cycles,
            "error_log_depth": error_log_depth,
            **kwargs,
        }

        return TemplateObject(config)

    def create_device_specific_signals(
        self,
        device_type: str,
        **kwargs,
    ) -> TemplateObject:
        """
        Create device-specific signal configurations for templates.

        Args:
            device_type: Type of device ('audio', 'network', 'storage', 'graphics', etc.)
            **kwargs: Additional device-specific configuration

        Returns:
            TemplateObject with device-specific signals
        """
        signals = {}

        # Ensure device_type is valid and not None
        if not device_type or not isinstance(device_type, str):
            device_type = "generic"

        if device_type == "audio":
            signals.update(
                {
                    "audio_enable": kwargs.get(
                        "audio_enable", True
                    ),  # Enable by default for audio devices
                    "volume_left": kwargs.get("volume_left", 0x8000),  # 16-bit value
                    "volume_right": kwargs.get("volume_right", 0x8000),  # 16-bit value
                    "sample_rate": kwargs.get("sample_rate", 44100),
                    "audio_format": kwargs.get("audio_format", 0),
                }
            )
        elif device_type == "network":
            signals.update(
                {
                    "link_up": kwargs.get("link_up", True),
                    "link_speed": kwargs.get("link_speed", 1),  # 1Gbps
                    "packet_size": kwargs.get("packet_size", 1500),
                    "network_enable": kwargs.get("network_enable", True),
                }
            )
        elif device_type == "storage":
            signals.update(
                {
                    "storage_ready": kwargs.get("storage_ready", True),
                    "sector_size": kwargs.get("sector_size", 512),
                    "storage_enable": kwargs.get("storage_enable", True),
                }
            )
        elif device_type == "graphics":
            signals.update(
                {
                    "display_enable": kwargs.get("display_enable", True),
                    "resolution_mode": kwargs.get("resolution_mode", 0),
                    "pixel_clock": kwargs.get("pixel_clock", 25_000_000),  # 25MHz
                }
            )
        elif device_type == "media":
            signals.update(
                {
                    "media_enable": kwargs.get("media_enable", True),
                    "codec_type": kwargs.get("codec_type", 0),
                    "stream_count": kwargs.get("stream_count", 1),
                }
            )
        elif device_type == "processor":
            signals.update(
                {
                    "processor_enable": kwargs.get("processor_enable", True),
                    "core_count": kwargs.get("core_count", 1),
                    "freq_mhz": kwargs.get("freq_mhz", 1000),
                }
            )
        elif device_type == "usb":
            signals.update(
                {
                    "usb_enable": kwargs.get("usb_enable", True),
                    "usb_version": kwargs.get("usb_version", 3),  # USB 3.0 by default
                    "port_count": kwargs.get("port_count", 4),
                }
            )

        # Add common device signals
        signals.update(
            {
                "device_type": device_type,
                "device_ready": kwargs.get("device_ready", True),
                "device_enable": kwargs.get("device_enable", True),
                **kwargs,
            }
        )

        return TemplateObject(signals)

    def create_complete_template_context(
        self,
        vendor_id: str = "8086",
        device_id: str = "1234",
        device_type: str = "network",
        device_class: str = "enterprise",
        **kwargs,
    ) -> TemplateObject:
        """
        Create a complete template context with all required variables.

        This is useful for tests and ensures all templates have the variables they need.

        Args:
            vendor_id: PCI vendor ID
            device_id: PCI device ID
            device_type: Device type string
            device_class: Device class string
            **kwargs: Additional context overrides

        Returns:
            TemplateObject with complete context
        """
        # Validate and sanitize inputs
        vendor_id = vendor_id or "8086"
        device_id = device_id or "1234"
        device_type = device_type or "network"
        device_class = device_class or "enterprise"

        # Ensure device_type is a known type
        if device_type not in KNOWN_DEVICE_TYPES:
            device_type = "generic"

        # Create all sub-configurations
        active_device_config = self.create_active_device_config(
            vendor_id=vendor_id,
            device_id=device_id,
            class_code="020000" if device_type == "network" else "000000",
        )

        generation_metadata = self.create_generation_metadata(
            device_signature=f"{vendor_id}:{device_id}"
        )

        # Compute integer aliases early so sub-objects can reference them
        def _parse_int(val, default):
            try:
                return int(str(val), 16)
            except Exception:
                try:
                    return int(val)
                except Exception:
                    return default

        vendor_id_int = _parse_int(vendor_id, 0x8086)
        device_id_int = _parse_int(device_id, 0x1234)

        board_config = self.create_board_config()

        logic_flags = self.create_template_logic_flags()

        # Create comprehensive performance config with all template variables
        perf_config = self.create_performance_config(
            enable_transaction_counters=kwargs.get("enable_transaction_counters", True),
            enable_bandwidth_monitoring=kwargs.get("enable_bandwidth_monitoring", True),
            enable_latency_tracking=kwargs.get("enable_latency_tracking", True),
            enable_latency_measurement=kwargs.get("enable_latency_measurement", True),
            enable_error_counting=kwargs.get("enable_error_counting", True),
            enable_error_rate_tracking=kwargs.get("enable_error_rate_tracking", True),
            enable_performance_grading=kwargs.get("enable_performance_grading", True),
            enable_perf_outputs=kwargs.get("enable_perf_outputs", True),
            # Set signal availability based on device type
            error_signals_available=True,
            network_signals_available=(device_type == "network"),
            storage_signals_available=(device_type == "storage"),
            graphics_signals_available=(device_type == "graphics"),
            audio_signals_available=(device_type == "audio"),
            media_signals_available=(device_type == "media"),
            processor_signals_available=(device_type == "processor"),
            usb_signals_available=(device_type == "usb"),
            generic_signals_available=True,
        )

        # Ensure perf_config exposes an alias for enable_perf_counters and default metrics
        try:
            if isinstance(perf_config, TemplateObject):
                perf_config._data.setdefault(
                    "enable_perf_counters",
                    getattr(perf_config, "enable_transaction_counters", True),
                )
                perf_config._data.setdefault(
                    "metrics_to_monitor", getattr(perf_config, "metrics_to_monitor", [])
                )
        except Exception:
            pass

        # Create power management config with all required variables
        power_management_config = self.create_power_management_config(
            enable_power_management=kwargs.get("power_management", True),
            has_interface_signals=kwargs.get("has_power_interface_signals", False),
        )

        # Ensure transition_delays alias exists
        try:
            if isinstance(power_management_config, TemplateObject):
                power_management_config._data.setdefault(
                    "transition_delays",
                    getattr(power_management_config, "transition_cycles", {}),
                )
        except Exception:
            pass

        # Create error handling config
        error_handling_config = self.create_error_handling_config(
            enable_error_detection=kwargs.get("error_handling", True),
        )

        # Ensure error handling exposes max_retry_count and fatal/recoverable lists
        try:
            if isinstance(error_handling_config, TemplateObject):
                error_handling_config._data.setdefault(
                    "max_retry_count",
                    getattr(error_handling_config, "max_retry_count", 3),
                )
                error_handling_config._data.setdefault(
                    "fatal_errors", getattr(error_handling_config, "fatal_errors", [])
                )
                error_handling_config._data.setdefault(
                    "recoverable_errors",
                    getattr(error_handling_config, "recoverable_errors", []),
                )
        except Exception:
            pass

        # Create device-specific signals
        device_signals = self.create_device_specific_signals(
            device_type=device_type,
            **kwargs,
        )

        # Create complete context
        context = {
            "header": "// Generated SystemVerilog Module",
            "device_type": device_type,
            "device_class": device_class,
            "device_signature": f"32'h{vendor_id.upper()}{device_id.upper()}",
            # Core configurations
            "active_device_config": active_device_config,
            "generation_metadata": generation_metadata,
            "board_config": board_config,
            "perf_config": perf_config,
            # Power management
            "power_management": power_management_config,  # Use the config object, not just boolean
            "power_config": power_management_config,
            # Error handling
            "error_handling": error_handling_config,  # Use the config object, not just boolean
            "error_config": error_handling_config,
            # Performance counters
            "performance_counters": perf_config,
            # Device-specific signals - merge into main context
            **device_signals.to_dict(),
            # Device configuration (converted to TemplateObject for template consistency)
            "device_config": TemplateObject(
                {
                    "vendor_id": vendor_id,
                    "device_id": device_id,
                    "vendor_id_int": vendor_id_int,
                    "device_id_int": device_id_int,
                    "subsystem_vendor_id": vendor_id,
                    "subsystem_device_id": device_id,
                    "class_code": "020000" if device_type == "network" else "000000",
                    "revision_id": "01",
                    "max_payload_size": 256,
                    "msi_vectors": 4,
                    "enable_advanced_features": True,
                    "enable_dma_operations": True,
                    "device_type": device_type,  # Add device_type to device_config
                    "device_class": device_class,  # Add device_class to device_config
                }
            ),
            # Template logic flags
            **logic_flags.to_dict(),
            # Additional configurations (converted to TemplateObjects)
            "config_space": TemplateObject({"size": 256, "raw_data": ""}),
            "bar_config": TemplateObject({"bars": []}),
            "interrupt_config": TemplateObject({"vectors": 4}),
            "msix_config": TemplateObject({"table_size": 4}),
            "timing_config": TemplateObject(
                {
                    "clock_frequency_mhz": kwargs.get("clock_frequency_mhz", 100),
                    "read_latency": kwargs.get("read_latency", 2),
                    "write_latency": kwargs.get("write_latency", 1),
                    "setup_time": kwargs.get("setup_time", 1),
                    "hold_time": kwargs.get("hold_time", 1),
                    "burst_length": kwargs.get("burst_length", 4),
                    "enable_clock_gating": kwargs.get("enable_clock_gating", False),
                }
            ),
            "pcileech_config": type(
                "PCILeechConfig",
                (),
                {
                    "buffer_size": kwargs.get("buffer_size", 4096),
                    "command_timeout": kwargs.get("command_timeout", 1000),
                    "enable_dma": kwargs.get("enable_dma_operations", True),
                    "enable_scatter_gather": kwargs.get("enable_scatter_gather", False),
                    "max_payload_size": kwargs.get("max_payload_size", 256),
                    "max_read_request_size": kwargs.get("max_read_request_size", 512),
                },
            )(),
            # Template variables commonly expected
            "registers": kwargs.get("registers", []),
            # Enable flags for templates
            "enable_performance_counters": perf_config.enable_transaction_counters,
            "enable_error_detection": error_handling_config.enable_error_detection,
            "enable_interrupt": True,
            "enable_custom_config": True,
            "enable_scatter_gather": False,
            "enable_clock_crossing": True,
            "enable_latency_measurement": perf_config.enable_latency_measurement,
            "enable_latency_tracking": perf_config.enable_latency_tracking,
            "enable_error_rate_tracking": perf_config.enable_error_rate_tracking,
            "enable_performance_grading": perf_config.enable_performance_grading,
            # Identifiers
            "vendor_id": vendor_id,
            "device_id": device_id,
            # Variance model - required by register_declarations.sv.j2
            "variance_model": TemplateObject(
                {
                    "enabled": True,
                    "variance_type": "normal",
                    "process_variation": 0.1,  # Required by template
                    "temperature_coefficient": 0.05,  # Required by template
                    "voltage_variation": 0.03,  # Required by template
                    "parameters": {
                        "mean": 0.0,
                        "std_dev": 0.1,
                        "min_value": -1.0,
                        "max_value": 1.0,
                    },
                }
            ),
            # Power state request variable for power management
            "power_state_req": 0x00,  # Default to D0 state (binary: 00)
            **kwargs,  # Allow overrides
        }

        # Provide a minimal `pcileech` top-level config object for TCL templates
        context.setdefault(
            "pcileech",
            TemplateObject(
                {
                    "src_dir": kwargs.get("pcileech_src_dir", "src"),
                    "ip_dir": kwargs.get("pcileech_ip_dir", "ip"),
                    "source_files": kwargs.get("pcileech_source_files", []),
                    "ip_files": kwargs.get("pcileech_ip_files", []),
                    "coefficient_files": kwargs.get("pcileech_coefficient_files", []),
                    "synthesis_strategy": kwargs.get("synthesis_strategy", "default"),
                }
            ),
        )

        # Minimal compatibility layer: keep only a small set of deterministic
        # aliases that templates commonly use for formatting or queries.
        # Templates should prefer canonical sub-objects (device_config, perf_config, board, etc.).
        context.setdefault("msix_config", TemplateObject({"table_size": 4}))

        # Provide integer aliases for vendor/device IDs used for formatting.
        try:
            context["vendor_id_int"] = int(str(vendor_id), 16)
        except Exception:
            try:
                context["vendor_id_int"] = int(vendor_id)
            except Exception:
                context["vendor_id_int"] = 0x8086

        try:
            context["device_id_int"] = int(str(device_id), 16)
        except Exception:
            try:
                context["device_id_int"] = int(device_id)
            except Exception:
                context["device_id_int"] = 0x1234

        # Small conservative top-level defaults used by older templates until they are migrated.
        context.setdefault("BAR_APERTURE_SIZE", kwargs.get("BAR_APERTURE_SIZE", 0x1000))
        context.setdefault("CONFIG_SPACE_SIZE", kwargs.get("CONFIG_SPACE_SIZE", 256))
        context.setdefault("ROM_SIZE", kwargs.get("ROM_SIZE", 0))
        context.setdefault(
            "build_system_version", kwargs.get("build_system_version", "v1.0")
        )
        context.setdefault(
            "header_comment", kwargs.get("header_comment", "// Auto-generated")
        )
        context.setdefault("title", kwargs.get("title", "PCILeech Generated Project"))
        context.setdefault(
            "generated_xdc_path",
            kwargs.get("generated_xdc_path", "constraints/generated.xdc"),
        )
        context.setdefault(
            "project",
            kwargs.get("project", TemplateObject({"name": "pcileech_project"})),
        )

        # Legacy top-level aliases (short-term)
        context.setdefault(
            "device",
            context.get("device_config") or context.get("active_device_config"),
        )
        context.setdefault(
            "device_info",
            context.get("device_config") or context.get("active_device_config"),
        )
        context.setdefault(
            "config",
            context.get("device_config") or context.get("active_device_config"),
        )
        context.setdefault("board", context.get("board_config") or context.get("board"))

        # MSIX aliases
        try:
            context.setdefault(
                "MSIX_TABLE_BIR", context["msix_config"].get("table_bir", 0)
            )
            context.setdefault(
                "MSIX_TABLE_OFFSET", context["msix_config"].get("table_offset", 0x1000)
            )
        except Exception:
            context.setdefault("MSIX_TABLE_BIR", 0)
            context.setdefault("MSIX_TABLE_OFFSET", 0x1000)

        context.setdefault(
            "NUM_MSIX",
            kwargs.get(
                "NUM_MSIX", getattr(context.get("msix_config"), "table_size", 4)
            ),
        )

        # Misc defaults
        context.setdefault("fifo_type", kwargs.get("fifo_type", "simple"))
        context.setdefault(
            "enable_perf_counters", kwargs.get("enable_perf_counters", True)
        )
        context.setdefault("timeout_ms", kwargs.get("timeout_ms", 1000))
        context.setdefault("enable_pme", kwargs.get("enable_pme", True))
        context.setdefault(
            "enable_wake_events", kwargs.get("enable_wake_events", False)
        )

        template_context = TemplateObject(context)

        # Expose helper macros/aliases to templates via simple globals
        try:
            # If templates expect functions like safe_attr in globals, provide a thin wrapper
            template_context._data.setdefault(
                "safe_attr",
                lambda obj, name, default="": (
                    obj.get(name, default)
                    if hasattr(obj, "get")
                    else (getattr(obj, name, default) if obj is not None else default)
                ),
            )
            # Provide safe board helper functions for templates that didn't import helpers
            template_context._data.setdefault(
                "safe_board_name",
                lambda b: (
                    b.get("name")
                    if hasattr(b, "get")
                    else (getattr(b, "name", b) if b is not None else "generic")
                ),
            )
            template_context._data.setdefault(
                "safe_board_fpga_part",
                lambda b: (
                    b.get("fpga_part")
                    if hasattr(b, "get")
                    else (getattr(b, "fpga_part", b) if b is not None else "xc7a35t")
                ),
            )
        except Exception:
            # best-effort; ignore if we can't inject
            pass

        # Conservative top-level fallbacks for legacy templates
        template_context._data.setdefault(
            "synthesis_strategy",
            template_context.get("pcileech", {}).get("synthesis_strategy", "default"),
        )
        template_context._data.setdefault(
            "pcie_rst_pin", kwargs.get("pcie_rst_pin", "")
        )

        # Provide subsys alias commonly referenced by older templates
        try:
            devcfg = template_context.get("device_config")
            if isinstance(devcfg, TemplateObject):
                devcfg._data.setdefault(
                    "subsys_device_id",
                    devcfg.get(
                        "subsystem_device_id",
                        devcfg.get("subsystem_device_id", device_id),
                    ),
                )
                devcfg._data.setdefault(
                    "subsys_vendor_id",
                    devcfg.get(
                        "subsystem_vendor_id",
                        devcfg.get("subsystem_vendor_id", vendor_id),
                    ),
                )
        except Exception:
            pass

        # Ensure perf/power/error nested objects expose the small set of attributes templates expect
        try:
            pf = template_context.get("perf_config")
            if isinstance(pf, TemplateObject):
                pf._data.setdefault(
                    "enable_perf_counters",
                    getattr(pf, "enable_transaction_counters", True),
                )
                pf._data.setdefault(
                    "metrics_to_monitor", getattr(pf, "metrics_to_monitor", [])
                )
        except Exception:
            pass

        try:
            pm = template_context.get("power_management")
            if isinstance(pm, TemplateObject):
                pm._data.setdefault(
                    "transition_delays", getattr(pm, "transition_cycles", {})
                )
        except Exception:
            pass

        try:
            eh = template_context.get("error_handling")
            if isinstance(eh, TemplateObject):
                eh._data.setdefault(
                    "max_retry_count", getattr(eh, "max_retry_count", 3)
                )
                eh._data.setdefault("fatal_errors", getattr(eh, "fatal_errors", []))
                eh._data.setdefault(
                    "recoverable_errors", getattr(eh, "recoverable_errors", [])
                )
        except Exception:
            pass

        # --- Coerce/ensure common objects and aliases to avoid template breakage ---
        # Ensure generation metadata exposes generated_time & pretty values
        try:
            gen = template_context.get("generation_metadata")
            if isinstance(gen, TemplateObject):
                gen._data.setdefault(
                    "generated_time", gen.get("generated_at", gen.get("timestamp", ""))
                )
                gen._data.setdefault(
                    "generated_time_pretty",
                    gen.get(
                        "generated_time_pretty", str(gen.get("generated_time", ""))
                    ),
                )
            else:
                template_context._data["generation_metadata"] = TemplateObject(
                    {
                        "generated_at": gen or "",
                        "generated_time": gen or "",
                        "generated_time_pretty": str(gen or ""),
                    }
                )
        except Exception:
            template_context._data.setdefault(
                "generation_metadata",
                TemplateObject(
                    {
                        "generated_at": "",
                        "generated_time": "",
                        "generated_time_pretty": "",
                    }
                ),
            )

        # Ensure board is a TemplateObject (many templates assume board.name / board.fpga_part)
        try:
            b = template_context.get("board")
            # Normalize strings/dicts into TemplateObject using create_board_config where possible
            if isinstance(b, str):
                template_context._data["board"] = self.create_board_config(
                    board_name=b, fpga_part=b
                )
            elif isinstance(b, dict):
                template_context._data["board"] = TemplateObject(b)
            elif b is None:
                # Prefer the explicit board_config if it exists; otherwise create a default
                template_context._data["board"] = template_context.get(
                    "board_config", self.create_board_config()
                )

            # Ensure nested board object has the commonly-expected attributes
            board_obj = template_context.get("board")
            if isinstance(board_obj, TemplateObject):
                board_obj._data.setdefault(
                    "name", getattr(board_obj, "name", "generic")
                )
                board_obj._data.setdefault(
                    "fpga_part",
                    getattr(
                        board_obj,
                        "fpga_part",
                        template_context.get("fpga_part", "xc7a35t"),
                    ),
                )
                board_obj._data.setdefault(
                    "fpga_family",
                    getattr(
                        board_obj,
                        "fpga_family",
                        template_context.get("fpga_family", "artix7"),
                    ),
                )
                board_obj._data.setdefault(
                    "pcie_ip_type",
                    getattr(
                        board_obj,
                        "pcie_ip_type",
                        template_context.get("pcie_ip_type", "axi_pcie"),
                    ),
                )

                # Ensure constraints exists and is TemplateObject-like with xdc_file
                try:
                    cons = board_obj.get("constraints", None)
                    if cons is None:
                        board_obj._data.setdefault(
                            "constraints", TemplateObject({"xdc_file": None})
                        )
                    elif isinstance(cons, dict):
                        board_obj._data["constraints"] = TemplateObject(cons)
                    # else: assume it's already TemplateObject and fine
                except Exception:
                    board_obj._data.setdefault(
                        "constraints", TemplateObject({"xdc_file": None})
                    )

                # Ensure features/defaults exist
                board_obj._data.setdefault(
                    "features", getattr(board_obj, "features", {})
                )
            else:
                # last-resort default
                template_context._data.setdefault("board", self.create_board_config())
        except Exception:
            template_context._data.setdefault("board", self.create_board_config())

        # Ensure project is a TemplateObject
        try:
            p = template_context.get("project")
            if isinstance(p, str):
                template_context._data["project"] = TemplateObject({"name": p})
            elif p is None:
                template_context._data["project"] = TemplateObject(
                    {"name": "pcileech_project"}
                )
        except Exception:
            template_context._data.setdefault(
                "project", TemplateObject({"name": "pcileech_project"})
            )

        # Ensure device/device_config aliases expose both string and integer ids
        try:
            dev = template_context.get("device_config")
            if isinstance(dev, TemplateObject):
                dev._data.setdefault("device_id", dev.get("device_id", device_id))
                # ensure integer alias exists
                try:
                    dev._data.setdefault(
                        "device_id_int",
                        int(str(dev.get("device_id", device_id)), 16),
                    )
                except Exception:
                    dev._data.setdefault("device_id_int", device_id_int)
                try:
                    dev._data.setdefault(
                        "vendor_id_int",
                        int(str(dev.get("vendor_id", vendor_id)), 16),
                    )
                except Exception:
                    dev._data.setdefault("vendor_id_int", vendor_id_int)
            else:
                template_context._data["device_config"] = TemplateObject(
                    {
                        "device_id": device_id,
                        "device_id_int": device_id_int,
                        "vendor_id": vendor_id,
                        "vendor_id_int": vendor_id_int,
                    }
                )
        except Exception:
            template_context._data.setdefault(
                "device_config",
                TemplateObject(
                    {
                        "device_id": device_id,
                        "device_id_int": device_id_int,
                        "vendor_id": vendor_id,
                        "vendor_id_int": vendor_id_int,
                    }
                ),
            )

        # Ensure a top-level `device` alias exists and points to device_config
        try:
            if not isinstance(template_context.get("device"), TemplateObject):
                template_context._data["device"] = template_context.get("device_config")
            template_context._data.setdefault(
                "device", template_context.get("device_config")
            )
            template_context._data.setdefault(
                "device_info", template_context.get("device_config")
            )
            template_context._data.setdefault(
                "config", template_context.get("device_config")
            )
        except Exception:
            template_context._data.setdefault(
                "device", template_context.get("device_config")
            )

        # Ensure bar list contains at least one bar to avoid index errors
        try:
            bar_config = template_context.get("bar_config")
            if bar_config and hasattr(bar_config, "get"):
                bars = bar_config.get("bars", [])
                if not bars:
                    default_bar = {
                        "base": 0,
                        "size": template_context.get("BAR_APERTURE_SIZE", 0x1000),
                        "type": "io",
                    }
                    # assign as a plain list of dicts (TemplateObject will wrap during rendering if needed)
                    if hasattr(bar_config, "_data"):
                        bar_config._data.setdefault("bars", [default_bar])
                    template_context._data.setdefault("bars", [default_bar])
            else:
                raise AttributeError("bar_config not found or invalid")
        except Exception:
            template_context._data.setdefault(
                "bar_config",
                TemplateObject(
                    {
                        "bars": [
                            {
                                "base": 0,
                                "size": template_context.get(
                                    "BAR_APERTURE_SIZE", 0x1000
                                ),
                                "type": "io",
                            }
                        ]
                    }
                ),
            )

        # Populate error-handling flags at both nested and top-level for templates that expect either
        try:
            eh = template_context.get("error_handling")
            if not isinstance(eh, TemplateObject):
                template_context._data["error_handling"] = TemplateObject(
                    {
                        "enable_crc_check": False,
                        "enable_timeout_detection": False,
                        "enable_error_logging": False,
                        "recoverable_errors": [],
                        "fatal_errors": [],
                        "error_recovery_cycles": 100,
                    }
                )
            else:
                eh._data.setdefault("enable_crc_check", False)
                eh._data.setdefault("enable_timeout_detection", False)
                eh._data.setdefault("enable_error_logging", False)
                eh._data.setdefault("recoverable_errors", [])
                eh._data.setdefault("fatal_errors", [])
                eh._data.setdefault("error_recovery_cycles", 100)

            # mirror to top-level aliases
            template_context._data.setdefault(
                "enable_crc_check", getattr(eh, "enable_crc_check", False)
            )
            template_context._data.setdefault(
                "enable_timeout_detection",
                getattr(eh, "enable_timeout_detection", False),
            )
            template_context._data.setdefault(
                "enable_error_logging", getattr(eh, "enable_error_logging", False)
            )
            template_context._data.setdefault(
                "recoverable_errors", getattr(eh, "recoverable_errors", [])
            )
            template_context._data.setdefault(
                "error_recovery_cycles", getattr(eh, "error_recovery_cycles", 100)
            )
        except Exception:
            template_context._data.setdefault("enable_crc_check", False)
            template_context._data.setdefault("enable_timeout_detection", False)
            template_context._data.setdefault("enable_error_logging", False)
            template_context._data.setdefault("recoverable_errors", [])
            template_context._data.setdefault("error_recovery_cycles", 100)

        # Ensure performance flags exist nested and top-level
        try:
            pf = template_context.get("perf_config")
            if not isinstance(pf, TemplateObject):
                template_context._data["perf_config"] = TemplateObject(
                    {
                        "enable_perf_outputs": False,
                        "enable_transaction_counters": False,
                        "metrics_to_monitor": [],
                    }
                )
            else:
                pf._data.setdefault(
                    "enable_perf_outputs", getattr(pf, "enable_perf_outputs", False)
                )
                pf._data.setdefault(
                    "enable_transaction_counters",
                    getattr(pf, "enable_transaction_counters", False),
                )
                pf._data.setdefault(
                    "metrics_to_monitor", getattr(pf, "metrics_to_monitor", [])
                )

            template_context._data.setdefault(
                "enable_perf_outputs", getattr(pf, "enable_perf_outputs", False)
            )
            template_context._data.setdefault(
                "enable_perf_counters",
                getattr(pf, "enable_transaction_counters", False),
            )
            template_context._data.setdefault(
                "metrics_to_monitor", getattr(pf, "metrics_to_monitor", [])
            )
        except Exception:
            template_context._data.setdefault("enable_perf_outputs", False)
            template_context._data.setdefault("enable_perf_counters", False)
            template_context._data.setdefault("metrics_to_monitor", [])

        # Ensure tr_ns top-level alias maps to power management transition timeout
        try:
            pm = template_context.get("power_management")
            tr = (
                getattr(pm, "transition_timeout_ns", None)
                if isinstance(pm, TemplateObject)
                else (
                    pm.get("transition_timeout_ns", None)
                    if isinstance(pm, dict)
                    else None
                )
            )
            template_context._data.setdefault("tr_ns", tr)
        except Exception:
            template_context._data.setdefault(
                "tr_ns", template_context.get("tr_ns", None)
            )

        # Ensure a minimal 'config' object exists for templates that expect it
        try:
            cfg = template_context.get("config")
            if not isinstance(cfg, TemplateObject):
                template_context._data["config"] = TemplateObject(
                    {
                        "idle_threshold": kwargs.get("idle_threshold", 1000),
                        "enable_clock_gating": kwargs.get("enable_clock_gating", False),
                        "supported_states": kwargs.get(
                            "supported_states", [{"name": "D0", "value": "D0"}]
                        ),
                    }
                )
            else:
                # Populate missing fields on existing config object
                if not hasattr(cfg, "idle_threshold"):
                    try:
                        setattr(
                            cfg, "idle_threshold", kwargs.get("idle_threshold", 1000)
                        )
                    except Exception:
                        cfg._data.setdefault(
                            "idle_threshold", kwargs.get("idle_threshold", 1000)
                        )
                if not hasattr(cfg, "enable_clock_gating"):
                    try:
                        setattr(
                            cfg,
                            "enable_clock_gating",
                            kwargs.get("enable_clock_gating", False),
                        )
                    except Exception:
                        cfg._data.setdefault(
                            "enable_clock_gating",
                            kwargs.get("enable_clock_gating", False),
                        )
                # Ensure error/timing related defaults exist on config for templates
                if not hasattr(cfg, "timeout_cycles"):
                    try:
                        setattr(
                            cfg, "timeout_cycles", kwargs.get("timeout_cycles", 1024)
                        )
                    except Exception:
                        cfg._data.setdefault(
                            "timeout_cycles", kwargs.get("timeout_cycles", 1024)
                        )
                if not hasattr(cfg, "enable_timeout_detection"):
                    try:
                        setattr(cfg, "enable_timeout_detection", False)
                    except Exception:
                        cfg._data.setdefault("enable_timeout_detection", False)
                if not hasattr(cfg, "enable_error_logging"):
                    try:
                        setattr(cfg, "enable_error_logging", False)
                    except Exception:
                        cfg._data.setdefault("enable_error_logging", False)
                if not hasattr(cfg, "error_recovery_cycles"):
                    try:
                        setattr(cfg, "error_recovery_cycles", 100)
                    except Exception:
                        cfg._data.setdefault("error_recovery_cycles", 100)
                if not hasattr(cfg, "fatal_errors"):
                    try:
                        setattr(cfg, "fatal_errors", [])
                    except Exception:
                        cfg._data.setdefault("fatal_errors", [])
                if not hasattr(cfg, "recoverable_errors"):
                    try:
                        setattr(cfg, "recoverable_errors", [])
                    except Exception:
                        cfg._data.setdefault("recoverable_errors", [])
                # Ensure metrics and perf/error defaults are also present on config
                if not hasattr(cfg, "metrics_to_monitor"):
                    try:
                        setattr(
                            cfg,
                            "metrics_to_monitor",
                            kwargs.get("metrics_to_monitor", []),
                        )
                    except Exception:
                        cfg._data.setdefault(
                            "metrics_to_monitor", kwargs.get("metrics_to_monitor", [])
                        )
                if not hasattr(cfg, "max_retry_count"):
                    try:
                        setattr(
                            cfg, "max_retry_count", kwargs.get("max_retry_count", 3)
                        )
                    except Exception:
                        cfg._data.setdefault(
                            "max_retry_count", kwargs.get("max_retry_count", 3)
                        )
                if not hasattr(cfg, "enable_perf_counters"):
                    try:
                        setattr(
                            cfg,
                            "enable_perf_counters",
                            getattr(
                                template_context.get("perf_config"),
                                "enable_transaction_counters",
                                True,
                            ),
                        )
                    except Exception:
                        cfg._data.setdefault(
                            "enable_perf_counters",
                            getattr(
                                template_context.get("perf_config"),
                                "enable_transaction_counters",
                                True,
                            ),
                        )
        except Exception:
            # best-effort
            template_context._data.setdefault(
                "config",
                TemplateObject(
                    {
                        "idle_threshold": kwargs.get("idle_threshold", 1000),
                        "enable_clock_gating": kwargs.get("enable_clock_gating", False),
                        "supported_states": [{"name": "D0", "value": "D0"}],
                    }
                ),
            )

        # Ensure device_config exposes id aliases as attributes
        try:
            dev = template_context.get("device_config")
            if isinstance(dev, TemplateObject):
                dev._data.setdefault("device_id", dev.get("device_id", device_id))
                dev._data.setdefault(
                    "device_id_int", dev.get("device_id_int", device_id_int)
                )
                dev._data.setdefault(
                    "vendor_id_int", dev.get("vendor_id_int", vendor_id_int)
                )
            else:
                template_context._data["device_config"] = TemplateObject(
                    {
                        "device_id": device_id,
                        "device_id_int": device_id_int,
                        "vendor_id": vendor_id,
                        "vendor_id_int": vendor_id_int,
                    }
                )
        except Exception:
            # best-effort
            template_context._data.setdefault(
                "device_config",
                TemplateObject(
                    {
                        "device_id": device_id,
                        "device_id_int": device_id_int,
                        "vendor_id": vendor_id,
                        "vendor_id_int": vendor_id_int,
                    }
                ),
            )

        # Top-level aliases expected by many templates
        template_context._data.setdefault(
            "network_signals_available",
            getattr(
                template_context.get("perf_config"), "network_signals_available", False
            ),
        )
        template_context._data.setdefault(
            "metrics_to_monitor",
            getattr(template_context.get("perf_config"), "metrics_to_monitor", []),
        )
        # tr_ns expected by PMCSR templates (map to transition timeout ns)
        template_context._data.setdefault(
            "tr_ns",
            getattr(
                template_context.get("power_management"),
                "transition_timeout_ns",
                kwargs.get("tr_ns", None),
            ),
        )

        # Best-effort: populate nested TemplateObjects with commonly-expected attributes
        def _populate(obj, defaults: Dict[str, Any]):
            try:
                if isinstance(obj, TemplateObject):
                    for k, v in defaults.items():
                        if not hasattr(obj, k):
                            try:
                                setattr(obj, k, v)
                            except Exception:
                                obj._data.setdefault(k, v)
                elif isinstance(obj, dict):
                    for k, v in defaults.items():
                        obj.setdefault(k, v)
            except Exception:
                # best-effort only
                pass

        # Perf defaults
        _populate(
            template_context.get("perf_config", {}),
            {
                "enable_transaction_counters": getattr(
                    template_context.get("perf_config"),
                    "enable_transaction_counters",
                    True,
                ),
                "enable_perf_outputs": getattr(
                    template_context.get("perf_config"), "enable_perf_outputs", True
                ),
                "metrics_to_monitor": getattr(
                    template_context.get("perf_config"), "metrics_to_monitor", []
                ),
                "error_signals_available": getattr(
                    template_context.get("perf_config"),
                    "error_signals_available",
                    False,
                ),
                "network_signals_available": getattr(
                    template_context.get("perf_config"),
                    "network_signals_available",
                    False,
                ),
            },
        )

        # Power management defaults
        _populate(
            template_context.get("power_management", {}),
            {
                "clk_hz": getattr(
                    template_context.get("power_management"), "clk_hz", 100_000_000
                ),
                "enable_pme": getattr(
                    template_context.get("power_management"), "enable_pme", True
                ),
                "enable_wake_events": getattr(
                    template_context.get("power_management"),
                    "enable_wake_events",
                    False,
                ),
                "transition_delays": getattr(
                    template_context.get("power_management"), "transition_delays", {}
                ),
            },
        )

        # Error handling defaults
        _populate(
            template_context.get("error_handling", {}),
            {
                "enable_crc_check": getattr(
                    template_context.get("error_handling"), "enable_crc_check", False
                ),
                "enable_timeout_detection": getattr(
                    template_context.get("error_handling"),
                    "enable_timeout_detection",
                    False,
                ),
                "enable_error_logging": getattr(
                    template_context.get("error_handling"),
                    "enable_error_logging",
                    False,
                ),
                "recoverable_errors": getattr(
                    template_context.get("error_handling"), "recoverable_errors", []
                ),
                "error_recovery_cycles": getattr(
                    template_context.get("error_handling"), "error_recovery_cycles", 100
                ),
            },
        )

        # Device config defaults
        _populate(
            template_context.get("device_config", {}),
            {
                "class_code": getattr(
                    template_context.get("device_config"), "class_code", "020000"
                ),
                "vendor_id": template_context.get("vendor_id", vendor_id),
                "device_id": template_context.get("device_id", device_id),
                "device_id_int": template_context.get(
                    "device_id_int",
                    (
                        int(str(device_id), 16)
                        if str(device_id).isdigit() or True
                        else 0x1234
                    ),
                ),
                "vendor_id_int": template_context.get(
                    "vendor_id_int",
                    (
                        int(str(vendor_id), 16)
                        if str(vendor_id).isdigit() or True
                        else 0x8086
                    ),
                ),
            },
        )

        # MSIX defaults
        _populate(
            template_context.get("msix_config", {}),
            {
                "table_size": getattr(
                    template_context.get("msix_config"), "table_size", 4
                ),
                "num_vectors": getattr(
                    template_context.get("msix_config"),
                    "num_vectors",
                    getattr(template_context.get("msix_config"), "table_size", 4),
                ),
                "table_bir": getattr(
                    template_context.get("msix_config"), "table_bir", 0
                ),
                "table_offset": getattr(
                    template_context.get("msix_config"), "table_offset", 0x1000
                ),
                "pba_bir": getattr(template_context.get("msix_config"), "pba_bir", 0),
                "pba_offset": getattr(
                    template_context.get("msix_config"), "pba_offset", 0x2000
                ),
            },
        )

        # Timing defaults
        _populate(
            template_context.get("timing_config", {}),
            {
                "clock_frequency_mhz": getattr(
                    template_context.get("timing_config"), "clock_frequency_mhz", 100
                ),
                "enable_clock_gating": getattr(
                    template_context.get("timing_config"), "enable_clock_gating", False
                ),
                "timeout_cycles": getattr(
                    template_context.get("timing_config"), "timeout_cycles", 1024
                ),
            },
        )

        # Board / project defaults
        _populate(
            template_context.get("board", {}),
            {
                "name": getattr(template_context.get("board"), "name", "generic"),
                "fpga_part": getattr(
                    template_context.get("board"), "fpga_part", "xc7a35t"
                ),
            },
        )
        _populate(
            template_context.get("project", {}),
            {
                "name": getattr(
                    template_context.get("project"), "name", "pcileech_project"
                )
            },
        )

        # Top-level small defaults
        template_context._data.setdefault(
            "integration_type", kwargs.get("integration_type", "default")
        )
        template_context._data.setdefault(
            "OVERLAY_ENTRIES", kwargs.get("OVERLAY_ENTRIES", [])
        )
        template_context._data.setdefault(
            "ROM_BAR_INDEX", kwargs.get("ROM_BAR_INDEX", 0)
        )
        template_context._data.setdefault(
            "FLASH_ADDR_OFFSET", kwargs.get("FLASH_ADDR_OFFSET", 0)
        )
        template_context._data.setdefault(
            "CONFIG_SHDW_HI", kwargs.get("CONFIG_SHDW_HI", 0xFFFF)
        )
        template_context._data.setdefault(
            "CONFIG_SHDW_LO", kwargs.get("CONFIG_SHDW_LO", 0x0)
        )
        template_context._data.setdefault(
            "CONFIG_SHDW_SIZE", kwargs.get("CONFIG_SHDW_SIZE", 4)
        )

        # More conservative aliases to satisfy legacy templates during migration
        template_context._data.setdefault(
            "MSIX_PBA_BIR",
            template_context.get("msix_config", {}).get("pba_bir", 0),
        )
        template_context._data.setdefault(
            "MSIX_TABLE_BIR",
            template_context.get("msix_config", {}).get("table_bir", 0),
        )
        template_context._data.setdefault(
            "MSIX_TABLE_OFFSET",
            template_context.get("msix_config", {}).get("table_offset", 0x1000),
        )
        template_context._data.setdefault("DUAL_PORT", False)
        template_context._data.setdefault("ALLOW_ROM_WRITES", False)
        template_context._data.setdefault("USE_QSPI", False)
        template_context._data.setdefault("device_specific_config", {})
        template_context._data.setdefault(
            "class_code",
            template_context.get("device_config", {}).get("class_code", "020000"),
        )
        template_context._data.setdefault(
            "generated_time",
            template_context.get("generation_metadata", {}).get("generated_time", ""),
        )
        template_context._data.setdefault(
            "generated_time_pretty",
            template_context.get("generation_metadata", {}).get(
                "generated_time_pretty", ""
            ),
        )
        # board/project name aliases used by many TCL templates
        if isinstance(template_context.get("board"), str):
            template_context._data.setdefault(
                "board_name", template_context.get("board")
            )
        else:
            template_context._data.setdefault(
                "board_name",
                template_context.get("board", {}).get("name", "generic"),
            )
        if isinstance(template_context.get("project"), str):
            template_context._data.setdefault(
                "project_name", template_context.get("project")
            )
        else:
            template_context._data.setdefault(
                "project_name",
                template_context.get("project", {}).get("name", "pcileech_project"),
            )
        # IP / FPGA aliases
        template_context._data.setdefault(
            "pcie_ip_type",
            template_context.get("pcie_ip_type", "axi_pcie"),
        )
        if isinstance(template_context.get("board"), str):
            # keep fpga_part alias when board is a simple string
            template_context._data.setdefault(
                "fpga_part",
                template_context.get("board"),
            )
        else:
            template_context._data.setdefault(
                "fpga_part",
                template_context.get("board", {}).get("fpga_part", "xc7a35t"),
            )

        # Ensure meta alias for generation metadata
        if not hasattr(template_context, "meta"):
            template_context._data.setdefault(
                "meta", template_context.get("generation_metadata")
            )

        # Map common nested values to legacy top-level aliases used by templates
        try:
            template_context._data.setdefault(
                "MSIX_PBA_OFFSET",
                template_context.get("msix_config", {}).get("pba_offset", 0x2000),
            )
        except Exception:
            template_context._data.setdefault("MSIX_PBA_OFFSET", 0x2000)

        # Overlays
        template_context._data.setdefault(
            "OVERLAY_MAP", template_context.get("OVERLAY_MAP", {})
        )
        template_context._data.setdefault(
            "OVERLAY_ENTRIES", template_context.get("OVERLAY_ENTRIES", [])
        )

        # Bars
        try:
            template_context._data.setdefault(
                "bars", template_context.get("bar_config").get("bars", [])
            )
        except Exception:
            template_context._data.setdefault("bars", [])

        # Error flags as top-level aliases
        try:
            template_context._data.setdefault(
                "enable_crc_check",
                getattr(
                    template_context.get("error_handling"), "enable_crc_check", False
                ),
            )
        except Exception:
            template_context._data.setdefault("enable_crc_check", False)
        try:
            template_context._data.setdefault(
                "enable_timeout_detection",
                getattr(
                    template_context.get("error_handling"),
                    "enable_timeout_detection",
                    False,
                ),
            )
        except Exception:
            template_context._data.setdefault("enable_timeout_detection", False)
        try:
            template_context._data.setdefault(
                "enable_error_logging",
                getattr(
                    template_context.get("error_handling"),
                    "enable_error_logging",
                    False,
                ),
            )
        except Exception:
            template_context._data.setdefault("enable_error_logging", False)
        template_context._data.setdefault(
            "recoverable_errors",
            template_context.get("error_handling", {}).get("recoverable_errors", []),
        )
        template_context._data.setdefault(
            "error_recovery_cycles",
            template_context.get("error_handling", {}).get(
                "error_recovery_cycles", 100
            ),
        )

        # Performance top-level aliases
        template_context._data.setdefault(
            "error_signals_available",
            getattr(
                template_context.get("perf_config"), "error_signals_available", False
            ),
        )
        template_context._data.setdefault(
            "metrics_to_monitor",
            getattr(template_context.get("perf_config"), "metrics_to_monitor", []),
        )

        # Option ROM / SPI defaults
        template_context._data.setdefault("INIT_ROM", False)
        template_context._data.setdefault("SPI_FAST_CMD", False)

        # Legacy macro/flag defaults often referenced by templates
        template_context._data.setdefault("USE_BYTE_ENABLES", False)
        template_context._data.setdefault("ENABLE_SIGNATURE_CHECK", False)
        template_context._data.setdefault("SIGNATURE_CHECK", False)
        template_context._data.setdefault("batch_mode", False)
        # Power optimization flag used by implementation templates
        template_context._data.setdefault(
            "enable_power_opt", kwargs.get("enable_power_opt", False)
        )
        # Incremental implementation flag used by TCL templates
        template_context._data.setdefault(
            "enable_incremental", kwargs.get("enable_incremental", False)
        )
        template_context._data.setdefault("project_dir", kwargs.get("project_dir", "."))
        # Ensure common interrupt support flags and a minimal build object exist
        # These conservative defaults help legacy TCL templates that expect these top-level names.
        template_context._data.setdefault(
            "supports_msi",
            getattr(template_context.get("board"), "supports_msi", False),
        )
        template_context._data.setdefault(
            "supports_msix",
            getattr(template_context.get("board"), "supports_msix", False),
        )
        template_context._data.setdefault(
            "build",
            TemplateObject(
                {
                    "jobs": kwargs.get("build_jobs", 1),
                    "batch_mode": template_context.get("batch_mode", False),
                }
            ),
        )
        template_context._data.setdefault(
            "timeout_cycles",
            getattr(template_context.get("config"), "timeout_cycles", 1024),
        )

        # Extra conservative defaults for legacy templates still being migrated
        template_context._data.setdefault(
            "CUSTOM_WIN_BASE", kwargs.get("CUSTOM_WIN_BASE", 0)
        )
        template_context._data.setdefault(
            "ROM_HEX_FILE", kwargs.get("ROM_HEX_FILE", "")
        )
        template_context._data.setdefault(
            "ENABLE_CACHE", kwargs.get("ENABLE_CACHE", False)
        )
        # Ensure board fields commonly referenced by TCL templates exist
        template_context._data.setdefault(
            "fpga_family",
            getattr(
                template_context.get("board"),
                "fpga_family",
                kwargs.get("fpga_family", "artix7"),
            ),
        )
        template_context._data.setdefault(
            "pcie_ip_type",
            getattr(
                template_context.get("board"),
                "pcie_ip_type",
                kwargs.get("pcie_ip_type", "axi_pcie"),
            ),
        )
        template_context._data.setdefault(
            "constraints",
            getattr(
                template_context.get("board"),
                "constraints",
                kwargs.get("constraints", []),
            ),
        )

        # Perf / metrics defaults
        template_context._data.setdefault(
            "enable_perf_counters",
            getattr(
                template_context.get("perf_config"), "enable_transaction_counters", True
            ),
        )
        template_context._data.setdefault(
            "metrics_to_monitor",
            getattr(template_context.get("perf_config"), "metrics_to_monitor", []),
        )

        # Power defaults referenced by templates
        template_context._data.setdefault(
            "transition_delays",
            getattr(template_context.get("power_management"), "transition_delays", {}),
        )

        # Additional conservative top-level fallbacks to help legacy TCL/SV templates
        template_context._data.setdefault(
            "fatal_errors",
            template_context.get("error_handling", {}).get("fatal_errors", []),
        )

        # Ensure transition_delays top-level alias exists (some templates look here)
        template_context._data.setdefault(
            "transition_delays",
            getattr(template_context.get("power_management"), "transition_delays", {}),
        )

        # Synthesis/implementation strategy used by some TCL flows
        template_context._data.setdefault(
            "implementation_strategy",
            template_context.get("pcileech", {}).get(
                "implementation_strategy",
                template_context.get("synthesis_strategy", "default"),
            ),
        )

        # FPGA/board related fallbacks
        template_context._data.setdefault(
            "max_lanes",
            getattr(
                template_context.get("board"),
                "max_lanes",
                getattr(template_context.get("board_config"), "max_lanes", 4),
            ),
        )

        # Constraint/source defaults used by TCL project generation
        template_context._data.setdefault(
            "constraint_files",
            kwargs.get(
                "constraint_files",
                template_context.get("pcileech", {}).get("coefficient_files", []),
            ),
        )
        template_context._data.setdefault(
            "top_module",
            kwargs.get("top_module", "top"),
        )
        template_context._data.setdefault(
            "pcie_rst_pin",
            template_context.get("pcie_rst_pin", kwargs.get("pcie_rst_pin", "")),
        )

        # Ensure error_thresholds exists (used by some SV error templates)
        template_context._data.setdefault(
            "error_thresholds",
            template_context.get("error_handling", {}).get("error_thresholds", {}),
        )

        # Force board and project to be TemplateObjects to avoid 'str' attribute errors
        try:
            bobj = template_context.get("board")
            if not isinstance(bobj, TemplateObject):
                # If it's a plain string or dict, coerce into TemplateObject using create_board_config
                if isinstance(bobj, str):
                    template_context._data["board"] = self.create_board_config(
                        board_name=bobj, fpga_part=bobj
                    )
                elif isinstance(bobj, dict):
                    template_context._data["board"] = TemplateObject(bobj)
                else:
                    template_context._data["board"] = self.create_board_config()
        except Exception:
            template_context._data.setdefault("board", self.create_board_config())

        try:
            pobj = template_context.get("project")
            if not isinstance(pobj, TemplateObject):
                if isinstance(pobj, str):
                    template_context._data["project"] = TemplateObject({"name": pobj})
                elif isinstance(pobj, dict):
                    template_context._data["project"] = TemplateObject(pobj)
                else:
                    template_context._data["project"] = TemplateObject(
                        {"name": "pcileech_project"}
                    )
        except Exception:
            template_context._data.setdefault(
                "project", TemplateObject({"name": "pcileech_project"})
            )

        # Ensure transition_delays is TemplateObject so templates can use attribute access
        try:
            pm = template_context.get("power_management")
            if isinstance(pm, TemplateObject):
                td = getattr(pm, "transition_delays", None) or getattr(
                    pm, "transition_cycles", {}
                )
                if not isinstance(td, TemplateObject):
                    pm._data["transition_delays"] = TemplateObject(
                        td if isinstance(td, dict) else {}
                    )
                    template_context._data.setdefault(
                        "transition_delays", pm._data["transition_delays"]
                    )
        except Exception:
            template_context._data.setdefault("transition_delays", TemplateObject({}))

        # Ensure device_config fields are plain scalars (avoid TemplateObject in numeric formatting)
        try:
            dev = template_context.get("device_config")
            if isinstance(dev, TemplateObject):
                # Force device_id to string
                try:
                    dev._data.setdefault(
                        "device_id", str(dev.get("device_id", device_id))
                    )
                    dev._data["device_id"] = str(dev.get("device_id"))
                except Exception:
                    dev._data.setdefault("device_id", device_id)
                # Ensure integer alias exists and is an int
                try:
                    dev._data.setdefault(
                        "device_id_int",
                        int(str(dev.get("device_id", device_id)), 16),
                    )
                except Exception:
                    dev._data.setdefault("device_id_int", device_id_int)
                try:
                    dev._data.setdefault(
                        "vendor_id_int",
                        int(str(dev.get("vendor_id", vendor_id)), 16),
                    )
                except Exception:
                    dev._data.setdefault("vendor_id_int", vendor_id_int)
        except Exception:
            # best-effort
            template_context._data.setdefault(
                "device_config",
                TemplateObject(
                    {
                        "device_id": device_id,
                        "device_id_int": device_id_int,
                        "vendor_id": vendor_id,
                        "vendor_id_int": vendor_id_int,
                    }
                ),
            )

        # Ensure device_id exists as both string and int where expected
        template_context._data.setdefault(
            "device_id", template_context.get("device_id", device_id)
        )
        template_context._data.setdefault(
            "vendor_id", template_context.get("vendor_id", vendor_id)
        )

        # Perf counter flag
        template_context._data.setdefault(
            "enable_perf_counters",
            getattr(
                template_context.get("perf_config"), "enable_transaction_counters", True
            ),
        )

        # Power / timing top-level
        template_context._data.setdefault(
            "clk_hz",
            getattr(template_context.get("power_management"), "clk_hz", 100_000_000),
        )
        template_context._data.setdefault(
            "transition_delays",
            getattr(template_context.get("power_management"), "transition_cycles", {}),
        )

        # Generic aliases
        template_context._data.setdefault(
            "pcie_config", template_context.get("pcie_config", {})
        )
        template_context._data.setdefault(
            "pcie_ip_type", template_context.get("pcie_ip_type", "axi_pcie")
        )

        # Generated time alias (map to generation metadata)
        try:
            template_context._data.setdefault(
                "generated_time",
                getattr(
                    template_context.get("generation_metadata"), "generated_at", ""
                ),
            )
        except Exception:
            template_context._data.setdefault("generated_time", "")

        # Robustly ensure nested TemplateObjects expose expected attributes
        nested_defaults = {
            "perf_config": {
                "network_signals_available": getattr(
                    template_context.get("perf_config"),
                    "network_signals_available",
                    False,
                ),
                "metrics_to_monitor": getattr(
                    template_context.get("perf_config"),
                    "metrics_to_monitor",
                    [],
                ),
                "enable_transaction_counters": getattr(
                    template_context.get("perf_config"),
                    "enable_transaction_counters",
                    True,
                ),
            },
            "power_management": {
                "clk_hz": getattr(
                    template_context.get("power_management"), "clk_hz", 100_000_000
                ),
                "transition_cycles": getattr(
                    template_context.get("power_management"), "transition_cycles", {}
                ),
                "tr_ns": getattr(
                    template_context.get("power_management"),
                    "transition_timeout_ns",
                    None,
                ),
            },
            "error_handling": {
                "enable_crc_check": getattr(
                    template_context.get("error_handling"),
                    "enable_crc_check",
                    False,
                ),
                "enable_timeout_detection": getattr(
                    template_context.get("error_handling"),
                    "enable_timeout_detection",
                    False,
                ),
                "enable_error_logging": getattr(
                    template_context.get("error_handling"),
                    "enable_error_logging",
                    False,
                ),
                "recoverable_errors": template_context.get("error_handling", {}).get(
                    "recoverable_errors", []
                ),
                "error_recovery_cycles": template_context.get("error_handling", {}).get(
                    "error_recovery_cycles", 100
                ),
                "fatal_errors": template_context.get("error_handling", {}).get(
                    "fatal_errors", []
                ),
            },
            "device_config": {
                "device_id": template_context.get("device_id", device_id),
                "device_id_int": template_context.get(
                    "device_id_int", context.get("device_id_int")
                ),
                "vendor_id": template_context.get("vendor_id", vendor_id),
                "class_code": template_context.get("device_config", {}).get(
                    "class_code", "020000"
                ),
            },
            "msix_config": {
                "table_size": getattr(
                    template_context.get("msix_config"), "table_size", 4
                ),
                "num_vectors": getattr(
                    template_context.get("msix_config"),
                    "num_vectors",
                    getattr(template_context.get("msix_config"), "table_size", 4),
                ),
            },
            "timing_config": {
                "enable_clock_gating": getattr(
                    template_context.get("timing_config"),
                    "enable_clock_gating",
                    False,
                ),
            },
            "board": {
                "fpga_part": getattr(
                    template_context.get("board"),
                    "fpga_part",
                    template_context.get("fpga_part", "xc7a35t"),
                ),
                "name": getattr(
                    template_context.get("board"),
                    "name",
                    template_context.get("board_name", "generic"),
                ),
                "fpga_family": getattr(
                    template_context.get("board"),
                    "fpga_family",
                    template_context.get("fpga_family", "artix7"),
                ),
            },
            "project": {
                "name": getattr(
                    template_context.get("project"),
                    "name",
                    template_context.get("project_name", "pcileech_project"),
                ),
            },
            "bar_config": {
                "bars": template_context.get("bar_config", {}).get(
                    "bars",
                    [
                        {
                            "base": 0,
                            "size": template_context.get("BAR_APERTURE_SIZE", 0x1000),
                            "type": "io",
                        }
                    ],
                ),
            },
        }

        for ns, defs in nested_defaults.items():
            try:
                ns_obj = template_context.get(ns)
                if isinstance(ns_obj, TemplateObject):
                    for k, v in defs.items():
                        if not hasattr(ns_obj, k):
                            try:
                                setattr(ns_obj, k, v)
                            except Exception:
                                ns_obj._data.setdefault(k, v)
                else:
                    # ensure top-level mapping exists
                    template_context._data.setdefault(ns, defs)
            except Exception:
                # best-effort
                template_context._data.setdefault(ns, defs)

        # Explicitly set attributes on nested TemplateObjects to avoid missing-attribute errors
        try:
            eh = template_context.get("error_handling")
            if isinstance(eh, TemplateObject):
                if not hasattr(eh, "max_retry_count"):
                    try:
                        setattr(eh, "max_retry_count", 3)
                    except Exception:
                        eh._data.setdefault("max_retry_count", 3)
                if not hasattr(eh, "fatal_errors"):
                    try:
                        setattr(eh, "fatal_errors", [])
                    except Exception:
                        eh._data.setdefault("fatal_errors", [])
                if not hasattr(eh, "recoverable_errors"):
                    try:
                        setattr(eh, "recoverable_errors", [])
                    except Exception:
                        eh._data.setdefault("recoverable_errors", [])
        except Exception:
            pass

        try:
            pf = template_context.get("perf_config")
            if isinstance(pf, TemplateObject):
                if not hasattr(pf, "enable_perf_counters"):
                    try:
                        setattr(
                            pf,
                            "enable_perf_counters",
                            getattr(pf, "enable_transaction_counters", True),
                        )
                    except Exception:
                        pf._data.setdefault(
                            "enable_perf_counters",
                            getattr(pf, "enable_transaction_counters", True),
                        )
                if not hasattr(pf, "metrics_to_monitor"):
                    try:
                        setattr(
                            pf,
                            "metrics_to_monitor",
                            getattr(pf, "metrics_to_monitor", []),
                        )
                    except Exception:
                        pf._data.setdefault(
                            "metrics_to_monitor", getattr(pf, "metrics_to_monitor", [])
                        )
        except Exception:
            pass

        try:
            pm = template_context.get("power_management")
            if isinstance(pm, TemplateObject):
                if not hasattr(pm, "transition_delays"):
                    try:
                        setattr(
                            pm,
                            "transition_delays",
                            getattr(pm, "transition_cycles", {}),
                        )
                    except Exception:
                        pm._data.setdefault(
                            "transition_delays", getattr(pm, "transition_cycles", {})
                        )
        except Exception:
            pass

        try:
            dev = template_context.get("device_config")
            if isinstance(dev, TemplateObject):
                if not hasattr(dev, "subsys_device_id"):
                    try:
                        setattr(
                            dev,
                            "subsys_device_id",
                            dev.get("subsystem_device_id", device_id),
                        )
                    except Exception:
                        dev._data.setdefault(
                            "subsys_device_id",
                            dev.get("subsystem_device_id", device_id),
                        )
                if not hasattr(dev, "subsys_vendor_id"):
                    try:
                        setattr(
                            dev,
                            "subsys_vendor_id",
                            dev.get("subsystem_vendor_id", vendor_id),
                        )
                    except Exception:
                        dev._data.setdefault(
                            "subsys_vendor_id",
                            dev.get("subsystem_vendor_id", vendor_id),
                        )
        except Exception:
            pass

        # Validate the context to ensure no missing values required by templates
        self.validate_template_context(template_context)

        return template_context

    def validate_template_context(self, context: TemplateObject) -> None:
        """
        Validate that template context has all critical values.

        Args:
            context: Template context to validate

        Raises:
            ValueError: If critical values are missing
        """
        missing_keys = []
        for key in CRITICAL_TEMPLATE_CONTEXT_KEYS:
            if not hasattr(context, key) or getattr(context, key) is None:
                missing_keys.append(key)

        if missing_keys:
            raise ValueError(
                f"Missing critical template context values: {missing_keys}"
            )

        # Validate nested configurations have required fields
        if hasattr(context, "variance_model"):
            variance_required = [
                "process_variation",
                "temperature_coefficient",
                "voltage_variation",
            ]
            for field in variance_required:
                if not hasattr(context.variance_model, field):
                    setattr(
                        context.variance_model,
                        field,
                        {
                            "process_variation": 0.1,
                            "temperature_coefficient": 0.05,
                            "voltage_variation": 0.03,
                        }[field],
                    )

    def _get_device_class(self, class_code: str) -> str:
        """Get device class from PCI class code."""
        if class_code.startswith("01"):
            return "storage"
        elif class_code.startswith("02"):
            return "network"
        elif class_code.startswith("03"):
            return "display"
        elif class_code.startswith("04"):
            return "multimedia"
        elif class_code.startswith("0c"):
            return "serial_bus"
        else:
            return "generic"


def convert_to_template_object(data: Any) -> Any:
    """
    Convert any data structure to be template-compatible.

    Args:
        data: Data to convert (dict, list, or other)

    Returns:
        Template-compatible version of the data
    """
    if isinstance(data, dict):
        return TemplateObject(data)
    elif isinstance(data, list):
        return [convert_to_template_object(item) for item in data]
    else:
        return data


def ensure_template_compatibility(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure a template context is fully compatible with Jinja2 templates.

    This converts all nested dictionaries to TemplateObjects to support
    both dictionary and attribute access in templates.

    Args:
        context: Original template context

    Returns:
        Template-compatible context
    """
    compatible_context = {}

    for key, value in context.items():
        compatible_context[key] = convert_to_template_object(value)

    return compatible_context
