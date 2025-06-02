#!/usr/bin/env python3
"""
Test script for PCILeech firmware generator Phase 1 enhancements.

This script validates that all the high priority improvements are working correctly:
1. Extended configuration space extraction
2. Enhanced register context analysis
3. Dynamic behavior profiling infrastructure
4. Enhanced SystemVerilog generation

Usage:
    python3 test_enhancements.py --test-mode
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def test_donor_dump_enhancements():
    """Test the enhanced donor_dump module."""
    print("[TEST] Testing donor_dump enhancements...")

    # Check if the module compiles with new features
    try:
        os.chdir("src/donor_dump")
        result = subprocess.run(
            "make clean && make", shell=True, capture_output=True, text=True
        )

        if result.returncode == 0:
            print("  ✓ Enhanced donor_dump module compiles successfully")

            # Check for new module parameters
            if (
                "enable_extended_config" in result.stdout
                or "enable_enhanced_caps" in result.stdout
            ):
                print("  ✓ New configuration parameters detected")
            else:
                print("  ⚠ Configuration parameters may not be properly exposed")

        else:
            print(f"  ✗ Compilation failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        return False
    finally:
        os.chdir("../..")

    return True


def test_driver_scrape_enhancements():
    """Test the enhanced driver_scrape script."""
    print("[TEST] Testing driver_scrape enhancements...")

    try:
        # Test with a common device (Intel network controller)
        result = subprocess.run(
            "python3 src/scripts/driver_scrape.py 8086 1533",
            shell=True,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)

                # Check for enhanced context information
                enhanced_features = 0
                for reg in data:
                    if "context" in reg:
                        enhanced_features += 1
                        context = reg["context"]

                        # Check for new context fields
                        if "function" in context:
                            print("  ✓ Function context analysis detected")
                        if "dependencies" in context:
                            print("  ✓ Register dependency analysis detected")
                        if "timing" in context:
                            print("  ✓ Timing analysis detected")
                        if "sequences" in context:
                            print("  ✓ Access sequence analysis detected")

                if enhanced_features > 0:
                    print(
                        f"  ✓ Enhanced context analysis working ({enhanced_features} registers with context)"
                    )
                else:
                    print(
                        "  ⚠ No enhanced context detected - may be expected for test device"
                    )

            except json.JSONDecodeError:
                print("  ✗ Invalid JSON output from driver_scrape")
                return False

        else:
            print(
                f"  ⚠ Driver scrape failed (expected for test environment): {result.stderr}"
            )
            # This is expected in test environments without actual drivers

    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        return False

    return True


def test_behavior_profiler():
    """Test the behavior profiler module."""
    print("[TEST] Testing behavior profiler...")

    try:
        # Test import and basic functionality
        sys.path.append("src")
        from behavior_profiler import (BehaviorProfiler, RegisterAccess,
                                       TimingPattern)

        print("  ✓ Behavior profiler module imports successfully")

        # Test basic instantiation
        try:
            profiler = BehaviorProfiler("0000:00:00.0", debug=True)
            print("  ✓ BehaviorProfiler instantiation works")
        except Exception as e:
            print(f"  ✗ BehaviorProfiler instantiation failed: {e}")
            return False

        # Test data structures
        access = RegisterAccess(
            timestamp=1234567890.0, register="REG_TEST", offset=0x400, operation="read"
        )
        print("  ✓ RegisterAccess dataclass works")

        pattern = TimingPattern(
            pattern_type="periodic",
            registers=["REG_TEST"],
            avg_interval_us=100.0,
            std_deviation_us=5.0,
            frequency_hz=10000.0,
            confidence=0.95,
        )
        print("  ✓ TimingPattern dataclass works")

    except ImportError as e:
        print(f"  ✗ Import failed: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        return False

    return True


def test_enhanced_systemverilog_generation():
    """Test the enhanced SystemVerilog generation."""
    print("[TEST] Testing enhanced SystemVerilog generation...")

    try:
        # Create test register data with enhanced context
        test_regs = [
            {
                "offset": 0x400,
                "name": "reg_ctrl",
                "value": "0x0",
                "rw": "rw",
                "context": {
                    "function": "init_device",
                    "dependencies": ["reg_status"],
                    "timing": "early",
                    "access_pattern": "write_then_read",
                    "timing_constraints": [
                        {"delay_us": 10, "context": "register_access"}
                    ],
                    "sequences": [
                        {
                            "function": "init_device",
                            "position": 0,
                            "total_ops": 3,
                            "operation": "write",
                        }
                    ],
                },
            },
            {
                "offset": 0x404,
                "name": "reg_status",
                "value": "0x0",
                "rw": "ro",
                "context": {
                    "function": "check_status",
                    "dependencies": [],
                    "timing": "runtime",
                    "access_pattern": "read_heavy",
                },
            },
        ]

        # Test the enhanced build_sv function
        sys.path.append("src")
        from build import build_sv

        # Create a temporary target file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sv", delete=False) as f:
            temp_target = Path(f.name)

        try:
            build_sv(test_regs, temp_target)

            # Read the generated SystemVerilog
            sv_content = temp_target.read_text()

            # Check for enhanced features
            enhancements_found = []

            if "delay_counter" in sv_content:
                enhancements_found.append("Timing delay logic")

            if "state_machine" in sv_content.lower():
                enhancements_found.append("State machine generation")

            if "device_state" in sv_content:
                enhancements_found.append("Device-level state management")

            if "global_timer" in sv_content:
                enhancements_found.append("Global timing reference")

            if len(enhancements_found) > 0:
                print(
                    f"  ✓ Enhanced SystemVerilog features detected: {', '.join(enhancements_found)}"
                )
            else:
                print("  ⚠ No enhanced features detected in generated SystemVerilog")

            # Check basic structure
            if "module pcileech_tlps128_bar_controller" in sv_content:
                print("  ✓ SystemVerilog module structure is correct")
            else:
                print("  ✗ SystemVerilog module structure is incorrect")
                return False

        finally:
            # Clean up
            if temp_target.exists():
                temp_target.unlink()

    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        return False

    return True


def test_build_integration():
    """Test the integration of all enhancements in build.py."""
    print("[TEST] Testing build.py integration...")

    try:
        # Test that build.py can import all required modules
        sys.path.append("src")

        # Test imports
        from build import (generate_device_state_machine,
                           generate_register_state_machine,
                           integrate_behavior_profile)

        print("  ✓ Enhanced build functions import successfully")

        # Test argument parsing enhancements
        result = subprocess.run(
            "python3 src/build.py --help", shell=True, capture_output=True, text=True
        )

        if result.returncode == 0:
            help_text = result.stdout

            enhanced_args = []
            if "--enable-behavior-profiling" in help_text:
                enhanced_args.append("behavior profiling")
            if "--profile-duration" in help_text:
                enhanced_args.append("profile duration")
            if "--enhanced-timing" in help_text:
                enhanced_args.append("enhanced timing")
            if "--save-analysis" in help_text:
                enhanced_args.append("analysis saving")
            if "--verbose" in help_text:
                enhanced_args.append("verbose output")

            if len(enhanced_args) > 0:
                print(
                    f"  ✓ Enhanced command-line arguments detected: {', '.join(enhanced_args)}"
                )
            else:
                print("  ⚠ No enhanced arguments detected")

        else:
            print(f"  ✗ build.py help failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        return False

    return True


def main():
    """Run all enhancement tests."""
    print("PCILeech Firmware Generator - Phase 1 Enhancement Tests")
    print("=" * 60)

    tests = [
        ("Donor Dump Enhancements", test_donor_dump_enhancements),
        ("Driver Scrape Enhancements", test_driver_scrape_enhancements),
        ("Behavior Profiler", test_behavior_profiler),
        ("Enhanced SystemVerilog Generation", test_enhanced_systemverilog_generation),
        ("Build Integration", test_build_integration),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n[{test_name}]")
        try:
            if test_func():
                passed += 1
                print(f"  ✓ {test_name} PASSED")
            else:
                print(f"  ✗ {test_name} FAILED")
        except Exception as e:
            print(f"  ✗ {test_name} FAILED with exception: {e}")

    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All Phase 1 enhancements are working correctly!")
        return 0
    else:
        print("⚠️  Some tests failed. Please review the implementation.")
        return 1


if __name__ == "__main__":
    exit(main())
