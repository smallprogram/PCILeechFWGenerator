# PCILeech Firmware Generator

[![CI](https://github.com/ramseymcgrath/PCILeechFWGenerator/workflows/CI/badge.svg)](https://github.com/ramseymcgrath/PCILeechFWGenerator/actions)
[![codecov](https://codecov.io/gh/ramseymcgrath/PCILeechFWGenerator/branch/main/graph/badge.svg)](https://codecov.io/gh/ramseymcgrath/PCILeechFWGenerator)
![](https://dcbadge.limes.pink/api/shield/429866199833247744)

Generate authentic PCIe DMA firmware from real donor hardware with a single command. This tool extracts donor device configurations, builds personalized FPGA bitstreams, and optionally flashes your DMA card over USB-JTAG.

> [!WARNING]
> This tool requires real hardware and generates firmware containing actual device identifiers. It will not produce realistic firmware without a donor card.

## ✨ Key Features

- **Donor Hardware Analysis**: Extract real PCIe device configurations and register maps
- **Full 4KB Config-Space Shadow**: Complete configuration space emulation with overlay RAM
- **MSI-X Table Replication**: Exact replication of MSI-X tables from donor devices
- **Deterministic Variance Seeding**: Consistent hardware variance based on device serial number
- **Advanced SystemVerilog Generation**: Comprehensive PCIe device controller with modular architecture
- **Interactive TUI**: Modern text-based interface with real-time monitoring and guided workflows
- **Automated Build Pipeline**: Containerized synthesis and bitstream generation
- **USB-JTAG Flashing**: Direct firmware deployment to DMA boards

📚 **[Complete Documentation](../../wiki)** | 🏗️ **[Device Cloning Guide](../../wiki/device-cloning)** | 🔧 **[Development Setup](../../wiki/development)**

## 🚀 Quick Start

### Installation

```bash
# Install with TUI support (recommended)
pip install pcileechfwgenerator[tui]

# Install sudo wrapper scripts for easier usage
wget https://raw.githubusercontent.com/ramseymcgrath/PCILeechFWGenerator/refs/heads/main/install-sudo-wrapper.sh
./install-sudo-wrapper.sh

# Load required kernel modules
sudo modprobe vfio vfio-pci
```

### Requirements

- **Podman** (not Docker - required for proper PCIe device mounting)
- **Vivado Studio** (2022.2+ for synthesis and bitstream generation)
- **Python ≥ 3.9**
- **Donor PCIe card** (any inexpensive NIC, sound, or capture card)
- **DMA board** (pcileech_75t484_x1, pcileech_35t325_x4, or pcileech_100t484_x1)

### Basic Usage

```bash
# Interactive TUI (recommended for first-time users)
pcileech-tui-sudo

# CLI interface
pcileech-generate build

# Development from repository
git clone https://github.com/ramseymcgrath/PCILeechFWGenerator.git
cd PCILeechFWGenerator
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
sudo -E python3 generate.py
```

### Flashing Firmware

```bash
# Flash to DMA board
pcileech-generate flash output/firmware.bin --board pcileech_75t484_x1

# Or use usbloader directly
usbloader -f output/firmware.bin
```

> [!WARNING]
> Avoid using on-board devices (audio, graphics cards) as the VFIO process can lock the bus and cause system reboots.

## 🔧 Troubleshooting

### VFIO Setup Issues

The most common issues involve VFIO (Virtual Function I/O) configuration. Use the built-in diagnostic tool:

```bash
# Check VFIO setup and device compatibility
./vfio_setup_checker.py

# Check a specific device
./vfio_setup_checker.py 0000:03:00.0

# Interactive mode with guided fixes
./vfio_setup_checker.py --interactive

# Generate automated fix script
./vfio_setup_checker.py --generate-script
```

### Common VFIO Problems

**1. IOMMU not enabled in BIOS/UEFI**
```bash
# Enable VT-d (Intel) or AMD-Vi (AMD) in BIOS settings
# Then add to /etc/default/grub GRUB_CMDLINE_LINUX:
# For Intel: intel_iommu=on
# For AMD: amd_iommu=on
sudo update-grub && sudo reboot
```

**2. VFIO modules not loaded**
```bash
sudo modprobe vfio vfio_pci vfio_iommu_type1
```

**3. Device not in IOMMU group**
```bash
# Check IOMMU groups
find /sys/kernel/iommu_groups/ -name '*' -type l | grep YOUR_DEVICE_BDF
```

**4. Permission issues**
```bash
# Add user to required groups
sudo usermod -a -G vfio $USER
sudo usermod -a -G dialout $USER  # For USB-JTAG access
```

### Installation Issues

```bash
# If pip installation fails
pip install --upgrade pip setuptools wheel
pip install pcileechfwgenerator[tui]

# For TUI dependencies
pip install textual rich psutil watchdog

# Container issues
podman --version
podman info | grep rootless
```

### Getting Help

- **[GitHub Issues](https://github.com/ramseymcgrath/PCILeechFWGenerator/issues)**: Report bugs or request features
- **[GitHub Discussions](https://github.com/ramseymcgrath/PCILeechFWGenerator/discussions)**: Community support
- **[Wiki Documentation](../../wiki)**: Comprehensive guides and tutorials

## 📚 Documentation

For detailed information, please visit our **[Wiki](../../wiki)**:

- **[Device Cloning Process](../../wiki/device-cloning)** - Complete guide to the cloning workflow
- **[Firmware Uniqueness](../../wiki/firmware-uniqueness)** - How authenticity is achieved
- **[Manual Donor Dump](../../wiki/manual-donor-dump)** - Step-by-step manual extraction
- **[Development Setup](../../wiki/development)** - Contributing and development guide
- **[TUI Documentation](docs/TUI_README.md)** - Interactive interface guide

## 🧹 Cleanup & Safety

- **Rebind donors**: Use TUI/CLI to rebind donor devices to original drivers
- **Keep firmware private**: Generated firmware contains real device identifiers
- **Use isolated build environments**: Never build on production systems
- **Container cleanup**: `podman rmi pcileechfwgenerator:latest`

## 📄 License & Disclaimer

This project is licensed under the Apache License - see the [LICENSE](LICENSE) file for details.

> [!IMPORTANT]
> This tool is intended for educational research and legitimate PCIe development purposes only. Users are responsible for ensuring compliance with all applicable laws and regulations. The authors assume no liability for misuse of this software.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

- **[GitHub Issues](https://github.com/ramseymcgrath/PCILeechFWGenerator/issues)**: Report bugs or request features
- **[GitHub Discussions](https://github.com/ramseymcgrath/PCILeechFWGenerator/discussions)**: Community support

Systematic analysis of Base Address Registers determines memory layout:

```
For each BAR index (0-5):
├── Issue VFIO_DEVICE_GET_REGION_INFO ioctl
├── Extract: size, read/write permissions, mmap capability
├── Filter: Ignore I/O ports and zero-sized regions
├── Record: All valid MMIO BARs with metadata
└── Select: Largest MMIO BAR as primary window
```

**Advanced BAR Handling**:

- **64-bit BARs**: Properly handles paired 32-bit registers
- **Prefetchable Memory**: Preserves caching hints and optimization flags
- **Size Validation**: Ensures BAR sizes are power-of-2 aligned
- **Conflict Resolution**: Handles overlapping or invalid BAR configurations

**Fallback Mechanisms**:

- **Heuristic Sizing**: When VFIO fails, estimates BAR sizes from register patterns
- **Conservative Defaults**: Uses safe minimum sizes for critical BARs
- **Manual Override**: Allows explicit BAR configuration via command-line parameters

### Stage 4: Interrupt Architecture Analysis

The generator determines optimal interrupt emulation strategy:

#### Priority Order (Highest to Lowest)

1. **MSI-X**: Multi-vector message signaled interrupts
   - Validates table size > 0
   - Preserves vector count and table structure
   - Maps interrupt vectors to FPGA resources

2. **MSI**: Single-vector message signaled interrupts
   - Fallback when MSI-X unavailable
   - Simpler implementation with single interrupt line

3. **Legacy INTx**: Pin-based interrupts
   - Last resort for older devices
   - Emulates traditional interrupt sharing

**Capability Validation**:

- **Table Size Verification**: Ensures MSI-X table is properly sized
- **Vector Count Limits**: Respects hardware and software constraints
- **Interrupt Routing**: Validates interrupt pin assignments

### Stage 5: Template Context Generation

All extracted data is consolidated into a comprehensive template context:

#### Core Components

- **Device Identity**: Complete PCI configuration header
- **Memory Layout**: BAR map with sizes, types, and access patterns
- **Interrupt Configuration**: Selected interrupt mechanism with parameters
- **Timing Parameters**: Clock domains, reset sequences, power states
- **Feature Flags**: DMA capabilities, error handling, debug interfaces

#### Validation Pipeline

```
Context Validation:
├── Required Fields Check
│   ├── Non-zero Vendor ID
│   ├── Valid Device Class
│   └── Usable MMIO BAR present
├── Consistency Verification
│   ├── BAR size alignment
│   ├── Capability chain integrity
│   └── Interrupt configuration validity
└── Security Validation
    ├── Signature uniqueness
    ├── No default/generic patterns
    └── Sanitized vendor data
```

**Error Recovery**:

- **Missing BARs**: Provides synthetic minimal BAR configuration
- **Invalid Capabilities**: Gracefully degrades to simpler interrupt modes
- **Corrupted Data**: Attempts repair or fails with detailed diagnostics

### Stage 6: Firmware Generation

The validated context drives the Jinja2/SystemVerilog template engine:

#### Output Artifacts

- **FPGA Bitstream**: Device-specific `.bit` or `.bin` file
- **Configuration Headers**: C/C++ headers for host software integration
- **JSON Metadata**: Machine-readable device description
- **Build Reports**: Synthesis timing, resource utilization, verification results

#### Quality Assurance

- **Template Validation**: Ensures generated Verilog is syntactically correct
- **Resource Estimation**: Predicts FPGA utilization before synthesis
- **Timing Analysis**: Validates clock domain crossings and setup/hold times

### Quick Start Command

```bash
# Enable IOMMU and run generator
sudo python3 generate.py build --donor 0000:01:00.0 --board pcileech_35t325_x4
```

## Firmware Uniqueness and Authenticity

The generated firmware achieves hardware-level authenticity through comprehensive device replication while maintaining a stable, maintainable core architecture.

### Cloned Device Characteristics

#### Exact Hardware Replication

The firmware replicates every aspect visible to system software:

**Configuration Space Fidelity**:

- **Standard Header**: Complete 256-byte PCI configuration header
- **Extended Capabilities**: All capability blocks (MSI/MSI-X, PM, PCIe, vendor-specific)
- **Device Identity**: Vendor ID, Device ID, Subsystem IDs, Class Code, Revision
- **Memory Layout**: BAR sizes, types, prefetchability flags, alignment requirements
- **Power Management**: P-states, D-states, wake capabilities, power budgets

**Address Space Mapping**:

- **BAR Decode Logic**: Synthesized to match original device's address map exactly
- **Memory Apertures**: Identical size, alignment, and access characteristics
- **I/O Space**: Preserved for devices requiring port-based access
- **Configuration Registers**: Byte-perfect replica of all readable registers

**System Integration**:

- **Interrupt Behavior**: MSI/MSI-X vector counts, table structures, delivery modes
- **DMA Capabilities**: Address width, coherency domains, IOMMU compatibility
- **Error Handling**: AER capabilities, error injection, recovery mechanisms
- **Hot-plug Support**: Surprise removal, attention indicators, power control

#### Detection Resistance

The firmware is designed to be indistinguishable from original hardware:

**Software Compatibility**:

- **Driver Binding**: Original device drivers load and function normally
- **OS Recognition**: [`lspci`](README.md:365), Device Manager, and system profilers show identical information
- **Diagnostic Tools**: Hardware scanners, benchmarks, and validation suites pass
- **Security Software**: Anti-tampering and hardware verification systems satisfied

**Cryptographic Uniqueness**:

- **Bitstream Signatures**: Each donor produces a unique FPGA configuration
- **ROM Content Hashing**: Configuration data ripples through synthesis, changing timing
- **Build Fingerprints**: Compilation timestamps and tool versions embedded
- **Entropy Sources**: Hardware-specific variations preserved in generated logic

### Stable Core Architecture

While device-specific characteristics change, the underlying infrastructure remains consistent:

#### Generic Hardware Components

**Data Path Elements** (unchanged across builds):

- **AXI4/Avalon Bridges**: Standard bus protocol translation
- **DMA Engines**: Configurable scatter-gather, descriptor management
- **Memory Controllers**: FIFO management, buffer allocation, flow control
- **Clock Management**: PLL configuration, domain crossing, reset distribution

**Debug and Monitoring Infrastructure**:

- **UART Interface**: Serial console for runtime diagnostics
- **JTAG Access**: Boundary scan, internal signal probing
- **Performance Counters**: Bandwidth monitoring, error statistics, latency measurement
- **CSR Map**: Control and status register interface for configuration

**System Services**:

- **Error Detection**: Parity checking, ECC, protocol violation detection
- **Power Management**: Clock gating, voltage scaling, thermal monitoring
- **Security Features**: Access control, encryption engines, secure boot

#### Parameterized Design Benefits

**Predictable Characteristics**:

- **Timing Closure**: Consistent setup/hold margins across device types
- **Resource Utilization**: Stable LUT, BRAM, and DSP usage patterns
- **Power Consumption**: Predictable static and dynamic power profiles
- **Thermal Behavior**: Consistent heat generation and dissipation

**Maintainability Advantages**:

- **Code Reuse**: Core modules shared across all device types
- **Testing Strategy**: Common test benches and verification environments
- **Documentation**: Stable API and interface specifications
- **Debugging**: Familiar signal names and debug interfaces

**Performance Optimization**:

- **Pipeline Depth**: Optimized for target clock frequencies
- **Memory Bandwidth**: Efficient utilization of available FPGA memory
- **Latency Characteristics**: Predictable response times for critical operations
- **Throughput Scaling**: Linear performance scaling with resource allocation

### Security and Research Applications

The firmware's authenticity makes it suitable for advanced security research:

**Red Team Operations**:

- **Hardware Implants**: Undetectable device substitution
- **Supply Chain Testing**: Verification of hardware authenticity measures
- **Driver Exploitation**: Testing device driver security with controlled hardware
- **Firmware Analysis**: Safe environment for reverse engineering and vulnerability research

**Blue Team Defense**:

- **Detection Algorithm Development**: Training datasets for hardware anomaly detection
- **Forensic Analysis**: Understanding attacker techniques and signatures
- **Incident Response**: Controlled reproduction of hardware-based attacks
- **Security Validation**: Testing hardware security measures and countermeasures

**Academic Research**:

- **Hardware Security**: Novel attack and defense mechanism development
- **System Architecture**: PCIe protocol research and optimization
- **Performance Analysis**: Benchmarking and characterization studies
- **Verification Methods**: Formal verification of hardware designs

The combination of perfect device replication and stable core architecture provides researchers with a powerful platform that maintains authenticity while offering the flexibility and observability needed for advanced security research and development.

## ⚠️ Disclaimer

This tool is intended for educational research and legitimate PCIe development purposes only. Users are responsible for ensuring compliance with all applicable laws and regulations. The authors assume no liability for misuse of this software. The firmware generation is best effort and you should always validate it before use.

## 📦 Development & Contributing

For development setup instructions, please see [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

### Contributing

We welcome contributions! Please see [`CONTRIBUTING.md`](CONTRIBUTING.md) for detailed guidelines.

**Quick Start:**

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Run the test suite (`pytest`)
6. Commit your changes (`git commit -m 'feat: add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Release Process

For maintainers releasing new versions:

```bash
# Automated release (recommended)
python scripts/release.py minor --release-notes "Add new TUI features and improvements"

# Manual release
python -m build
twine upload dist/*

# Test package installation
pip install --index-url https://test.pypi.org/simple/ pcileechfwgenerator[tui]
```

## 📚 Documentation

- **[Build System Architecture](docs/BUILD_SYSTEM_ARCHITECTURE.md)**: Entry points, build flow, and troubleshooting guide
- **[TUI Documentation](docs/TUI_README.md)**: Detailed TUI interface guide
- **[Manual Donor Dump Guide](docs/MANUAL_DONOR_DUMP.md)**: Step-by-step guide for manually generating donor dumps
- **[Contributing Guide](CONTRIBUTING.md)**: Development and contribution guidelines
- **[Changelog](CHANGELOG.md)**: Version history and release notes

## 🔧 Troubleshooting

### Common Issues

**Installation Problems:**
```bash
# If pip installation fails
pip install --upgrade pip setuptools wheel
pip install pcileechfwgenerator[tui]

# For development installation issues
pip install -e .[dev]
```

**TUI Not Starting:**

```bash
# Check TUI dependencies
python -c "import textual; print('TUI dependencies OK')"

# Install TUI dependencies manually
pip install textual rich psutil watchdog

# Try using the sudo wrapper
pcileech-tui-sudo

# Or run with preserved environment
sudo -E pcileech-tui
```

**Permission Issues:**

```bash
# Ensure proper permissions for PCIe operations
sudo usermod -a -G vfio $USER
sudo usermod -a -G dialout $USER  # For USB-JTAG access

# Load required kernel modules
sudo modprobe vfio
sudo modprobe vfio-pci
```

**Command Not Found:**

```bash
# If pcileech-* commands are not found after pip install
pip install --force-reinstall pcileechfwgenerator[tui]

# Or use the sudo wrappers
./install-sudo-wrapper.sh
pcileech-tui-sudo
```

**Container Issues:**

```bash
# Check Podman installation
podman --version

# Verify rootless setup
podman info | grep rootless

# Build container manually
podman build -t pcileechfwgenerator:latest -f Containerfile .

# Test container dependencies
podman run --rm pcileechfwgenerator:latest python3 -c "import psutil, pydantic; print('Dependencies OK')"

# Check container file structure
podman run --rm pcileechfwgenerator:latest ls -la /app/

# Test with required capabilities
podman run --rm --cap-add=SYS_RAWIO --cap-add=SYS_ADMIN pcileechfwgenerator:latest echo "Capability test passed"

# Debug container build issues
podman run --rm -it pcileechfwgenerator:latest /bin/bash
```

**Donor Dump Issues:**

```bash
# If donor_dump module fails to build or load
# See the Manual Donor Dump Guide for step-by-step instructions:
# docs/MANUAL_DONOR_DUMP.md

# Build the kernel module manually
cd src/donor_dump
make clean && make

# Load the module manually (replace BDF with your device)
sudo insmod donor_dump.ko bdf=0000:03:00.0
cat /proc/donor_dump > donor_info.txt
sudo rmmod donor_dump

# Check kernel module dependencies
modinfo src/donor_dump/donor_dump.ko
```

### Getting Help

- **GitHub Issues**: [Report bugs or request features](https://github.com/ramseymcgrath/PCILeechFWGenerator/issues)
- **GitHub Discussions**: [Community support](https://github.com/ramseymcgrath/PCILeechFWGenerator/discussions)
- **Documentation**: Check the docs/ directory for detailed guides

## 🏆 Acknowledgments

- **Xilinx/AMD**: For Vivado synthesis tools
- **Textual**: For the modern TUI framework
- **PCILeech Community**: For feedback and contributions

## 📄 License

This project is licensed under the Apache License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Legal Notice

*AGAIN* This tool is intended for educational research and legitimate PCIe development purposes only. Users are responsible for ensuring compliance with all applicable laws and regulations. The authors assume no liability for misuse of this software.

**Security Considerations:**

- Never build firmware on systems used for production or sensitive operations
- Use isolated build environments (Seperate dedicated hardware)
- Keep generated firmware private and secure
- Follow responsible disclosure practices for any security research
- Use the SECURITY.md template to raise security concerns

---
