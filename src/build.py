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
    },
    "75t": {
        "root": ROOT / "pcileech-fpga" / "PCIeEnigmaX1",
        "gen": "vivado_generate_project_75t.tcl",
    },
    "100t": {
        "root": ROOT / "pcileech-fpga" / "XilinxZDMA",
        "gen": "vivado_generate_project_100t.tcl",
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
        return json.loads(output)
    except subprocess.CalledProcessError:
        return []


def integrate_behavior_profile(bdf: str, regs: list, duration: float = 10.0) -> list:
    """Integrate behavior profiling data with register definitions."""
    try:
        # Import behavior profiler
        sys.path.append(str(ROOT / "src"))
        from behavior_profiler import BehaviorProfiler

        print(f"[*] Capturing device behavior profile for {duration}s...")
        profiler = BehaviorProfiler(bdf, debug=False)

        # Capture a short behavior profile
        profile = profiler.capture_behavior_profile(duration)
        analysis = profiler.analyze_patterns(profile)

        # Enhance register definitions with behavioral data
        enhanced_regs = []
        for reg in regs:
            enhanced_reg = reg.copy()

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


def build_sv(regs: list, target_src: pathlib.Path) -> None:
    """Generate enhanced SystemVerilog BAR controller from register definitions."""
    if not regs:
        sys.exit("No registers scraped – aborting build")

    declarations = []
    write_cases = []
    read_cases = []
    timing_logic = []
    state_machines = []

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

            declarations.append(
                f"    logic [31:0] {name}_reg = 32'h{initial_value:08X};"
            )
            declarations.append(
                f"    logic [{max(1, delay_cycles.bit_length()-1)}:0] {name}_delay_counter = 0;"
            )
            declarations.append(f"    logic {name}_write_pending = 0;")

            # Enhanced write logic with timing
            timing_logic.append(
                f"""
    // Timing logic for {name}
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
            # Read-only register with potential dynamic behavior
            if access_pattern == "read_heavy":
                # Add read counter for frequently read registers
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

            source = f"32'h{initial_value:08X}"

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


def generate_register_state_machine(reg_name: str, sequences: list, offset: int) -> str:
    """Generate a state machine for complex register access sequences."""
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
                if (bar_wr_en && ({"||".join([f'bar_addr == 32\'h{int(reg["offset"]):08X}' for reg in regs if reg["name"] in init_regs[:3]])})) begin
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

    return gen_tcl, tmp_path


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
    regs = scrape_driver_regs(info["vendor_id"], info["device_id"])
    if not regs:
        sys.exit("Driver scrape returned no registers")

    print(f"[*] Found {len(regs)} registers with context analysis")

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

    # Build enhanced SystemVerilog controller
    print("[*] Generating enhanced BAR controller with timing models")
    build_sv(regs, target_src)

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
