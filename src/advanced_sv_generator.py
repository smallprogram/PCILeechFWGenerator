#!/usr/bin/env python3
"""
Advanced SystemVerilog Generation Module

This module provides sophisticated SystemVerilog generation capabilities for PCIe device
firmware, including advanced timing models, power management, error handling, performance
counters, and device-specific logic generation.

Advanced SystemVerilog Generation feature for the PCILeechFWGenerator project.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

# Import manufacturing variance for integration
try:
    from .manufacturing_variance import (
        ManufacturingVarianceSimulator,
        DeviceClass,
        VarianceModel,
    )
except ImportError:
    from manufacturing_variance import (
        ManufacturingVarianceSimulator,
        DeviceClass,
        VarianceModel,
    )


class PowerState(Enum):
    """PCIe power states."""

    D0 = "D0"  # Fully operational
    D1 = "D1"  # Intermediate power state
    D2 = "D2"  # Intermediate power state
    D3_HOT = "D3_HOT"  # Software power down
    D3_COLD = "D3_COLD"  # Hardware power down


class LinkState(Enum):
    """PCIe link power states."""

    L0 = "L0"  # Active state
    L0S = "L0s"  # Standby state
    L1 = "L1"  # Low power standby
    L2 = "L2"  # Auxiliary power
    L3 = "L3"  # Off state


class ErrorType(Enum):
    """PCIe error types."""

    CORRECTABLE = "correctable"
    UNCORRECTABLE_NON_FATAL = "uncorrectable_non_fatal"
    UNCORRECTABLE_FATAL = "uncorrectable_fatal"


class DeviceType(Enum):
    """Device-specific types for specialized logic."""

    GENERIC = "generic"
    NETWORK_CONTROLLER = "network"
    STORAGE_CONTROLLER = "storage"
    GRAPHICS_CONTROLLER = "graphics"
    AUDIO_CONTROLLER = "audio"


@dataclass
class PowerManagementConfig:
    """Configuration for power management features."""

    # Power state support
    supported_power_states: List[PowerState] = field(
        default_factory=lambda: [PowerState.D0, PowerState.D1, PowerState.D3_HOT]
    )
    supported_link_states: List[LinkState] = field(
        default_factory=lambda: [LinkState.L0, LinkState.L0S, LinkState.L1]
    )

    # Power transition timing (in clock cycles)
    d0_to_d1_cycles: int = 100
    d1_to_d0_cycles: int = 50
    d0_to_d3_cycles: int = 1000
    d3_to_d0_cycles: int = 10000

    # Link state transition timing
    l0_to_l0s_cycles: int = 10
    l0s_to_l0_cycles: int = 20
    l0_to_l1_cycles: int = 100
    l1_to_l0_cycles: int = 200

    # Power management features
    enable_clock_gating: bool = True
    enable_power_domains: bool = True
    enable_aspm: bool = True  # Active State Power Management
    enable_wake_on_lan: bool = False

    # Power consumption estimates (mW)
    d0_power_mw: float = 1000.0
    d1_power_mw: float = 500.0
    d3_power_mw: float = 10.0


@dataclass
class ErrorHandlingConfig:
    """Configuration for error detection and handling."""

    # Supported error types
    supported_error_types: List[ErrorType] = field(
        default_factory=lambda: [
            ErrorType.CORRECTABLE,
            ErrorType.UNCORRECTABLE_NON_FATAL,
        ]
    )

    # Error detection features
    enable_ecc: bool = True
    enable_parity_check: bool = True
    enable_crc_check: bool = True
    enable_timeout_detection: bool = True

    # Error recovery features
    enable_auto_retry: bool = True
    max_retry_count: int = 3
    enable_error_logging: bool = True
    enable_error_injection: bool = False  # For testing

    # Error thresholds
    correctable_error_threshold: int = 100
    uncorrectable_error_threshold: int = 10

    # Recovery timing (in clock cycles)
    error_recovery_cycles: int = 1000
    retry_delay_cycles: int = 100


@dataclass
class PerformanceCounterConfig:
    """Configuration for performance monitoring counters."""

    # Counter types to implement
    enable_transaction_counters: bool = True
    enable_bandwidth_monitoring: bool = True
    enable_latency_measurement: bool = True
    enable_error_rate_tracking: bool = True

    # Counter specifications
    counter_width_bits: int = 32
    timestamp_width_bits: int = 64

    # Measurement windows
    bandwidth_window_cycles: int = 100000  # ~1ms at 100MHz
    latency_sample_rate: int = 1000  # Sample every 1000 transactions

    # Counter sets based on device type
    network_counters: List[str] = field(
        default_factory=lambda: [
            "rx_packets",
            "tx_packets",
            "rx_bytes",
            "tx_bytes",
            "rx_errors",
            "tx_errors",
        ]
    )
    storage_counters: List[str] = field(
        default_factory=lambda: [
            "read_ops",
            "write_ops",
            "read_bytes",
            "write_bytes",
            "io_errors",
            "queue_depth",
        ]
    )
    graphics_counters: List[str] = field(
        default_factory=lambda: [
            "frame_count",
            "pixel_count",
            "memory_bandwidth",
            "gpu_utilization",
        ]
    )


@dataclass
class DeviceSpecificLogic:
    """Configuration for device-specific logic generation."""

    device_type: DeviceType = DeviceType.GENERIC
    device_class: DeviceClass = DeviceClass.CONSUMER

    # Device capabilities
    max_payload_size: int = 256
    max_read_request_size: int = 512
    msi_vectors: int = 1
    msix_vectors: int = 0

    # Device-specific features
    enable_dma: bool = False
    enable_interrupt_coalescing: bool = False
    enable_virtualization: bool = False
    enable_sr_iov: bool = False

    # Queue management
    tx_queue_depth: int = 256
    rx_queue_depth: int = 256
    command_queue_depth: int = 64

    # Buffer sizes
    tx_buffer_size_kb: int = 64
    rx_buffer_size_kb: int = 64

    # Timing characteristics
    base_frequency_mhz: float = 100.0
    memory_frequency_mhz: float = 200.0


class AdvancedSVGenerator:
    """Advanced SystemVerilog generator with sophisticated device modeling."""

    def __init__(
        self,
        power_config: Optional[PowerManagementConfig] = None,
        error_config: Optional[ErrorHandlingConfig] = None,
        perf_config: Optional[PerformanceCounterConfig] = None,
        device_config: Optional[DeviceSpecificLogic] = None,
    ):
        """Initialize the advanced SystemVerilog generator."""

        self.power_config = power_config or PowerManagementConfig()
        self.error_config = error_config or ErrorHandlingConfig()
        self.perf_config = perf_config or PerformanceCounterConfig()
        self.device_config = device_config or DeviceSpecificLogic()

        # Initialize variance simulator for realistic timing
        self.variance_simulator = ManufacturingVarianceSimulator()

    def generate_advanced_systemverilog(
        self, regs: List[Dict], variance_model: Optional[VarianceModel] = None
    ) -> str:
        """Generate comprehensive advanced SystemVerilog module."""

        # Generate individual components
        declarations = self._generate_declarations(regs, variance_model)
        power_management = self._generate_power_management()
        error_handling = self._generate_error_handling()
        performance_counters = self._generate_performance_counters()
        clock_domains = self._generate_clock_domains(variance_model)
        interrupt_handling = self._generate_interrupt_handling()
        device_specific = self._generate_device_specific_logic()
        register_logic = self._generate_advanced_register_logic(regs, variance_model)

        # Combine into complete module
        module_content = f"""//==============================================================================
