#!/usr/bin/env python3
"""
FPGA firmware builder

Usage:
  python3 build.py --bdf 0000:03:00.0 --board 75t

Boards:
  35t  → Squirrel   (PCIeSquirrel)
  75t  → Enigma-X1  (PCIeEnigmaX1)
  100t → ZDMA       (XilinxZDMA)
"""

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Optional

# Import manufacturing variance simulation and advanced SystemVerilog generation
try:
    from .manufacturing_variance import ManufacturingVarianceSimulator, DeviceClass
    from .advanced_sv_main import (
        AdvancedSVGenerator,
        PowerManagementConfig,
        ErrorHandlingConfig,
        PerformanceCounterConfig,
        DeviceSpecificLogic,
        DeviceType,
    )
except ImportError:
    # Fallback for direct execution
    from manufacturing_variance import ManufacturingVarianceSimulator, DeviceClass
    from advanced_sv_main import (
        AdvancedSVGenerator,
        PowerManagementConfig,
        ErrorHandlingConfig,
        PerformanceCounterConfig,
        DeviceSpecificLogic,
        DeviceType,
    )

# Configuration constants
ROOT = Path(__file__).parent.parent.resolve()  # Get project root directory
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
DDIR = ROOT / "src" / "donor_dump"

# BAR aperture size mappings
APERTURE = {
    1024: "1_KB",
    2048: "2_KB",
    4096: "4_KB",
    8192: "8_KB",
    16384: "16_KB",
    32768: "32_KB",
    65536: "64_KB",
    131072: "128_KB",
    262144: "256_KB",
    524288: "512_KB",
    1048576: "1_MB",
    2097152: "2_MB",
    4194304: "4_MB",
    8388608: "8_MB",
    16777216: "16_MB",
}

# Board configuration mapping
BOARD_INFO = {
    "35t": {
        "root": ROOT / "pcileech-fpga" / "PCIeSquirrel",
        "gen": "vivado_generate_project_35t.tcl",
        "base_frequency_mhz": 100.0,
        "device_class": "consumer",
    },
    "75t": {
        "root": ROOT / "pcileech-fpga" / "PCIeEnigmaX1",
        "gen": "vivado_generate_project_75t.tcl",
        "base_frequency_mhz": 125.0,
        "device_class": "industrial",
    },
    "100t": {
        "root": ROOT / "pcileech-fpga" / "XilinxZDMA",
        "gen": "vivado_generate_project_100t.tcl",
        "base_frequency_mhz": 150.0,
        "device_class": "enterprise",
    },
}


def run(cmd: str, **kwargs) -> None:
    """Execute a shell command with logging."""
    print(f"[+] {cmd}")
    subprocess.run(cmd, shell=True, check=True, **kwargs)


def create_secure_tempfile(suffix: str = "", prefix: str = "pcileech_") -> str:
    """
    Create a temporary file with secure permissions in a secure location.
    Returns the path to the created file.
    """
    fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    try:
        # Set secure permissions (owner read/write only)
        os.fchmod(fd, 0o600)
        os.close(fd)
        return tmp_path
    except Exception:
        # Clean up on error
        try:
            os.close(fd)
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def get_donor_info(bdf: str) -> dict:
    """Extract donor PCIe device information using kernel module."""
    os.chdir(DDIR)
    run("make -s")
    run(f"insmod donor_dump.ko bdf={bdf}")

    try:
        raw = subprocess.check_output("cat /proc/donor_dump", shell=True, text=True)
    finally:
        run("rmmod donor_dump")

    # Parse the output into a dictionary
    info = {}
    for line in raw.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            info[key] = value.strip()

    # Validate required fields
    required_fields = [
        "vendor_id",
        "device_id",
        "subvendor_id",
        "subsystem_id",
        "revision_id",
        "bar_size",
        "mpc",
        "mpr",
    ]

    missing_fields = [field for field in required_fields if field not in info]
    if missing_fields:
        sys.exit(f"donor_dump missing required fields: {missing_fields}")

    return info


def scrape_driver_regs(vendor: str, device: str) -> list:
    """Scrape driver registers for the given vendor/device ID."""
    try:
        output = subprocess.check_output(
            f"python3 scripts/driver_scrape.py {vendor} {device}", shell=True, text=True
        )
        data = json.loads(output)

        # Handle new format with state machine analysis
        if isinstance(data, dict) and "registers" in data:
            return data["registers"]
        else:
            # Backward compatibility with old format - ensure data is a list
            if isinstance(data, list):
                return data
            else:
                return []
    except subprocess.CalledProcessError:
        return []


