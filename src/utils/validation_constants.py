"""
Centralized validation constants used across the PCILeech firmware generator.

This module provides consistent validation lists that are used in multiple
places throughout the codebase for template context validation, critical
variable tracking, and security checks.
"""

from typing import Final, List, Tuple

# Critical template context keys that must be present for safe firmware generation
CRITICAL_TEMPLATE_CONTEXT_KEYS: Final[List[str]] = [
    "vendor_id",
    "device_id",
    "device_type",
    "device_class",
    "active_device_config",
    "generation_metadata",
    "board_config",
]

# Required context sections for PCILeech context completeness validation
REQUIRED_CONTEXT_SECTIONS: Final[List[str]] = [
    "device_config",
    "config_space",
    "bar_config",
    "interrupt_config",
]

# Sensitive tokens that indicate variables should never have fallbacks
# These are used by the fallback manager to identify critical hardware identifiers
SENSITIVE_TOKENS: Final[Tuple[str, ...]] = (
    "vendor_id",
    "device_id",
    "revision_id",
    "class_code",
    "bars",
    "subsys",
    # Common sensitive tokens - avoid exposing these in fallbacks
    "token",
    "secret",
    "password",
    "credential",
    "key",
)

# Device identification fields that are required for all device configurations
DEVICE_IDENTIFICATION_FIELDS: Final[List[str]] = [
    "vendor_id",
    "device_id",
    "subsystem_vendor_id",
    "subsystem_device_id",
    "class_code",
    "revision_id",
]

# Board configuration fields that are essential for FPGA targeting
ESSENTIAL_BOARD_CONFIG_FIELDS: Final[List[str]] = [
    "name",
    "fpga_part",
    "fpga_family",
    "pcie_ip_type",
]

# Generation metadata fields required for firmware provenance
REQUIRED_METADATA_FIELDS: Final[List[str]] = [
    "generated_at",
    "generator_version",
    "device_signature",
    "build_timestamp",
]

# Known device types supported by the firmware generator
KNOWN_DEVICE_TYPES: Final[List[str]] = [
    "audio",
    "graphics",
    "media",
    "network",
    "processor",
    "storage",
    "usb",
    "generic",  # Keep generic last as it's the fallback
]