// Advanced PCIe Device Controller with Comprehensive Features
// Generated by AdvancedSVGenerator - Advanced SystemVerilog Generation Feature
//
// Features:
// - Advanced power management (D0-D3, L0-L3 states)
// - Comprehensive error handling and recovery
// - Hardware performance counters
// - Multiple clock domain support
// - Device-specific optimizations
// - Manufacturing variance integration
//==============================================================================

module advanced_pcileech_controller #(
    parameter DEVICE_TYPE = "{self.device_config.device_type.value}",
    parameter DEVICE_CLASS = "{self.device_config.device_class.value}",
    parameter MAX_PAYLOAD_SIZE = {self.device_config.max_payload_size},
    parameter MSI_VECTORS = {self.device_config.msi_vectors},
    parameter COUNTER_WIDTH = {self.perf_config.counter_width_bits}
) (
    // Clock and reset
    input logic clk,
    input logic reset_n,
    
    // Additional clock domains
    input logic mem_clk,
    input logic aux_clk,
    
    // PCIe interface
    input logic [31:0] bar_addr,
    input logic [31:0] bar_wr_data,
    input logic bar_wr_en,
    input logic bar_rd_en,
    output logic [31:0] bar_rd_data,
    
    // Power management interface
    input logic [1:0] power_state_req,
    output logic [1:0] power_state_ack,
    input logic [1:0] link_state_req,
    output logic [1:0] link_state_ack,
    
    // Interrupt interface
    output logic msi_request,
    input logic msi_ack,
    output logic [7:0] msi_vector,
    input logic cfg_interrupt_msi_enable,
    output logic cfg_interrupt,
    input logic cfg_interrupt_ready,
    
    // Error reporting interface
    output logic correctable_error,
    output logic uncorrectable_error,
    output logic [7:0] error_code,
    
    // Performance monitoring interface
    output logic [COUNTER_WIDTH-1:0] perf_counter_0,
    output logic [COUNTER_WIDTH-1:0] perf_counter_1,
    output logic [COUNTER_WIDTH-1:0] perf_counter_2,
    output logic [COUNTER_WIDTH-1:0] perf_counter_3,
    
    // Device-specific interfaces
    {self._generate_device_specific_ports()}
);