def integrate_behavior_profile(bdf: str, regs: list, duration: float = 10.0) -> list:
    """Integrate behavior profiling data with register definitions."""
    try:
        # Import behavior profiler
        src_path = str(ROOT / "src")
        if src_path not in sys.path:
            sys.path.append(src_path)
        from behavior_profiler import BehaviorProfiler

        print(f"[*] Capturing device behavior profile for {duration}s...")
        profiler = BehaviorProfiler(bdf, debug=False)

        # Capture a short behavior profile
        profile = profiler.capture_behavior_profile(duration)
        analysis = profiler.analyze_patterns(profile)

        # Enhance register definitions with behavioral data
        enhanced_regs = []
        for reg in regs:
            # Ensure we're working with a mutable copy
            enhanced_reg = dict(reg) if isinstance(reg, dict) else reg.copy()

            # Add behavioral timing information
            reg_name = reg["name"].upper()

            # Find matching behavioral data
            for pattern in profile.timing_patterns:
                if reg_name in [r.upper() for r in pattern.registers]:
                    if "context" not in enhanced_reg:
                        enhanced_reg["context"] = {}

                    enhanced_reg["context"]["behavioral_timing"] = {
                        "avg_interval_us": pattern.avg_interval_us,
                        "frequency_hz": pattern.frequency_hz,
                        "confidence": pattern.confidence,
                    }
                    break

            # Add device characteristics
            if "context" not in enhanced_reg:
                enhanced_reg["context"] = {}

            enhanced_reg["context"]["device_analysis"] = {
                "access_frequency_hz": analysis["device_characteristics"][
                    "access_frequency_hz"
                ],
                "timing_regularity": analysis["behavioral_signatures"][
                    "timing_regularity"
                ],
                "performance_class": (
                    "high"
                    if analysis["device_characteristics"]["access_frequency_hz"] > 1000
                    else "standard"
                ),
            }

            enhanced_regs.append(enhanced_reg)

        print(f"[*] Enhanced {len(enhanced_regs)} registers with behavioral data")
        return enhanced_regs

    except Exception as e:
        print(f"[!] Behavior profiling failed: {e}")
        print("[*] Continuing with static analysis only...")
        return regs


