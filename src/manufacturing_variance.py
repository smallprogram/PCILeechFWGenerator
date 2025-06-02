"""
Manufacturing Variance Simulation Module

This module provides realistic hardware variance simulation for PCIe device firmware
generation, adding timing jitter and parameter variations to make generated firmware
more realistic and harder to detect.
"""

import math
import random
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class DeviceClass(Enum):
    """Device class categories with different variance characteristics."""

    CONSUMER = "consumer"
    ENTERPRISE = "enterprise"
    INDUSTRIAL = "industrial"
    AUTOMOTIVE = "automotive"


class VarianceType(Enum):
    """Types of manufacturing variance."""

    CLOCK_JITTER = "clock_jitter"
    REGISTER_TIMING = "register_timing"
    POWER_NOISE = "power_noise"
    TEMPERATURE_DRIFT = "temperature_drift"
    PROCESS_VARIATION = "process_variation"
    PROPAGATION_DELAY = "propagation_delay"


@dataclass
class VarianceParameters:
    """Device-specific variance parameter ranges."""

    device_class: DeviceClass

    # Clock domain crossing timing variations (percentage)
    clock_jitter_percent_min: float = 2.0
    clock_jitter_percent_max: float = 5.0

    # Register access timing jitter (nanoseconds)
    register_timing_jitter_ns_min: float = 10.0
    register_timing_jitter_ns_max: float = 50.0

    # Power supply noise effects (percentage of nominal)
    power_noise_percent_min: float = 1.0
    power_noise_percent_max: float = 3.0

    # Temperature-dependent drift (ppm/°C)
    temperature_drift_ppm_per_c_min: float = 10.0
    temperature_drift_ppm_per_c_max: float = 100.0

    # Process variation effects (percentage)
    process_variation_percent_min: float = 5.0
    process_variation_percent_max: float = 15.0

    # Propagation delay variations (picoseconds)
    propagation_delay_ps_min: float = 50.0
    propagation_delay_ps_max: float = 200.0

    # Operating temperature range (Celsius)
    temp_min_c: float = 0.0
    temp_max_c: float = 85.0

    # Supply voltage variations (percentage)
    voltage_variation_percent: float = 5.0


@dataclass
class VarianceModel:
    """Represents a specific variance model for a device."""

    device_id: str
    device_class: DeviceClass
    base_frequency_mhz: float

    # Applied variance values
    clock_jitter_percent: float
    register_timing_jitter_ns: float
    power_noise_percent: float
    temperature_drift_ppm_per_c: float
    process_variation_percent: float
    propagation_delay_ps: float

    # Environmental conditions
    operating_temp_c: float = 25.0
    supply_voltage_v: float = 3.3

    # Calculated timing adjustments
    timing_adjustments: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        """Calculate timing adjustments based on variance parameters."""
        self._calculate_timing_adjustments()

    def _calculate_timing_adjustments(self):
        """Calculate timing adjustments for various operations."""
        base_period_ns = 1000.0 / self.base_frequency_mhz

        # Clock jitter adjustment
        jitter_ns = base_period_ns * (self.clock_jitter_percent / 100.0)

        # Temperature effects
        temp_delta = self.operating_temp_c - 25.0  # Reference temperature
        temp_adjustment_ppm = self.temperature_drift_ppm_per_c * temp_delta
        temp_factor = 1.0 + (temp_adjustment_ppm / 1_000_000.0)

        # Process variation effects
        process_factor = 1.0 + (self.process_variation_percent / 100.0)

        # Power noise effects
        power_factor = 1.0 + (self.power_noise_percent / 100.0)

        # Combined timing adjustments
        self.timing_adjustments = {
            "base_period_ns": base_period_ns,
            "jitter_ns": jitter_ns,
            "register_access_jitter_ns": self.register_timing_jitter_ns,
            "temp_factor": temp_factor,
            "process_factor": process_factor,
            "power_factor": power_factor,
            "propagation_delay_ps": self.propagation_delay_ps,
            "combined_timing_factor": temp_factor * process_factor * power_factor,
        }


