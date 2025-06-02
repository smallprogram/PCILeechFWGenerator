# Quick Start Guide

Get up and running with PCILeech Firmware Generator in minutes.

## 🚀 Installation

### Option 1: pip Installation (Recommended)

```bash
# Install with TUI support
pip install pcileech-fw-generator[tui]

# Verify installation
pcileech-tui --help
```

### Option 2: From Source

```bash
git clone https://github.com/ramseymcgrath/PCILeechFWGenerator
cd PCILeechFWGenerator
pip install -e .[tui]
```

## 🎯 First Run

### 1. System Setup

```bash
# Install system dependencies (one-time setup)
sudo ./install.sh

# Re-login or run newgrp for Podman permissions
newgrp
```

### 2. Hardware Setup

1. **Insert donor PCIe card** into your Linux build system
2. **Boot Linux** and ensure the donor loads its vendor driver
3. **Connect DMA board** (optional, for direct flashing)

### 3. Generate Firmware

#### Interactive TUI (Recommended)

```bash
sudo pcileech-tui
```

The TUI will guide you through:
- 🔍 **Device Discovery**: Automatically detect PCIe devices
- ⚙️ **Configuration**: Set board type and options
- 🏗️ **Build Process**: Monitor real-time progress
- 📦 **Output**: Get your firmware.bin file

#### Command Line

```bash
# Interactive device selection
sudo pcileech-generate

# Direct build (if you know the device BDF)
sudo pcileech-build --bdf 0000:03:00.0 --board 75t
```

## 📋 Common Workflows

### Basic Firmware Generation

```bash
# 1. Launch TUI
sudo pcileech-tui

# 2. Select your donor device from the list
# 3. Choose board type (35t, 75t, 100t)
# 4. Click "Start Build"
# 5. Wait for completion
# 6. Find firmware in output/firmware.bin
```

### Advanced Features

```bash
# Enable all advanced features
sudo pcileech-build --bdf 0000:03:00.0 --board 75t --advanced-sv

# Network device with behavior profiling
sudo pcileech-build --bdf 0000:03:00.0 --board 75t --advanced-sv \
  --device-type network --enable-behavior-profiling

# Custom profiling duration
sudo pcileech-build --bdf 0000:03:00.0 --board 75t \
  --enable-behavior-profiling --profile-duration 30.0
```

### Flashing DMA Board

```bash
# Flash the generated firmware
usbloader -f output/firmware.bin

# For multiple boards, specify VID:PID
usbloader -f output/firmware.bin --vidpid 1d50:6130
```

## 🔧 Troubleshooting

### Permission Issues

```bash
# Add user to required groups
sudo usermod -a -G vfio $USER
sudo usermod -a -G dialout $USER

# Re-login or use newgrp
newgrp vfio
```

### TUI Not Starting

```bash
# Check TUI dependencies
python -c "import textual; print('TUI OK')"

# Install missing dependencies
pip install textual rich psutil watchdog
```

### Container Issues

```bash
# Check Podman
podman --version
podman info | grep rootless

# If issues, reinstall Podman
sudo ./install.sh
```

### Device Not Found

```bash
# List PCIe devices
lspci -nn

# Check if device is bound to vfio-pci
lspci -k -s 0000:03:00.0

# Manually bind to vfio-pci if needed
echo "0000:03:00.0" | sudo tee /sys/bus/pci/drivers/vfio-pci/bind
```

## 📚 Next Steps

- **[TUI Documentation](TUI_README.md)**: Detailed TUI interface guide
- **[Advanced Features](../README.md#advanced-features)**: Power user features
- **[Contributing](../CONTRIBUTING.md)**: Help improve the project
- **[Troubleshooting](../README.md#troubleshooting)**: Detailed problem solving

## 🆘 Getting Help

- **GitHub Issues**: [Report problems](https://github.com/ramseymcgrath/PCILeechFWGenerator/issues)
- **Discussions**: [Ask questions](https://github.com/ramseymcgrath/PCILeechFWGenerator/discussions)
- **Documentation**: Check the docs/ directory

## ⚠️ Important Notes

- **Security**: Never build on the same system you'll use for attacks
- **Privacy**: Keep generated firmware private (contains donor identifiers)
- **Legal**: Use only for educational research and legitimate development
- **Hardware**: Donor card should be quarantined after extraction

---

**Happy firmware generating!** 🎉