def build_sv(
    regs: list,
    target_src: pathlib.Path,
    board_type: str = "75t",
    enable_variance: bool = True,
    variance_metadata: Optional[dict] = None,
) -> None:
    """Generate enhanced SystemVerilog BAR controller from register definitions with variance simulation."""
    if not regs:
        sys.exit("No registers scraped – aborting build")

    declarations = []
    write_cases = []
    read_cases = []
    timing_logic = []
    state_machines = []

    # Initialize variance simulator if enabled
    variance_simulator = None
    variance_model = None
    if enable_variance:
        variance_simulator = ManufacturingVarianceSimulator()

        # Get board configuration
        board_config = BOARD_INFO.get(board_type, BOARD_INFO["75t"])
        device_class_str = board_config.get("device_class", "consumer")
        base_freq = board_config.get("base_frequency_mhz", 100.0)

        # Map string to DeviceClass enum
        device_class_map = {
            "consumer": DeviceClass.CONSUMER,
            "enterprise": DeviceClass.ENTERPRISE,
            "industrial": DeviceClass.INDUSTRIAL,
            "automotive": DeviceClass.AUTOMOTIVE,
        }
        device_class = device_class_map.get(device_class_str, DeviceClass.CONSUMER)

        # Generate or use existing variance model
        if variance_metadata and "device_id" in variance_metadata:
            device_id = variance_metadata["device_id"]
        else:
            device_id = f"board_{board_type}"

        variance_model = variance_simulator.generate_variance_model(
            device_id=device_id, device_class=device_class, base_frequency_mhz=base_freq
        )

        print(
            f"[*] Manufacturing variance simulation enabled for {device_class.value} class device"
        )
        print(
            f"[*] Variance parameters: jitter={variance_model.clock_jitter_percent:.2f}%, "
            f"temp={variance_model.operating_temp_c:.1f}°C"
        )

    # Enhanced register analysis with timing and context
    for reg in regs:
        offset = int(reg["offset"])
        initial_value = int(reg["value"], 16)
        name = reg["name"]
        context = reg.get("context", {})

        # Generate timing-aware register logic
        timing_constraints = context.get("timing_constraints", [])
        access_pattern = context.get("access_pattern", "unknown")

        if reg["rw"] in ["rw", "wo"]:
            # Add timing delay logic for write operations
            delay_cycles = 1  # Default delay
            if timing_constraints:
                # Convert microseconds to clock cycles (assuming 100MHz clock)
                avg_delay_us = sum(
                    tc.get("delay_us", 0) for tc in timing_constraints
                ) / len(timing_constraints)
                delay_cycles = max(1, int(avg_delay_us * 100))  # 100MHz = 10ns period

            # Apply manufacturing variance to timing if enabled
            if variance_simulator and variance_model:
                # Use variance-aware timing generation
                variance_timing_code = (
                    variance_simulator.generate_systemverilog_timing_code(
                        register_name=name,
                        base_delay_cycles=delay_cycles,
                        variance_model=variance_model,
                        offset=offset,
                    )
                )

                # Add register declaration (variance code includes its own timing declarations)
                declarations.append(
                    f"    logic [31:0] {name}_reg = 32'h{initial_value:08X};"
                )

                # Add the variance-aware timing logic (already includes all necessary declarations)
                timing_logic.append(variance_timing_code)
            else:
                # Standard timing logic (backward compatibility)
                declarations.append(
                    f"    logic [31:0] {name}_reg = 32'h{initial_value:08X};"
                )
                declarations.append(
                    f"    logic [{max(1, delay_cycles.bit_length()-1)}:0] {name}_delay_counter = 0;"
                )
                declarations.append(f"    logic {name}_write_pending = 0;")

                # Standard write logic with timing
                timing_logic.append(
                    f"""
    // Standard timing logic for {name}
    always_ff @(posedge clk) begin
        if (!reset_n) begin
            {name}_delay_counter <= 0;
            {name}_write_pending <= 0;
        end else if (bar_wr_en && bar_addr == 32'h{offset:08X}) begin
            {name}_write_pending <= 1;
            {name}_delay_counter <= {delay_cycles};
        end else if ({name}_write_pending && {name}_delay_counter > 0) begin
            {name}_delay_counter <= {name}_delay_counter - 1;
        end else if ({name}_write_pending && {name}_delay_counter == 0) begin
            {name}_reg <= bar_wr_data;
            {name}_write_pending <= 0;
        end
    end"""
                )

            source = f"{name}_reg"
        else:
            # Read-only register - always create a register declaration
            declarations.append(
                f"    logic [31:0] {name}_reg = 32'h{initial_value:08X};"
            )

            # Add read tracking for frequently read registers
            if access_pattern == "read_heavy":
                declarations.append(f"    logic [31:0] {name}_read_count = 0;")
                timing_logic.append(
                    f"""
    // Read tracking for {name}
    always_ff @(posedge clk) begin
        if (!reset_n) begin
            {name}_read_count <= 0;
        end else if (bar_rd_en && bar_addr == 32'h{offset:08X}) begin
            {name}_read_count <= {name}_read_count + 1;
        end
    end"""
                )

            source = f"{name}_reg"

        read_cases.append(f"      32'h{offset:08X}: bar_rd_data <= {source};")

        # Generate state machine for complex register sequences
        sequences = context.get("sequences", [])
        if sequences and len(sequences) > 1:
            state_machine = generate_register_state_machine(name, sequences, offset)
            if state_machine:
                state_machines.append(state_machine)

    # Generate device-specific state machine based on register dependencies
    device_state_machine = generate_device_state_machine(regs)

    # Generate enhanced SystemVerilog module
    sv_content = f"""//--------------------------------------------------------------
// Enhanced PCIe BAR Controller with Realistic Timing and State Machines
// Generated with advanced register context analysis and behavioral modeling
//--------------------------------------------------------------
module pcileech_tlps128_bar_controller
(
 input logic clk, reset_n,
 input logic [31:0] bar_addr, bar_wr_data,
 input logic bar_wr_en, bar_rd_en,
 output logic [31:0] bar_rd_data,
 output logic msi_request,  input logic msi_ack,
 input logic cfg_interrupt_msi_enable,
 output logic cfg_interrupt, input logic cfg_interrupt_ready
);

    // Register declarations with timing support
{os.linesep.join(declarations)}
    
    // Interrupt and state management
    logic irq_latch;
    logic [2:0] device_state = 3'b000;  // Device state machine
    logic [15:0] global_timer = 0;      // Global timing reference
    
    // Global timing reference
    always_ff @(posedge clk) begin
        if (!reset_n) begin
            global_timer <= 0;
        end else begin
            global_timer <= global_timer + 1;
        end
    end

{os.linesep.join(timing_logic)}

    // Enhanced interrupt logic with timing awareness
    always_ff @(posedge clk) begin
        if (!reset_n) begin
            irq_latch <= 0;
        end else if (bar_wr_en) begin
            // Generate interrupt based on write patterns and timing
            irq_latch <= 1;
        end else if (irq_latch && msi_ack) begin
            irq_latch <= 0;
        end
    end

{device_state_machine}

{os.linesep.join(state_machines)}

    // Enhanced read logic with state awareness
    always_comb begin
        unique case(bar_addr)
{os.linesep.join(read_cases)}
            // Device state register
            32'h00000000: bar_rd_data = {{29'b0, device_state}};
            // Global timer register
            32'h00000004: bar_rd_data = {{16'b0, global_timer}};
            default: bar_rd_data = 32'h0;
        endcase
    end

    assign msi_request = irq_latch;
    assign cfg_interrupt = irq_latch & cfg_interrupt_msi_enable;
    
endmodule
"""

    # Write to output and target locations
    (OUT / "bar_controller.sv").write_text(sv_content)
    shutil.copyfile(OUT / "bar_controller.sv", target_src)