class ManufacturingVarianceSimulator:
    """Main class for simulating manufacturing variance in PCIe devices."""

    # Default variance parameters for different device classes
    DEFAULT_VARIANCE_PARAMS = {
        DeviceClass.CONSUMER: VarianceParameters(
            device_class=DeviceClass.CONSUMER,
            clock_jitter_percent_min=3.0,
            clock_jitter_percent_max=7.0,
            register_timing_jitter_ns_min=20.0,
            register_timing_jitter_ns_max=80.0,
            power_noise_percent_min=2.0,
            power_noise_percent_max=5.0,
            process_variation_percent_min=8.0,
            process_variation_percent_max=20.0,
        ),
        DeviceClass.ENTERPRISE: VarianceParameters(
            device_class=DeviceClass.ENTERPRISE,
            clock_jitter_percent_min=1.5,
            clock_jitter_percent_max=3.0,
            register_timing_jitter_ns_min=5.0,
            register_timing_jitter_ns_max=25.0,
            power_noise_percent_min=0.5,
            power_noise_percent_max=2.0,
            process_variation_percent_min=3.0,
            process_variation_percent_max=8.0,
        ),
        DeviceClass.INDUSTRIAL: VarianceParameters(
            device_class=DeviceClass.INDUSTRIAL,
            clock_jitter_percent_min=2.0,
            clock_jitter_percent_max=4.0,
            register_timing_jitter_ns_min=10.0,
            register_timing_jitter_ns_max=40.0,
            power_noise_percent_min=1.0,
            power_noise_percent_max=3.0,
            process_variation_percent_min=5.0,
            process_variation_percent_max=12.0,
            temp_min_c=-40.0,
            temp_max_c=125.0,
        ),
        DeviceClass.AUTOMOTIVE: VarianceParameters(
            device_class=DeviceClass.AUTOMOTIVE,
            clock_jitter_percent_min=1.0,
            clock_jitter_percent_max=2.5,
            register_timing_jitter_ns_min=5.0,
            register_timing_jitter_ns_max=20.0,
            power_noise_percent_min=0.5,
            power_noise_percent_max=1.5,
            process_variation_percent_min=2.0,
            process_variation_percent_max=6.0,
            temp_min_c=-40.0,
            temp_max_c=150.0,
        ),
    }

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize the variance simulator.

        Args:
            seed: Random seed for reproducible variance generation
        """
        if seed is not None:
            random.seed(seed)

        self.generated_models: Dict[str, VarianceModel] = {}

    def generate_variance_model(
        self,
        device_id: str,
        device_class: DeviceClass = DeviceClass.CONSUMER,
        base_frequency_mhz: float = 100.0,
        custom_params: Optional[VarianceParameters] = None,
    ) -> VarianceModel:
        """
        Generate a variance model for a specific device.

        Args:
            device_id: Unique identifier for the device
            device_class: Class of device (affects variance ranges)
            base_frequency_mhz: Base operating frequency in MHz
            custom_params: Custom variance parameters (overrides defaults)

        Returns:
            VarianceModel with generated variance parameters
        """
        # Use custom parameters or defaults for device class
        params = custom_params or self.DEFAULT_VARIANCE_PARAMS[device_class]

        # Generate random variance values within specified ranges
        clock_jitter = random.uniform(
            params.clock_jitter_percent_min, params.clock_jitter_percent_max
        )

        register_timing_jitter = random.uniform(
            params.register_timing_jitter_ns_min, params.register_timing_jitter_ns_max
        )

        power_noise = random.uniform(
            params.power_noise_percent_min, params.power_noise_percent_max
        )

        temperature_drift = random.uniform(
            params.temperature_drift_ppm_per_c_min,
            params.temperature_drift_ppm_per_c_max,
        )

        process_variation = random.uniform(
            params.process_variation_percent_min, params.process_variation_percent_max
        )

        propagation_delay = random.uniform(
            params.propagation_delay_ps_min, params.propagation_delay_ps_max
        )

        # Generate operating conditions
        operating_temp = random.uniform(params.temp_min_c, params.temp_max_c)
        supply_voltage = 3.3 * (
            1.0
            + random.uniform(
                -params.voltage_variation_percent / 100.0,
                params.voltage_variation_percent / 100.0,
            )
        )

        model = VarianceModel(
            device_id=device_id,
            device_class=device_class,
            base_frequency_mhz=base_frequency_mhz,
            clock_jitter_percent=clock_jitter,
            register_timing_jitter_ns=register_timing_jitter,
            power_noise_percent=power_noise,
            temperature_drift_ppm_per_c=temperature_drift,
            process_variation_percent=process_variation,
            propagation_delay_ps=propagation_delay,
            operating_temp_c=operating_temp,
            supply_voltage_v=supply_voltage,
        )

        self.generated_models[device_id] = model
        return model

    def analyze_timing_patterns(
        self, timing_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze existing timing patterns to generate realistic variance.

        Args:
            timing_data: List of timing measurements from behavior profiling

        Returns:
            Dictionary containing variance analysis results
        """
        if not timing_data:
            return {"variance_detected": False, "recommendations": []}

        # Extract timing intervals
        intervals = []
        for data in timing_data:
            if "interval_us" in data:
                intervals.append(data["interval_us"])

        if not intervals:
            return {"variance_detected": False, "recommendations": []}

        # Statistical analysis
        mean_interval = statistics.mean(intervals)
        std_dev = statistics.stdev(intervals) if len(intervals) > 1 else 0.0
        coefficient_of_variation = std_dev / mean_interval if mean_interval > 0 else 0.0

        # Detect variance patterns
        variance_analysis = {
            "variance_detected": coefficient_of_variation > 0.05,  # 5% threshold
            "mean_interval_us": mean_interval,
            "std_deviation_us": std_dev,
            "coefficient_of_variation": coefficient_of_variation,
            "sample_count": len(intervals),
            "recommendations": [],
        }

        # Generate recommendations based on detected patterns
        if coefficient_of_variation > 0.2:
            variance_analysis["recommendations"].append(
                "High timing variance detected - consider consumer-grade device simulation"
            )
        elif coefficient_of_variation < 0.02:
            variance_analysis["recommendations"].append(
                "Low timing variance detected - consider enterprise-grade device simulation"
            )
        else:
            variance_analysis["recommendations"].append(
                "Moderate timing variance detected - standard simulation parameters appropriate"
            )

        return variance_analysis

    def apply_variance_to_timing(
        self,
        base_timing_ns: float,
        variance_model: VarianceModel,
        operation_type: str = "register_access",
    ) -> float:
        """
        Apply variance to a base timing value.

        Args:
            base_timing_ns: Base timing value in nanoseconds
            variance_model: Variance model to apply
            operation_type: Type of operation (affects variance application)

        Returns:
            Adjusted timing value with variance applied
        """
        adjustments = variance_model.timing_adjustments

        # Apply base timing factor
        adjusted_timing = base_timing_ns * adjustments["combined_timing_factor"]

        # Add operation-specific jitter
        if operation_type == "register_access":
            jitter = random.uniform(
                -adjustments["register_access_jitter_ns"],
                adjustments["register_access_jitter_ns"],
            )
            adjusted_timing += jitter
        elif operation_type == "clock_domain":
            jitter = random.uniform(-adjustments["jitter_ns"], adjustments["jitter_ns"])
            adjusted_timing += jitter

        # Ensure positive timing
        return max(0.1, adjusted_timing)

    def generate_systemverilog_timing_code(
        self,
        register_name: str,
        base_delay_cycles: int,
        variance_model: VarianceModel,
        offset: int,
    ) -> str:
        """
        Generate SystemVerilog code with variance-aware timing.

        Args:
            register_name: Name of the register
            base_delay_cycles: Base delay in clock cycles
            variance_model: Variance model to apply

        Returns:
            SystemVerilog code string with variance-aware timing
        """
        adjustments = variance_model.timing_adjustments

        # Calculate variance-adjusted delay cycles
        timing_factor = adjustments["combined_timing_factor"]
        jitter_cycles = int(
            adjustments["register_access_jitter_ns"] / 10.0
        )  # Assuming 100MHz clock

        adjusted_base_cycles = max(1, int(base_delay_cycles * timing_factor))
        max_jitter_cycles = max(1, jitter_cycles)

        # Generate variance-aware SystemVerilog code
        code = f"""
    // Variance-aware timing for {register_name}
    // Device class: {variance_model.device_class.value}
    // Base cycles: {base_delay_cycles}, Adjusted: {adjusted_base_cycles}
    // Jitter range: ±{max_jitter_cycles} cycles
    logic [{max(1, (adjusted_base_cycles + max_jitter_cycles).bit_length()-1)}:0] {register_name}_delay_counter = 0;
    logic [{max(1, max_jitter_cycles.bit_length()-1)}:0] {register_name}_jitter_lfsr = 1; // LFSR for jitter
    logic {register_name}_write_pending = 0;
    
    // LFSR for timing jitter generation
    always_ff @(posedge clk) begin
        if (!reset_n) begin
            {register_name}_jitter_lfsr <= 1;
        end else begin
            // Simple LFSR for pseudo-random jitter
            {register_name}_jitter_lfsr <= {{{register_name}_jitter_lfsr[{max_jitter_cycles.bit_length()-2}:0], 
                                            {register_name}_jitter_lfsr[{max_jitter_cycles.bit_length()-1}] ^ 
                                            {register_name}_jitter_lfsr[{max(0, max_jitter_cycles.bit_length()-3)}]}};
        end
    end
    
    // Variance-aware timing logic
    always_ff @(posedge clk) begin
        if (!reset_n) begin
            {register_name}_delay_counter <= 0;
            {register_name}_write_pending <= 0;
        end else if (bar_wr_en && bar_addr == 32'h{offset:08X}) begin
            {register_name}_write_pending <= 1;
            // Apply base delay with manufacturing variance
            {register_name}_delay_counter <= {adjusted_base_cycles} +
                                           ({register_name}_jitter_lfsr % {max_jitter_cycles + 1});
        end else if ({register_name}_write_pending && {register_name}_delay_counter > 0) begin
            {register_name}_delay_counter <= {register_name}_delay_counter - 1;
        end else if ({register_name}_write_pending && {register_name}_delay_counter == 0) begin
            {register_name}_reg <= bar_wr_data;
            {register_name}_write_pending <= 0;
        end
    end"""

        return code

    def get_variance_metadata(self, variance_model: VarianceModel) -> Dict[str, Any]:
        """
        Get metadata about the variance model for profiling integration.

        Args:
            variance_model: Variance model to extract metadata from

        Returns:
            Dictionary containing variance metadata
        """
        return {
            "device_id": variance_model.device_id,
            "device_class": variance_model.device_class.value,
            "variance_parameters": {
                "clock_jitter_percent": variance_model.clock_jitter_percent,
                "register_timing_jitter_ns": variance_model.register_timing_jitter_ns,
                "power_noise_percent": variance_model.power_noise_percent,
                "temperature_drift_ppm_per_c": variance_model.temperature_drift_ppm_per_c,
                "process_variation_percent": variance_model.process_variation_percent,
                "propagation_delay_ps": variance_model.propagation_delay_ps,
            },
            "operating_conditions": {
                "temperature_c": variance_model.operating_temp_c,
                "supply_voltage_v": variance_model.supply_voltage_v,
            },
            "timing_adjustments": variance_model.timing_adjustments,
        }
