#!/usr/bin/env python3
"""
Test suite for validating TCL generation against real-world examples.

This test suite compares the TCL generation capabilities of the PCILeech firmware
generator against real-world examples from the pcileech-wifi-v2 project.
"""

import os
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import build
from tests.utils import get_pcileech_wifi_tcl_file


class TestTCLValidation:
    """Test TCL generation against real-world examples."""

    @pytest.fixture
    def external_tcl_example(self):
        """Load the external TCL example file from GitHub."""
        try:
            return get_pcileech_wifi_tcl_file()
        except ValueError as e:
            pytest.skip(f"Failed to fetch TCL example from GitHub: {str(e)}")

    @pytest.fixture
    def mock_donor_info_from_example(self):
        """Create mock donor info that matches the external example."""
        return {
            "vendor_id": "0x1814",  # D-Link vendor ID
            "device_id": "0x0201",  # DWA-556 device ID
            "subvendor_id": "0x1814",
            "subsystem_id": "0x0201",
            "revision_id": "0x01",
            "bar_size": "0x20000",  # 128KB
            "mpc": "0x02",
            "mpr": "0x02",
        }

    def test_tcl_structure_matches_example(self, external_tcl_example):
        """Test that our TCL generation follows the same structure as the example."""
        # Extract key structural elements from the example
        example_sections = self._extract_tcl_sections(external_tcl_example)

        # Generate a TCL file with our generator
        with patch("tempfile.mkstemp", return_value=(0, "test.tcl")):
            with patch("os.close"):
                mock_info = {
                    "vendor_id": "0x8086",
                    "device_id": "0x1533",
                    "subvendor_id": "0x8086",
                    "subsystem_id": "0x0000",
                    "revision_id": "0x03",
                    "bar_size": "0x20000",  # 128KB
                    "mpc": "0x02",
                    "mpr": "0x02",
                }
                tcl_content, _ = build.build_tcl(mock_info, "test.tcl")

        # Extract the same sections from our generated TCL
        generated_sections = self._extract_tcl_sections(tcl_content)

        # Compare key sections
        assert "create_project" in generated_sections
        assert "set_property" in generated_sections
        assert "sources_1" in generated_sections

        # Verify that our TCL has the same basic structure
        for key_command in ["create_project", "set_property", "create_fileset"]:
            assert key_command in tcl_content, f"Missing key command: {key_command}"

    def test_tcl_device_id_configuration(
        self, external_tcl_example, mock_donor_info_from_example
    ):
        """Test that device ID configuration in TCL matches the expected pattern."""
        # Generate TCL with the same device info as the example
        with patch("tempfile.mkstemp", return_value=(0, "test.tcl")):
            with patch("os.close"):
                tcl_content, _ = build.build_tcl(
                    mock_donor_info_from_example, "test.tcl"
                )

        # Check for device ID configuration patterns
        vendor_id_pattern = r'set_property -name "VENDOR_ID" -value "0x.*?1814"'
        device_id_pattern = r'set_property -name "DEVICE_ID" -value "0x.*?0201"'

        # Verify our TCL contains proper device ID configuration
        assert (
            re.search(vendor_id_pattern, tcl_content, re.IGNORECASE) is not None
        ), "Vendor ID not properly configured in TCL"
        assert (
            re.search(device_id_pattern, tcl_content, re.IGNORECASE) is not None
        ), "Device ID not properly configured in TCL"

    def test_tcl_bar_size_configuration(
        self, external_tcl_example, mock_donor_info_from_example
    ):
        """Test that BAR size configuration in TCL matches the expected pattern."""
        # Generate TCL with the same BAR size as the example
        with patch("tempfile.mkstemp", return_value=(0, "test.tcl")):
            with patch("os.close"):
                tcl_content, _ = build.build_tcl(
                    mock_donor_info_from_example, "test.tcl"
                )

        # Check for BAR size configuration pattern (128KB)
        bar_size_pattern = r'set_property -name "BAR0_SIZE" -value "128_KB"'

        # Verify our TCL contains proper BAR size configuration
        assert (
            re.search(bar_size_pattern, tcl_content, re.IGNORECASE) is not None
        ), "BAR size not properly configured in TCL"

    def test_tcl_file_inclusion(self, external_tcl_example):
        """Test that our TCL generation includes the necessary SystemVerilog files."""
        # Extract file inclusions from the example
        example_files = self._extract_file_inclusions(external_tcl_example)

        # Generate a TCL file with our generator
        with patch("tempfile.mkstemp", return_value=(0, "test.tcl")):
            with patch("os.close"):
                mock_info = {
                    "vendor_id": "0x8086",
                    "device_id": "0x1533",
                    "subvendor_id": "0x8086",
                    "subsystem_id": "0x0000",
                    "revision_id": "0x03",
                    "bar_size": "0x20000",  # 128KB
                    "mpc": "0x02",
                    "mpr": "0x02",
                }
                tcl_content, _ = build.build_tcl(mock_info, "test.tcl")

        # Extract file inclusions from our generated TCL
        generated_files = self._extract_file_inclusions(tcl_content)

        # Check that our TCL includes key SystemVerilog files
        key_files = [
            "pcileech_tlps128_bar_controller.sv",
            "pcileech_tlps128_cfgspace_shadow.sv",
        ]
        for key_file in key_files:
            assert any(
                key_file in file for file in generated_files
            ), f"Missing key file inclusion: {key_file}"

    def _extract_tcl_sections(self, tcl_content):
        """Extract key sections from TCL content."""
        sections = {}

        # Extract create_project section
        create_project_match = re.search(
            r"create_project.*?(?=\n\n)", tcl_content, re.DOTALL
        )
        if create_project_match:
            sections["create_project"] = create_project_match.group(0)

        # Extract set_property section
        set_property_match = re.search(
            r"set_property.*?(?=\n\n)", tcl_content, re.DOTALL
        )
        if set_property_match:
            sections["set_property"] = set_property_match.group(0)

        # Extract sources_1 section
        sources_match = re.search(
            r"# Create \'sources_1\'.*?(?=\n\n)", tcl_content, re.DOTALL
        )
        if sources_match:
            sections["sources_1"] = sources_match.group(0)

        return sections

    def _extract_file_inclusions(self, tcl_content):
        """Extract file inclusions from TCL content."""
        file_pattern = r'\[file normalize "\$\{origin_dir\}/(.*?)"\]'
        return re.findall(file_pattern, tcl_content)