def build_advanced_sv(
    regs: list,
    target_src: pathlib.Path,
    board_type: str = "75t",
    enable_variance: bool = True,
    variance_metadata: Optional[dict] = None,
    advanced_features: Optional[dict] = None,
) -> None:
    """Generate advanced SystemVerilog BAR controller with comprehensive features."""

    if not regs:
        sys.exit("No registers scraped – aborting advanced build")

    # Configure advanced features based on board type and requirements
    board_config = BOARD_INFO.get(board_type, BOARD_INFO["75t"])
    device_class_str = board_config.get("device_class", "consumer")
    base_freq = board_config.get("base_frequency_mhz", 100.0)

    # Map string to DeviceClass enum
    device_class_map = {
        "consumer": DeviceClass.CONSUMER,
        "enterprise": DeviceClass.ENTERPRISE,
        "industrial": DeviceClass.INDUSTRIAL,
        "automotive": DeviceClass.AUTOMOTIVE,
    }
    device_class = device_class_map.get(device_class_str, DeviceClass.CONSUMER)

    # Configure advanced features with sensible defaults
    power_config = PowerManagementConfig(
        enable_clock_gating=True,
        enable_aspm=True,
        enable_power_domains=True,
        d0_to_d1_cycles=100,
        d1_to_d0_cycles=50,
        d0_to_d3_cycles=1000,
        d3_to_d0_cycles=10000,
    )

    error_config = ErrorHandlingConfig(
        enable_ecc=True,
        enable_parity_check=True,
        enable_crc_check=True,
        enable_timeout_detection=True,
        enable_auto_retry=True,
        max_retry_count=3,
        enable_error_logging=True,
    )

    perf_config = PerformanceCounterConfig(
        enable_transaction_counters=True,
        enable_bandwidth_monitoring=True,
        enable_latency_measurement=True,
        enable_error_rate_tracking=True,
        enable_device_specific_counters=True,
        counter_width_bits=32,
    )

    # Determine device type based on register patterns
    device_type = DeviceType.GENERIC
    if any("tx" in reg["name"].lower() or "rx" in reg["name"].lower() for reg in regs):
        device_type = DeviceType.NETWORK_CONTROLLER
    elif any(
        "read" in reg["name"].lower() or "write" in reg["name"].lower() for reg in regs
    ):
        device_type = DeviceType.STORAGE_CONTROLLER
    elif any(
        "frame" in reg["name"].lower() or "pixel" in reg["name"].lower() for reg in regs
    ):
        device_type = DeviceType.GRAPHICS_CONTROLLER

    device_config = DeviceSpecificLogic(
        device_type=device_type,
        device_class=device_class,
        base_frequency_mhz=base_freq,
        max_payload_size=256,
        msi_vectors=1,
        enable_dma=device_type != DeviceType.GENERIC,
        enable_interrupt_coalescing=device_type == DeviceType.NETWORK_CONTROLLER,
    )

    # Override with user-provided advanced features
    if advanced_features:
        if "device_type" in advanced_features:
            try:
                device_config.device_type = DeviceType(advanced_features["device_type"])
            except ValueError:
                print(
                    f"[!] Invalid device type: {advanced_features['device_type']}, using {device_type.value}"
                )

        if "enable_power_management" in advanced_features:
            power_config.enable_clock_gating = advanced_features[
                "enable_power_management"
            ]
            power_config.enable_aspm = advanced_features["enable_power_management"]

        if "enable_error_handling" in advanced_features:
            error_config.enable_auto_retry = advanced_features["enable_error_handling"]
            error_config.enable_error_logging = advanced_features[
                "enable_error_handling"
            ]

        if "enable_performance_counters" in advanced_features:
            perf_config.enable_transaction_counters = advanced_features[
                "enable_performance_counters"
            ]
            perf_config.enable_bandwidth_monitoring = advanced_features[
                "enable_performance_counters"
            ]

        if "counter_width" in advanced_features:
            perf_config.counter_width_bits = advanced_features["counter_width"]

    # Initialize variance simulator if enabled
    variance_model = None
    if enable_variance:
        variance_simulator = ManufacturingVarianceSimulator()
        device_id = (
            variance_metadata.get("device_id", f"board_{board_type}")
            if variance_metadata
            else f"board_{board_type}"
        )
        variance_model = variance_simulator.generate_variance_model(
            device_id=device_id, device_class=device_class, base_frequency_mhz=base_freq
        )
        print(
            f"[*] Advanced variance simulation enabled for {device_class.value} class device"
        )
        print(
            f"[*] Variance parameters: jitter={variance_model.clock_jitter_percent:.2f}%, temp={variance_model.operating_temp_c:.1f}°C"
        )

    # Generate advanced SystemVerilog
    print(f"[*] Generating advanced SystemVerilog with {len(regs)} registers")
    generator = AdvancedSVGenerator(
        power_config, error_config, perf_config, device_config
    )
    sv_content = generator.generate_advanced_systemverilog(regs, variance_model)

    # Write to output and target locations
    (OUT / "advanced_bar_controller.sv").write_text(sv_content)
    shutil.copyfile(OUT / "advanced_bar_controller.sv", target_src)

    print(f"[✓] Advanced SystemVerilog generation complete!")
    print(f"[*] Advanced Features Summary:")
    print(f"    - Device type: {device_config.device_type.value}")
    print(f"    - Device class: {device_config.device_class.value}")
    print(f"    - Power management: {'✓' if power_config.enable_clock_gating else '✗'}")
    print(f"    - Error handling: {'✓' if error_config.enable_auto_retry else '✗'}")
    print(
        f"    - Performance counters: {'✓' if perf_config.enable_transaction_counters else '✗'}"
    )
    print(f"    - Manufacturing variance: {'✓' if variance_model else '✗'}")
    print(f"    - Register count: {len(regs)}")