{declarations}

{clock_domains}

{power_management}

{error_handling}

{performance_counters}

{interrupt_handling}

{device_specific}

{register_logic}

    // Main read logic with advanced features
    always_comb begin
        bar_rd_data = 32'h0;
        
        unique case(bar_addr)
            // Power management registers
            32'h00000000: bar_rd_data = {{30'b0, current_power_state}};
            32'h00000004: bar_rd_data = {{30'b0, current_link_state}};
            
            // Error status registers
            32'h00000008: bar_rd_data = {{24'b0, error_status}};
            32'h0000000C: bar_rd_data = {{24'b0, error_code}};
            
            // Performance counter registers
            32'h00000010: bar_rd_data = perf_counter_0;
            32'h00000014: bar_rd_data = perf_counter_1;
            32'h00000018: bar_rd_data = perf_counter_2;
            32'h0000001C: bar_rd_data = perf_counter_3;
            
            // Device identification
            32'h00000020: bar_rd_data = 32'hADVANCED;  // Advanced controller signature
            32'h00000024: bar_rd_data = {{16'h0, DEVICE_TYPE[15:0]}};
            
            // Clock domain status
            32'h00000028: bar_rd_data = {{29'b0, clock_domain_status}};
            
            {self._generate_register_read_cases(regs)}
            
            default: bar_rd_data = 32'h0;
        endcase
    end

endmodule

//==============================================================================
// Advanced Clock Domain Crossing Module
//==============================================================================
module advanced_clock_crossing #(
    parameter DATA_WIDTH = 32,
    parameter SYNC_STAGES = 3
) (
    input logic src_clk,
    input logic dst_clk,
    input logic reset_n,
    input logic [DATA_WIDTH-1:0] src_data,
    input logic src_valid,
    output logic src_ready,
    output logic [DATA_WIDTH-1:0] dst_data,
    output logic dst_valid,
    input logic dst_ready
);

    // Implementation of advanced clock domain crossing with variance compensation
    logic [SYNC_STAGES-1:0] sync_reg;
    logic [DATA_WIDTH-1:0] data_reg;
    logic valid_reg;
    
    // Source domain logic
    always_ff @(posedge src_clk or negedge reset_n) begin
        if (!reset_n) begin
            data_reg <= '0;
            valid_reg <= 1'b0;
        end else if (src_valid && src_ready) begin
            data_reg <= src_data;
            valid_reg <= 1'b1;
        end else if (sync_reg[SYNC_STAGES-1]) begin
            valid_reg <= 1'b0;
        end
    end
    
    // Destination domain synchronizer
    always_ff @(posedge dst_clk or negedge reset_n) begin
        if (!reset_n) begin
            sync_reg <= '0;
        end else begin
            sync_reg <= {{sync_reg[SYNC_STAGES-2:0], valid_reg}};
        end
    end
    
    assign src_ready = !valid_reg || sync_reg[SYNC_STAGES-1];
    assign dst_data = data_reg;
    assign dst_valid = sync_reg[SYNC_STAGES-1] && dst_ready;

