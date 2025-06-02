# DMA Firmware Generator

Generate spoofed PCIe DMA firmware from real donor hardware with a single command. The workflow rips the donor's configuration space, builds a personalized FPGA bit‑stream in an isolated container, and (optionally) flashes your DMA card over USB‑JTAG.

## Features

- **Donor Hardware Analysis**: Extract real PCIe device configurations and register maps
- **Behavioral Profiling**: Capture dynamic device behavior patterns for enhanced realism
- **Manufacturing Variance Simulation**: Add realistic timing jitter and parameter variations
- **Advanced SystemVerilog Generation**: Comprehensive PCIe device controller with modular architecture
- **Automated Build Pipeline**: Containerized synthesis and bit-stream generation
- **USB-JTAG Flashing**: Direct firmware deployment to DMA boards

## 1. Requirements

### 1.1 Software

| Tool | Why you need it | Install |
|------|----------------|---------|
| Vivado Studio | Synthesis & bit‑stream generation | Download from Xilinx (any 2022.2+ release) |
| Podman | Rootless container runtime for the build sandbox | See [`install.sh`](install.sh) in this repo |
| Python ≥ 3.9 | Host‑side orchestrator ([`generate.py`](generate.py)) | Distro package (python3) |
| λConcept usbloader | USB flashing utility for Screamer‑class boards | Installed by [`install.sh`](install.sh) |
| pciutils, usbutils | lspci / lsusb helpers | Installed by [`install.sh`](install.sh) |

> **⚠️ Heads‑up**  
> Never build firmware on the same operating system you plan to run the attack from. Use a separate Linux box or VM.

### 1.2 Hardware

| Component | Notes |
|-----------|-------|
| Donor PCIe card | Any inexpensive NIC, sound, or capture card works. One donor → one firmware. Destroy or quarantine the donor after extraction. |
| DMA board | Supported Artix‑7 DMA boards (35T, 75T, 100T). Must expose the Screamer USB‑JTAG port. |

## 2. Setup (one‑time)

```bash
sudo ./install.sh        # grabs Podman, usbloader, Python, etc.
```

Re‑login or run `newgrp` afterwards so rootless Podman picks up subuid/subgid mappings.

## 3. Firmware Generation

1. Insert donor card (and optionally the DMA card) into your Linux build box.

2. Boot Linux and ensure the donor loads its vendor driver (the more registers, the better!).

3. Clone this repo and run the generator:

```bash
git clone https://github.com/ramseymcgrath/PCILeechFWGenerator
cd PCILeechFWGenerator

# Basic generation
sudo python3 generate.py              # interactive – pick the donor device

# Advanced generation with enhanced features
python3 src/build.py --bdf 0000:03:00.0 --board 75t --advanced-sv

# Device-specific generation with behavior profiling
python3 src/build.py --bdf 0000:03:00.0 --board 75t --advanced-sv \
  --device-type network --enable-behavior-profiling

# Selective feature control
python3 src/build.py --bdf 0000:03:00.0 --board 75t --advanced-sv \
  --disable-power-management --disable-performance-counters
```

**Output:** `output/firmware.bin` (FPGA bit‑stream ready for flashing).

## 4. Flashing the DMA Board

> **Note:** These steps can run on the same machine or a different PC.

1. Power down, install the DMA card, and remove the donor.

2. Connect the USB‑JTAG port.

3. Flash:

```bash
usbloader -f output/firmware.bin      # auto‑detects Screamer VID:PID 1d50:6130
```

If multiple λConcept boards are attached, add `--vidpid <vid:pid>`.

## 5. Advanced Features

### 5.1 Manufacturing Variance Simulation

The Manufacturing Variance Simulation feature adds realistic hardware variations to make generated firmware more authentic and harder to detect. This feature models real-world manufacturing tolerances and environmental conditions.

**Key Capabilities:**
- **Device Class Support**: Consumer, Enterprise, Industrial, and Automotive grade components with appropriate variance characteristics
- **Timing Variations**: Clock jitter, register access timing, and propagation delays
- **Environmental Modeling**: Temperature drift, power supply noise, and process variations
- **Integration**: Seamlessly integrates with behavior profiling for enhanced realism

**Device Classes:**
- `CONSUMER`: Standard consumer-grade tolerances (2-5% clock jitter)
- `ENTERPRISE`: Tighter enterprise-grade specifications (1-3% variations)
- `INDUSTRIAL`: Extended temperature and reliability ranges
- `AUTOMOTIVE`: Automotive-grade specifications with enhanced stability