def generate_register_state_machine(
    reg_name: str, sequences: list, offset: int, state_machines: Optional[list] = None
) -> str:
    """Generate a state machine for complex register access sequences."""
    # First try to use extracted state machines if available
    if state_machines:
        for sm_data in state_machines:
            if isinstance(sm_data, dict):
                # Check if this register is involved in the state machine
                sm_registers = sm_data.get("registers", [])
                offset_hex = f"{offset:08x}"
                if (
                    reg_name.lower() in [r.lower() for r in sm_registers]
                    or f"reg_0x{offset_hex}" in sm_registers
                ):

                    # Generate SystemVerilog from extracted state machine
                    states = sm_data.get("states", [])
                    transitions = sm_data.get("transitions", [])

                    if len(states) >= 2:
                        return generate_extracted_state_machine_sv(
                            sm_data, reg_name, offset
                        )

    # Fallback to original sequence-based generation
    if len(sequences) < 2:
        return ""

    states = []
    transitions = []

    for i, seq in enumerate(sequences):
        state_name = f"{reg_name}_state_{i}"
        states.append(state_name)

        if i < len(sequences) - 1:
            next_state = f"{reg_name}_state_{i+1}"
            transitions.append(
                f"        {state_name}: if (sequence_trigger_{reg_name}) next_state = {next_state};"
            )
        else:
            transitions.append(
                f"        {state_name}: if (sequence_trigger_{reg_name}) next_state = {reg_name}_state_0;"
            )

    return f"""
    // State machine for {reg_name} access sequences
    typedef enum logic [2:0] {{
        {', '.join(states)}
    }} {reg_name}_state_t;
    
    {reg_name}_state_t {reg_name}_current_state = {states[0]};
    logic sequence_trigger_{reg_name};
    
    assign sequence_trigger_{reg_name} = bar_wr_en && bar_addr == 32'h{offset:08X};
    
    always_ff @(posedge clk) begin
        if (!reset_n) begin
            {reg_name}_current_state <= {states[0]};
        end else begin
            case ({reg_name}_current_state)
{os.linesep.join(transitions)}
                default: {reg_name}_current_state <= {states[0]};
            endcase
        end
    end"""


