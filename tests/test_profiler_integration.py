#!/usr/bin/env python3
"""
Test suite for behavior profiler integration with the build process.

This test suite verifies that the behavior profiler is properly integrated
into the container build process and functions correctly.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import build
from behavior_profiler import BehaviorProfile, BehaviorProfiler
from tui.core.build_orchestrator import BuildOrchestrator
from tui.models.config import BuildConfiguration
from tui.models.device import PCIDevice


class TestProfilerIntegration:
    """Test behavior profiler integration with the build process."""

    @pytest.fixture
    def mock_behavior_profile(self):
        """Create a mock behavior profile for testing."""
        return BehaviorProfile(
            device_bdf="0000:03:00.0",
            capture_duration=10.0,
            total_accesses=100,
            register_accesses=[],
            timing_patterns=[],
            state_transitions={},
            power_states=["D0"],
            interrupt_patterns={},
        )

    @pytest.fixture
    def mock_registers(self):
        """Create mock register data for testing."""
        return [
            {
                "offset": 0x400,
                "name": "control",
                "value": "0x00000000",
                "rw": "rw",
                "context": {
                    "function": "device_control",
                    "timing": "runtime",
                    "access_pattern": "balanced",
                },
            },
            {
                "offset": 0x404,
                "name": "status",
                "value": "0x00000001",
                "rw": "ro",
                "context": {
                    "function": "status_check",
                    "timing": "runtime",
                    "access_pattern": "read_heavy",
                },
            },
        ]

    def test_profiler_flag_enables_profiling(self):
        """Test that the behavior profiler flag correctly enables profiling."""
        with patch("build.integrate_behavior_profile") as mock_integrate:
            # Mock the necessary functions to avoid actual hardware access
            with patch("build.get_donor_info") as mock_donor:
                with patch("build.scrape_driver_regs") as mock_scrape:
                    with patch("build.build_sv") as mock_build_sv:
                        with patch("build.build_tcl") as mock_build_tcl:
                            with patch("build.vivado_run") as mock_vivado:
                                # Set up mocks
                                mock_donor.return_value = {
                                    "vendor_id": "0x1234",
                                    "device_id": "0x5678",
                                }
                                mock_scrape.return_value = ([], {})

                                # Test with profiling enabled
                                sys.argv = [
                                    "build.py",
                                    "--bdf",
                                    "0000:03:00.0",
                                    "--board",
                                    "75t",
                                    "--enable-behavior-profiling",
                                ]

                                # Redirect stdout to avoid cluttering test output
                                with patch("sys.stdout"):
                                    with patch(
                                        "sys.exit"
                                    ):  # Prevent exit on empty registers
                                        build.main()

                                # Verify that integrate_behavior_profile was called
                                mock_integrate.assert_called_once()

                                # Reset mocks
                                mock_integrate.reset_mock()

                                # Test with profiling disabled
                                sys.argv = [
                                    "build.py",
                                    "--bdf",
                                    "0000:03:00.0",
                                    "--board",
                                    "75t",
                                ]

                                # Redirect stdout to avoid cluttering test output
                                with patch("sys.stdout"):
                                    with patch(
                                        "sys.exit"
                                    ):  # Prevent exit on empty registers
                                        build.main()

                                # Verify that integrate_behavior_profile was not called
                                mock_integrate.assert_not_called()

    def test_profile_duration_parameter(self):
        """Test that the profile duration parameter is correctly passed."""
        with patch("build.BehaviorProfiler") as MockProfiler:
            # Create a mock profiler instance
            mock_profiler_instance = Mock()
            mock_profiler_instance.capture_behavior_profile.return_value = (
                self.mock_behavior_profile()
            )
            mock_profiler_instance.analyze_patterns.return_value = {}
            MockProfiler.return_value = mock_profiler_instance

            # Call the integrate_behavior_profile function with a custom duration
            build.integrate_behavior_profile("0000:03:00.0", [], duration=15.0)

            # Verify that the profiler was initialized with the correct BDF
            MockProfiler.assert_called_once_with("0000:03:00.0", debug=False)

            # Verify that capture_behavior_profile was called with the correct duration
            mock_profiler_instance.capture_behavior_profile.assert_called_once_with(
                15.0
            )

    def test_profiler_results_integration(self, mock_registers):
        """Test that profiler results are correctly integrated into the build process."""
        with patch("build.BehaviorProfiler") as MockProfiler:
            # Create a mock profiler instance
            mock_profiler_instance = Mock()

            # Create a mock profile with timing patterns
            mock_profile = self.mock_behavior_profile()

            # Add a timing pattern that matches one of our registers
            from behavior_profiler import TimingPattern

            mock_profile.timing_patterns = [
                TimingPattern(
                    pattern_type="periodic",
                    registers=["CONTROL"],
                    avg_interval_us=100.0,
                    std_deviation_us=5.0,
                    frequency_hz=10000.0,
                    confidence=0.95,
                )
            ]

            # Set up the mock analysis results
            mock_analysis = {
                "device_characteristics": {
                    "access_frequency_hz": 5000.0,
                },
                "behavioral_signatures": {
                    "timing_regularity": 0.85,
                },
            }

            mock_profiler_instance.capture_behavior_profile.return_value = mock_profile
            mock_profiler_instance.analyze_patterns.return_value = mock_analysis
            MockProfiler.return_value = mock_profiler_instance

            # Call the integrate_behavior_profile function
            enhanced_regs = build.integrate_behavior_profile(
                "0000:03:00.0", mock_registers
            )

            # Verify that the registers were enhanced with behavioral data
            assert len(enhanced_regs) == len(mock_registers)

            # Check that the control register has behavioral timing information
            control_reg = next(r for r in enhanced_regs if r["name"] == "control")
            assert "context" in control_reg
            assert "behavioral_timing" in control_reg["context"]
            assert (
                control_reg["context"]["behavioral_timing"]["avg_interval_us"] == 100.0
            )
            assert (
                control_reg["context"]["behavioral_timing"]["frequency_hz"] == 10000.0
            )
            assert control_reg["context"]["behavioral_timing"]["confidence"] == 0.95

            # Check that all registers have device analysis information
            for reg in enhanced_regs:
                assert "context" in reg
                assert "device_analysis" in reg["context"]
                assert (
                    reg["context"]["device_analysis"]["access_frequency_hz"] == 5000.0
                )
                assert reg["context"]["device_analysis"]["timing_regularity"] == 0.85

    @patch("asyncio.create_subprocess_exec")
    @patch("asyncio.get_event_loop")
    async def test_build_orchestrator_profiling_integration(self, mock_loop, mock_exec):
        """Test that the build orchestrator correctly integrates behavior profiling."""
        # Create a mock device and configuration
        device = PCIDevice(
            bdf="0000:03:00.0",
            vendor_id="1234",
            device_id="5678",
            device_name="Test Device",
            driver="test_driver",
        )

        # Create configuration with behavior profiling enabled
        config_with_profiling = BuildConfiguration(
            board_type="75t", behavior_profiling=True, behavior_profile_duration=20.0
        )

        # Create configuration with behavior profiling disabled
        config_without_profiling = BuildConfiguration(
            board_type="75t", behavior_profiling=False
        )

        # Set up the mock process
        mock_process = Mock()
        mock_process.stdout = Mock()
        mock_process.stdout.readline = Mock(return_value=b"")
        mock_process.wait = Mock(return_value=None)
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        # Create the build orchestrator
        orchestrator = BuildOrchestrator()

        # Mock the _run_behavior_profiling method
        with patch.object(orchestrator, "_run_behavior_profiling") as mock_profiling:
            # Test with profiling enabled
            await orchestrator.start_build(device, config_with_profiling)

            # Verify that _run_behavior_profiling was called
            mock_profiling.assert_called_once()

            # Reset mock
            mock_profiling.reset_mock()

            # Test with profiling disabled
            await orchestrator.start_build(device, config_without_profiling)

            # Verify that _run_behavior_profiling was not called
            mock_profiling.assert_not_called()

        # Test that the correct CLI arguments are passed to the container
        with patch.object(orchestrator, "_run_monitored_command") as mock_run:
            # Test with profiling enabled
            await orchestrator.start_build(device, config_with_profiling)

            # Get the command that was passed to _run_monitored_command
            cmd_args = mock_run.call_args[0][0]

            # Convert list to string for easier checking
            cmd_str = " ".join(cmd_args)

            # Verify that the behavior profiling flags are included
            assert "--enable-behavior-profiling" in cmd_str
            assert "--profile-duration 20.0" in cmd_str
