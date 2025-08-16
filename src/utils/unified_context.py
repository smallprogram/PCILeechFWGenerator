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
        except ImportError:
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
            if isinstance(value, dict):
                # Recursively convert nested dicts to TemplateObjects
                setattr(self, key, TemplateObject(value))
            elif isinstance(value, list):
                # Handle lists that might contain dicts
                processed_list = []
                for item in value:
                    if isinstance(item, dict):
                        processed_list.append(TemplateObject(item))
                    else:
                        processed_list.append(item)
                setattr(self, key, processed_list)
            else:
                setattr(self, key, value)

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
        metadata = {
            "generated_at": datetime.now().isoformat(),
            "timestamp": datetime.now().isoformat(),  # Keep both for compatibility
            "generator": "PCILeechFWGenerator",
            "version": get_package_version(),
            "device_signature": device_signature or "unknown",
            **kwargs,
        }

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
        known_device_types = ["audio", "network", "storage", "graphics", "generic"]
        if device_type not in known_device_types:
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
            generic_signals_available=True,
        )

        # Create power management config with all required variables
        power_management_config = self.create_power_management_config(
            enable_power_management=kwargs.get("power_management", True),
            has_interface_signals=kwargs.get("has_power_interface_signals", False),
        )

        # Create error handling config
        error_handling_config = self.create_error_handling_config(
            enable_error_detection=kwargs.get("error_handling", True),
        )

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
            # Device configuration
            "device_config": {
                "vendor_id": vendor_id,
                "device_id": device_id,
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
            },
            # Template logic flags
            **logic_flags.to_dict(),
            # Additional configurations
            "config_space": {"size": 256, "raw_data": ""},
            "bar_config": {"bars": []},
            "interrupt_config": {"vectors": 4},
            "msix_config": {"table_size": 4},
            "timing_config": {},
            "pcileech_config": {},
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

        template_context = TemplateObject(context)

        # Validate the context to ensure no missing values
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
        critical_keys = [
            "vendor_id",
            "device_id",
            "device_type",
            "device_class",
            "active_device_config",
            "generation_metadata",
            "board_config",
        ]

        missing_keys = []
        for key in critical_keys:
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