def generate_extracted_state_machine_sv(
    sm_data: dict, reg_name: str, offset: int
) -> str:
    """Generate SystemVerilog from extracted state machine data."""
    sm_name = sm_data.get("name", f"{reg_name}_sm")
    states = sm_data.get("states", [])
    transitions = sm_data.get("transitions", [])
    initial_state = sm_data.get("initial_state", states[0] if states else "IDLE")

    if not states:
        return ""

    # Generate state enumeration
    state_bits = max(1, (len(states) - 1).bit_length())
    state_enum = f"typedef enum logic [{state_bits-1}:0] {{\n"
    for i, state in enumerate(states):
        state_enum += f"        {state.upper()} = {i}"
        if i < len(states) - 1:
            state_enum += ","
        state_enum += "\n"
    state_enum += f"    }} {sm_name}_state_t;\n"

    # Generate transition logic
    transition_cases = []
    transitions_by_state = {}

    for transition in transitions:
        from_state = transition.get("from_state", "").upper()
        to_state = transition.get("to_state", "").upper()
        trigger = transition.get("trigger", "")
        condition = transition.get("condition", "")
        transition_type = transition.get("transition_type", "condition")

        if from_state not in transitions_by_state:
            transitions_by_state[from_state] = []

        # Generate condition based on transition type
        sv_condition = ""
        if transition_type == "register_write":
            sv_condition = f"bar_wr_en && bar_addr == 32'h{offset:08X}"
        elif transition_type == "register_read":
            sv_condition = f"bar_rd_en && bar_addr == 32'h{offset:08X}"
        elif transition_type == "timeout":
            sv_condition = "timeout_expired"
        elif condition:
            sv_condition = condition
        else:
            sv_condition = "1'b1"  # Unconditional

        transitions_by_state[from_state].append((to_state, sv_condition))

    # Generate case statements
    for state in states:
        state_upper = state.upper()
        case_content = f"            {state_upper}: begin\n"

        if state_upper in transitions_by_state:
            for to_state, condition in transitions_by_state[state_upper]:
                case_content += f"                if ({condition}) {sm_name}_next_state = {to_state};\n"

        case_content += "            end"
        transition_cases.append(case_content)

    return f"""
    // Enhanced state machine: {sm_name}
    {state_enum}
    
    {sm_name}_state_t {sm_name}_current_state = {initial_state.upper()};
    {sm_name}_state_t {sm_name}_next_state;
    logic timeout_expired;
    
    // State transition logic for {sm_name}
    always_ff @(posedge clk) begin
        if (!reset_n) begin
            {sm_name}_current_state <= {initial_state.upper()};
        end else begin
            {sm_name}_current_state <= {sm_name}_next_state;
        end
    end
    
    // Next state combinational logic for {sm_name}
    always_comb begin
        {sm_name}_next_state = {sm_name}_current_state;
        case ({sm_name}_current_state)
{chr(10).join(transition_cases)}
            default: {sm_name}_next_state = {initial_state.upper()};
        endcase
    end"""


def generate_device_state_machine(regs: list) -> str:
    """Generate a device-level state machine based on register dependencies."""
    # Analyze register dependencies to create device states
    init_regs = []
    runtime_regs = []
    cleanup_regs = []

    for reg in regs:
        context = reg.get("context", {})
        timing = context.get("timing", "unknown")

        if timing == "early":
            init_regs.append(reg["name"])
        elif timing == "late":
            cleanup_regs.append(reg["name"])
        else:
            runtime_regs.append(reg["name"])

    # Define hex prefix to avoid backslash in f-string
    hex_prefix = "32'h"

    # Create init register conditions outside f-string to avoid backslash issues
    init_conditions = []
    for reg in regs:
        if reg["name"] in init_regs[:3]:
            offset_hex = f"{int(reg['offset']):08X}"
            init_conditions.append(f"bar_addr == {hex_prefix}{offset_hex}")

    init_condition_str = " || ".join(init_conditions) if init_conditions else "1'b0"

    return f"""
    // Device-level state machine
    typedef enum logic [2:0] {{
        DEVICE_RESET    = 3'b000,
        DEVICE_INIT     = 3'b001,
        DEVICE_READY    = 3'b010,
        DEVICE_ACTIVE   = 3'b011,
        DEVICE_ERROR    = 3'b100,
        DEVICE_SHUTDOWN = 3'b101
    }} device_state_t;
    
    device_state_t current_state = DEVICE_RESET;
    device_state_t next_state;
    
    // State transition logic
    always_ff @(posedge clk) begin
        if (!reset_n) begin
            current_state <= DEVICE_RESET;
        end else begin
            current_state <= next_state;
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = current_state;
        case (current_state)
            DEVICE_RESET: begin
                if (global_timer > 16'h0010) next_state = DEVICE_INIT;
            end
            DEVICE_INIT: begin
                // Transition to ready after initialization registers are accessed
                if (bar_wr_en && ({init_condition_str})) begin
                    next_state = DEVICE_READY;
                end
            end
            DEVICE_READY: begin
                if (bar_wr_en) next_state = DEVICE_ACTIVE;
            end
            DEVICE_ACTIVE: begin
                // Stay active during normal operation
                if (global_timer[3:0] == 4'hF) next_state = DEVICE_READY;  // Periodic state refresh
            end
            default: next_state = DEVICE_RESET;
        endcase
    end
    
    assign device_state = current_state;"""