**Usage:**
```bash
# Enable manufacturing variance (automatically applied with --advanced-sv)
python3 src/build.py --bdf 0000:03:00.0 --board 75t --advanced-sv
```

### 5.2 Advanced SystemVerilog Generation

The Advanced SystemVerilog Generation feature provides a comprehensive, modular PCIe device controller with enterprise-grade capabilities and optimizations.

**Architecture Components:**
- **Modular Design**: Specialized components for power, error handling, and performance monitoring
- **Multiple Clock Domains**: Proper clock domain crossing with variance-aware timing
- **Device-Specific Logic**: Optimizations for Network, Storage, Graphics, and Audio devices
- **Comprehensive Integration**: All components work together seamlessly

**Power Management Features:**
- **PCIe Power States**: Full D0, D1, D2, D3hot, D3cold state support
- **ASPM (Active State Power Management)**: L0s, L1, L1.1, L1.2 link states
- **Dynamic Power Scaling**: Frequency and voltage scaling based on workload
- **Wake-on-LAN/Event**: Configurable wake event handling

**Error Handling & Recovery:**
- **Comprehensive Error Detection**: Correctable and uncorrectable error handling
- **Advanced Error Reporting (AER)**: Full PCIe AER implementation
- **Recovery Mechanisms**: Automatic error recovery and link retraining
- **Error Logging**: Detailed error tracking and reporting

**Performance Monitoring:**
- **Hardware Counters**: Transaction, bandwidth, and latency monitoring
- **Device-Specific Metrics**: Tailored counters for different device types
- **Real-time Monitoring**: Live performance data collection
- **Threshold-based Alerts**: Configurable performance thresholds

**Device-Specific Optimizations:**
- **Network Devices**: Multi-queue support, interrupt coalescing, checksum offload
- **Storage Devices**: Command queuing, wear leveling, power loss protection
- **Graphics Devices**: Memory bandwidth optimization, display timing
- **Audio Devices**: Low-latency processing, sample rate conversion

**Usage Examples:**
```bash
# Enable all advanced features
python3 src/build.py --bdf 0000:03:00.0 --board 75t --advanced-sv

# Network device with specific optimizations
python3 src/build.py --bdf 0000:03:00.0 --board 75t --advanced-sv --device-type network

# Disable specific features for minimal implementation
python3 src/build.py --bdf 0000:03:00.0 --board 75t --advanced-sv \
  --disable-power-management --disable-error-handling

# Storage device with performance monitoring
python3 src/build.py --bdf 0000:03:00.0 --board 75t --advanced-sv \
  --device-type storage --enable-behavior-profiling
```

### 5.3 Behavioral Profiling

Dynamic behavior profiling captures real device operation patterns to enhance firmware realism.

**Capabilities:**
- **Real-time Monitoring**: Captures live device register access patterns
- **Pattern Analysis**: Identifies behavioral signatures and timing characteristics
- **Integration**: Enhances register definitions with behavioral data
- **Configurable Duration**: Adjustable profiling periods (default: 10 seconds)

**Usage:**
```bash
# Enable behavior profiling with custom duration
python3 src/build.py --bdf 0000:03:00.0 --board 75t \
  --enable-behavior-profiling --profile-duration 30.0
```

### 5.4 Command-Line Options

**Core Options:**
- `--bdf`: PCIe Bus:Device.Function identifier (required)
- `--board`: Target board type (35t, 75t, 100t) (required)

**Advanced Features:**
- `--advanced-sv`: Enable advanced SystemVerilog generation
- `--device-type`: Specify device type (generic, network, storage, graphics, audio)
- `--enable-behavior-profiling`: Enable dynamic behavior profiling
- `--profile-duration`: Profiling duration in seconds (default: 10.0)

**Feature Control:**
- `--disable-power-management`: Disable power management features
- `--disable-error-handling`: Disable error handling features
- `--disable-performance-counters`: Disable performance monitoring

**Analysis & Debugging:**
- `--save-analysis`: Save detailed analysis to specified file
- `--verbose`: Enable verbose output
- `--enhanced-timing`: Enable enhanced timing models (default: enabled)

## 6. Cleanup & Safety

- Rebind the donor back to its original driver if you keep it around.
- Keep the generated firmware private; it contains identifiers from the donor.
- Advanced features require appropriate privileges for hardware access.

## 7. Disclaimer

For educational research and legitimate PCIe development only. Misuse may violate laws and void warranties. The authors assume no liability.