endmodule
"""

        return module_content

    def _generate_declarations(
        self, regs: List[Dict], variance_model: Optional[VarianceModel]
    ) -> str:
        """Generate advanced register and signal declarations."""

        declarations = []

        # Power management signals
        declarations.append("    // Power Management Signals")
        declarations.append("    logic [1:0] current_power_state = 2'b00;  // D0 state")
        declarations.append("    logic [1:0] current_link_state = 2'b00;   // L0 state")
        declarations.append("    logic [15:0] power_transition_timer = 16'h0;")
        declarations.append("    logic power_state_changing = 1'b0;")
        declarations.append("")

        # Error handling signals
        declarations.append("    // Error Handling Signals")
        declarations.append("    logic [7:0] error_status = 8'h0;")
        declarations.append("    logic [7:0] correctable_error_count = 8'h0;")
        declarations.append("    logic [7:0] uncorrectable_error_count = 8'h0;")
        declarations.append("    logic error_recovery_active = 1'b0;")
        declarations.append("    logic [15:0] error_recovery_timer = 16'h0;")
        declarations.append("")

        # Performance counter signals
        declarations.append("    // Performance Counter Signals")
        declarations.append(
            f"    logic [{self.perf_config.counter_width_bits-1}:0] transaction_counter = {self.perf_config.counter_width_bits}'h0;"
        )
        declarations.append(
            f"    logic [{self.perf_config.counter_width_bits-1}:0] bandwidth_counter = {self.perf_config.counter_width_bits}'h0;"
        )
        declarations.append(
            f"    logic [{self.perf_config.counter_width_bits-1}:0] latency_accumulator = {self.perf_config.counter_width_bits}'h0;"
        )
        declarations.append(
            f"    logic [{self.perf_config.counter_width_bits-1}:0] error_rate_counter = {self.perf_config.counter_width_bits}'h0;"
        )
        declarations.append("")

        # Clock domain signals
        declarations.append("    // Clock Domain Management")
        declarations.append("    logic [2:0] clock_domain_status = 3'b111;")
        declarations.append("    logic mem_clk_valid = 1'b1;")
        declarations.append("    logic aux_clk_valid = 1'b1;")
        declarations.append("")

        # Interrupt management
        declarations.append("    // Interrupt Management")
        declarations.append("    logic [7:0] interrupt_vector = 8'h0;")
        declarations.append("    logic interrupt_pending = 1'b0;")
        declarations.append("    logic [3:0] interrupt_priority = 4'h0;")
        declarations.append("")

        # Register-specific declarations with variance integration
        declarations.append("    // Register-Specific Declarations")
        for reg in regs:
            name = reg["name"]
            offset = int(reg["offset"])
            initial_value = int(reg["value"], 16)

            # Apply variance to initial values if model provided
            if variance_model:
                # Add small variance to initial values for realism
                variance_factor = 1.0 + (random.random() - 0.5) * 0.01  # ±0.5% variance
                varied_value = int(initial_value * variance_factor) & 0xFFFFFFFF
                declarations.append(
                    f"    logic [31:0] {name}_reg = 32'h{varied_value:08X};"
                )
            else:
                declarations.append(
                    f"    logic [31:0] {name}_reg = 32'h{initial_value:08X};"
                )

            # Add timing control signals
            declarations.append(f"    logic {name}_access_pending = 1'b0;")
            declarations.append(f"    logic [7:0] {name}_timing_counter = 8'h0;")

        declarations.append("")

        return "\n".join(declarations)

    def _generate_power_management(self) -> str:
        """Generate advanced power management logic."""

        if not self.power_config.supported_power_states:
            return "    // Power management disabled\n"

        power_logic = []

        power_logic.append("    // Advanced Power Management State Machine")
        power_logic.append("    typedef enum logic [2:0] {")
        power_logic.append("        PM_D0_ACTIVE    = 3'b000,")
        power_logic.append("        PM_D0_TO_D1     = 3'b001,")
        power_logic.append("        PM_D1_STANDBY   = 3'b010,")
        power_logic.append("        PM_D1_TO_D0     = 3'b011,")
        power_logic.append("        PM_D0_TO_D3     = 3'b100,")
        power_logic.append("        PM_D3_SUSPEND   = 3'b101,")
        power_logic.append("        PM_D3_TO_D0     = 3'b110,")
        power_logic.append("        PM_ERROR        = 3'b111")
        power_logic.append("    } power_state_t;")
        power_logic.append("")
        power_logic.append("    power_state_t pm_state = PM_D0_ACTIVE;")
        power_logic.append("    power_state_t pm_next_state;")
        power_logic.append("")

        # Power state transition logic
        power_logic.append("    // Power state transition logic")
        power_logic.append("    always_ff @(posedge clk or negedge reset_n) begin")
        power_logic.append("        if (!reset_n) begin")
        power_logic.append("            pm_state <= PM_D0_ACTIVE;")
        power_logic.append("            power_transition_timer <= 16'h0;")
        power_logic.append("            power_state_changing <= 1'b0;")
        power_logic.append("        end else begin")
        power_logic.append("            pm_state <= pm_next_state;")
        power_logic.append("            ")
        power_logic.append("            if (power_state_changing) begin")
        power_logic.append(
            "                power_transition_timer <= power_transition_timer + 1;"
        )
        power_logic.append("            end else begin")
        power_logic.append("                power_transition_timer <= 16'h0;")
        power_logic.append("            end")
        power_logic.append("        end")
        power_logic.append("    end")
        power_logic.append("")

        # Power state combinational logic
        power_logic.append("    // Power state combinational logic")
        power_logic.append("    always_comb begin")
        power_logic.append("        pm_next_state = pm_state;")
        power_logic.append("        power_state_changing = 1'b0;")
        power_logic.append("        ")
        power_logic.append("        case (pm_state)")
        power_logic.append("            PM_D0_ACTIVE: begin")
        power_logic.append("                if (power_state_req == 2'b01) begin")
        power_logic.append("                    pm_next_state = PM_D0_TO_D1;")
        power_logic.append("                    power_state_changing = 1'b1;")
        power_logic.append(
            "                end else if (power_state_req == 2'b11) begin"
        )
        power_logic.append("                    pm_next_state = PM_D0_TO_D3;")
        power_logic.append("                    power_state_changing = 1'b1;")
        power_logic.append("                end")
        power_logic.append("            end")
        power_logic.append("            ")
        power_logic.append("            PM_D0_TO_D1: begin")
        power_logic.append("                power_state_changing = 1'b1;")
        power_logic.append(
            f"                if (power_transition_timer >= {self.power_config.d0_to_d1_cycles}) begin"
        )
        power_logic.append("                    pm_next_state = PM_D1_STANDBY;")
        power_logic.append("                end")
        power_logic.append("            end")
        power_logic.append("            ")
        power_logic.append("            PM_D1_STANDBY: begin")
        power_logic.append("                if (power_state_req == 2'b00) begin")
        power_logic.append("                    pm_next_state = PM_D1_TO_D0;")
        power_logic.append("                    power_state_changing = 1'b1;")
        power_logic.append("                end")
        power_logic.append("            end")
        power_logic.append("            ")
        power_logic.append("            PM_D1_TO_D0: begin")
        power_logic.append("                power_state_changing = 1'b1;")
        power_logic.append(
            f"                if (power_transition_timer >= {self.power_config.d1_to_d0_cycles}) begin"
        )
        power_logic.append("                    pm_next_state = PM_D0_ACTIVE;")
        power_logic.append("                end")
        power_logic.append("            end")
        power_logic.append("            ")
        power_logic.append("            PM_D0_TO_D3: begin")
        power_logic.append("                power_state_changing = 1'b1;")
        power_logic.append(
            f"                if (power_transition_timer >= {self.power_config.d0_to_d3_cycles}) begin"
        )
        power_logic.append("                    pm_next_state = PM_D3_SUSPEND;")
        power_logic.append("                end")
        power_logic.append("            end")
        power_logic.append("            ")
        power_logic.append("            PM_D3_SUSPEND: begin")
        power_logic.append("                if (power_state_req == 2'b00) begin")
        power_logic.append("                    pm_next_state = PM_D3_TO_D0;")
        power_logic.append("                    power_state_changing = 1'b1;")
        power_logic.append("                end")
        power_logic.append("            end")
        power_logic.append("            ")
        power_logic.append("            PM_D3_TO_D0: begin")
        power_logic.append("                power_state_changing = 1'b1;")
        power_logic.append(
            f"                if (power_transition_timer >= {self.power_config.d3_to_d0_cycles}) begin"
        )
        power_logic.append("                    pm_next_state = PM_D0_ACTIVE;")
        power_logic.append("                end")
        power_logic.append("            end")
        power_logic.append("            ")
        power_logic.append("            default: pm_next_state = PM_D0_ACTIVE;")
        power_logic.append("        endcase")
        power_logic.append("    end")
        power_logic.append("")

        # Power state output mapping
        power_logic.append("    // Power state output mapping")
        power_logic.append("    always_comb begin")
        power_logic.append("        case (pm_state)")
        power_logic.append(
            "            PM_D0_ACTIVE, PM_D1_TO_D0, PM_D3_TO_D0: current_power_state = 2'b00;  // D0"
        )
        power_logic.append(
            "            PM_D0_TO_D1, PM_D1_STANDBY: current_power_state = 2'b01;  // D1"
        )
        power_logic.append(
            "            PM_D0_TO_D3, PM_D3_SUSPEND: current_power_state = 2'b11;  // D3"
        )
        power_logic.append("            default: current_power_state = 2'b00;")
        power_logic.append("        endcase")
        power_logic.append("    end")
        power_logic.append("")

        # Clock gating logic if enabled
        if self.power_config.enable_clock_gating:
            power_logic.append("    // Clock gating for power savings")
            power_logic.append("    logic gated_clk;")
            power_logic.append("    logic clock_enable;")
            power_logic.append("    ")
            power_logic.append(
                "    assign clock_enable = (pm_state == PM_D0_ACTIVE) || power_state_changing;"
            )
            power_logic.append("    assign gated_clk = clk & clock_enable;")
            power_logic.append("")

        power_logic.append("    assign power_state_ack = current_power_state;")
        power_logic.append("")

        return "\n".join(power_logic)

    def _generate_error_handling(self) -> str:
        """Generate comprehensive error handling logic."""

        error_logic = []

        error_logic.append("    // Advanced Error Handling and Recovery")
        error_logic.append("    typedef enum logic [2:0] {")
        error_logic.append("        ERR_NORMAL      = 3'b000,")
        error_logic.append("        ERR_DETECTED    = 3'b001,")
        error_logic.append("        ERR_ANALYZING   = 3'b010,")
        error_logic.append("        ERR_RECOVERING  = 3'b011,")
        error_logic.append("        ERR_RETRY       = 3'b100,")
        error_logic.append("        ERR_FATAL       = 3'b101")
        error_logic.append("    } error_state_t;")
        error_logic.append("")
        error_logic.append("    error_state_t error_state = ERR_NORMAL;")
        error_logic.append("    logic [3:0] retry_count = 4'h0;")
        error_logic.append("    logic error_injection_active = 1'b0;")
        error_logic.append("")

        # Error detection logic
        error_logic.append("    // Error detection logic")
        error_logic.append(
            "    logic parity_error, crc_error, timeout_error, ecc_error;"
        )
        error_logic.append("    logic [31:0] timeout_counter = 32'h0;")
        error_logic.append("    ")
        error_logic.append("    // Timeout detection")
        error_logic.append("    always_ff @(posedge clk or negedge reset_n) begin")
        error_logic.append("        if (!reset_n) begin")
        error_logic.append("            timeout_counter <= 32'h0;")
        error_logic.append("            timeout_error <= 1'b0;")
        error_logic.append("        end else if (bar_wr_en || bar_rd_en) begin")
        error_logic.append("            timeout_counter <= 32'h0;")
        error_logic.append("            timeout_error <= 1'b0;")
        error_logic.append("        end else begin")
        error_logic.append("            timeout_counter <= timeout_counter + 1;")
        error_logic.append(
            "            timeout_error <= (timeout_counter > 32'h00100000);  // ~10ms timeout"
        )
        error_logic.append("        end")
        error_logic.append("    end")
        error_logic.append("")

        # Parity and CRC checking
        if self.error_config.enable_parity_check:
            error_logic.append("    // Parity checking")
            error_logic.append(
                "    assign parity_error = bar_wr_en && (^bar_wr_data != ^bar_addr[7:0]);"
            )
            error_logic.append("")

        if self.error_config.enable_crc_check:
            error_logic.append("    // CRC checking (simplified)")
            error_logic.append("    logic [7:0] calculated_crc;")
            error_logic.append(
                "    assign calculated_crc = bar_addr[7:0] ^ bar_wr_data[7:0];"
            )
            error_logic.append(
                "    assign crc_error = bar_wr_en && (calculated_crc != bar_wr_data[15:8]);"
            )
            error_logic.append("")