def code_from_bytes(byte_count: int) -> int:
    """Convert byte count to PCIe configuration code."""
    byte_to_code = {128: 0, 256: 1, 512: 2, 1024: 3, 2048: 4, 4096: 5}
    return byte_to_code[byte_count]


def build_tcl(info: dict, gen_tcl: str) -> tuple[str, str]:
    """Generate TCL patch file for Vivado configuration."""
    bar_bytes = int(info["bar_size"], 16)
    aperture = APERTURE.get(bar_bytes)
    if not aperture:
        sys.exit(f"Unsupported BAR size: {bar_bytes} bytes")

    # Calculate max payload size and max read request size
    mps = 1 << (int(info["mpc"], 16) + 7)
    mrr = 1 << (int(info["mpr"], 16) + 7)

    # Generate TCL patch content
    patch_content = f"""
set core [get_ips pcie_7x_0]
set_property CONFIG.VENDOR_ID           0x{info['vendor_id']}  $core
set_property CONFIG.DEVICE_ID           0x{info['device_id']}  $core
set_property CONFIG.SUBSYSTEM_VENDOR_ID 0x{info['subvendor_id']} $core
set_property CONFIG.SUBSYSTEM_ID        0x{info['subsystem_id']} $core
set_property CONFIG.REVISION_ID         0x{info['revision_id']}  $core
set_property CONFIG.DEV_CAP_MAX_PAYLOAD_SUPPORTED {code_from_bytes(mps)} $core
set_property CONFIG.DEV_CAP_MAX_READ_REQ_SIZE     {code_from_bytes(mrr)} $core
set_property CONFIG.MSI_CAP_ENABLE true $core
set_property CONFIG.MSI_CAP_MULTIMSGCAP 1 $core
set_property CONFIG.BAR0_APERTURE_SIZE  {aperture} $core
save_project
"""

    tmp_path = create_secure_tempfile(suffix=".tcl", prefix="vivado_patch_")
    try:
        with open(tmp_path, "w") as tmp:
            tmp.write(patch_content)
    except Exception:
        # Clean up on error
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return patch_content, tmp_path


def vivado_run(board_root: pathlib.Path, gen_tcl_path: str, patch_tcl: str) -> None:
    """Execute Vivado build flow."""
    os.chdir(board_root)

    try:
        # Run Vivado build steps
        run(f"vivado -mode batch -source {gen_tcl_path} -notrace")
        run(f"vivado -mode batch -source {patch_tcl} -notrace")
        run("vivado -mode batch -source vivado_build.tcl -notrace")

        # Find and copy the generated bitstream
        bit_files = list(board_root.glob("*/impl_*/pcileech_*_top.bin"))
        if not bit_files:
            sys.exit("No bitstream file found after Vivado build")

        bitstream = bit_files[0]
        shutil.copy(bitstream, OUT / "firmware.bin")
        print(f"[✓] Firmware ready → {OUT / 'firmware.bin'}")

    finally:
        # Clean up temporary TCL file for security
        if os.path.exists(patch_tcl):
            try:
                os.unlink(patch_tcl)
                print(f"[*] Cleaned up temporary file: {patch_tcl}")
            except OSError as e:
                print(f"Warning: Failed to clean up temporary file {patch_tcl}: {e}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Enhanced FPGA firmware builder with behavioral analysis"
    )
    parser.add_argument(
        "--bdf", required=True, help="PCIe Bus:Device.Function (e.g., 0000:03:00.0)"
    )
    parser.add_argument(
        "--board",
        choices=["35t", "75t", "100t"],
        required=True,
        help="Target board type",
    )
    parser.add_argument(
        "--enable-behavior-profiling",
        action="store_true",
        help="Enable dynamic behavior profiling (requires root privileges)",
    )
    parser.add_argument(
        "--profile-duration",
        type=float,
        default=10.0,
        help="Behavior profiling duration in seconds (default: 10.0)",
    )
    parser.add_argument(
        "--enhanced-timing",
        action="store_true",
        default=True,
        help="Enable enhanced timing models in SystemVerilog generation",
    )
    parser.add_argument(
        "--save-analysis", help="Save detailed analysis to specified file"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument(
        "--advanced-sv",
        action="store_true",
        help="Enable advanced SystemVerilog generation with comprehensive features",
    )
    parser.add_argument(
        "--device-type",
        choices=["generic", "network", "storage", "graphics", "audio"],
        default="generic",
        help="Specify device type for advanced generation (default: generic)",
    )
    parser.add_argument(
        "--disable-power-management",
        action="store_true",
        help="Disable power management features in advanced generation",
    )
    parser.add_argument(
        "--disable-error-handling",
        action="store_true",
        help="Disable error handling features in advanced generation",
    )
    parser.add_argument(
        "--disable-performance-counters",
        action="store_true",
        help="Disable performance counters in advanced generation",
    )
    args = parser.parse_args()

    # Get board configuration
    board_config = BOARD_INFO[args.board]
    board_root = Path(board_config["root"])
    target_src = board_root / "src" / "pcileech_tlps128_bar_controller.sv"

    # Validate board directory exists
    if not target_src.parent.exists():
        sys.exit("Expected pcileech board folder missing in repo clone")

    # Extract donor information with extended config space
    print(f"[*] Extracting enhanced donor info from {args.bdf}")
    info = get_donor_info(args.bdf)

    if args.verbose:
        print(
            f"[*] Device info: {info['vendor_id']}:{info['device_id']} (Rev {info['revision_id']})"
        )
        print(f"[*] BAR size: {info['bar_size']}")
        if "extended_config" in info:
            print(f"[*] Extended config space: {len(info['extended_config'])} bytes")

    # Scrape driver registers with enhanced context analysis
    print(
        f"[*] Performing enhanced register analysis for {info['vendor_id']}:{info['device_id']}"
    )
    regs, state_machine_analysis = scrape_driver_regs(
        info["vendor_id"], info["device_id"]
    )
    if not regs:
        sys.exit("Driver scrape returned no registers")

    print(f"[*] Found {len(regs)} registers with context analysis")

    # Print state machine analysis summary
    if state_machine_analysis:
        sm_count = state_machine_analysis.get("extracted_state_machines", 0)
        opt_sm_count = state_machine_analysis.get("optimized_state_machines", 0)
        print(f"[*] Extracted {sm_count} state machines, optimized to {opt_sm_count}")

    # Optional behavior profiling
    if args.enable_behavior_profiling:
        print(f"[*] Integrating dynamic behavior profiling...")
        regs = integrate_behavior_profile(args.bdf, regs, args.profile_duration)
    else:
        print(
            "[*] Skipping behavior profiling (use --enable-behavior-profiling to enable)"
        )

    # Save detailed analysis if requested
    if args.save_analysis:
        analysis_data = {
            "device_info": info,
            "registers": regs,
            "build_config": {
                "board": args.board,
                "enhanced_timing": args.enhanced_timing,
                "behavior_profiling": args.enable_behavior_profiling,
            },
            "timestamp": time.time(),
        }

        with open(args.save_analysis, "w") as f:
            json.dump(analysis_data, f, indent=2, default=str)
        print(f"[*] Analysis saved to {args.save_analysis}")

    # Extract variance metadata from behavior profiling if available
    variance_metadata = None
    if args.enable_behavior_profiling:
        # Check if any register has variance metadata
        for reg in regs:
            if "context" in reg and "variance_metadata" in reg["context"]:
                variance_metadata = reg["context"]["variance_metadata"]
                break

    # Enable variance simulation by default, can be disabled via command line
    enable_variance = getattr(args, "enable_variance", True)

    # Choose SystemVerilog generation method
    if args.advanced_sv:
        print(
            "[*] Generating advanced SystemVerilog controller with comprehensive features"
        )

        # Configure advanced features based on command line arguments
        advanced_features = {
            "device_type": args.device_type,
            "enable_power_management": not args.disable_power_management,
            "enable_error_handling": not args.disable_error_handling,
            "enable_performance_counters": not args.disable_performance_counters,
        }

        build_advanced_sv(
            regs,
            target_src,
            board_type=args.board,
            enable_variance=enable_variance,
            variance_metadata=variance_metadata,
            advanced_features=advanced_features,
        )
    else:
        print("[*] Generating enhanced BAR controller with timing models")

        build_sv(
            regs,
            target_src,
            board_type=args.board,
            enable_variance=enable_variance,
            variance_metadata=variance_metadata,
        )

    # Generate TCL configuration with extended capabilities
    print("[*] Generating Vivado configuration")
    gen_tcl, patch_tcl = build_tcl(info, board_config["gen"])

    # Run Vivado build
    print("[*] Starting Vivado build")
    vivado_run(board_root, gen_tcl, patch_tcl)

    print("[✓] Enhanced firmware generation complete!")
    print(f"[*] Firmware ready → {OUT / 'firmware.bin'}")

    # Print enhancement summary
    print("\n[*] Enhancement Summary:")
    print(f"    - Extended config space: {'✓' if 'extended_config' in info else '✗'}")
    print(f"    - Enhanced register analysis: ✓")
    print(f"    - Behavior profiling: {'✓' if args.enable_behavior_profiling else '✗'}")
    print(f"    - Advanced timing models: {'✓' if args.enhanced_timing else '✗'}")
    print(f"    - Registers analyzed: {len(regs)}")


if __name__ == "__main__":
    main()
