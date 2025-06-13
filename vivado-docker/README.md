# Vivado Container for PCILeech Firmware Generator

This directory contains the setup for building a containerized version of the PCILeech Firmware Generator that includes Xilinx Vivado for complete FPGA build flows.

## Overview

The Vivado container provides a self-contained environment for:
- Complete PCILeech DMA firmware generation
- FPGA synthesis, implementation, and bitstream generation
- Advanced SystemVerilog features with Vivado integration
- Reproducible builds across different systems

## Prerequisites

### 1. Download Vivado Installer

Download the Vivado Linux installer from Xilinx:
- Visit: https://www.xilinx.com/support/download.html
- Download the **Linux** version (e.g., `Xilinx_Vivado_SDK_Web_2025.1_0610_1_Lin64.bin`)
- Place the installer file in this `vivado-docker/` directory

**Supported Vivado Versions:**
- 2025.1 (default)
- 2024.2
- 2024.1
- 2023.2

### 2. License Requirements

You need either:
- **License file**: A valid Xilinx license file (`.lic`)
- **Network license**: Access to a Xilinx license server

### 3. System Requirements

- **Disk Space**: ~30GB free space for building
- **Memory**: 8GB+ RAM recommended
- **Container Engine**: Podman or Docker

## Quick Start

### 1. Prepare Files

```bash
cd vivado-docker/

# Place your Vivado installer here
# Example: Xilinx_Vivado_SDK_Web_2025.1_0610_1_Lin64.bin

# Verify the installer is present
ls -la *.bin
```

### 2. Build Container

```bash
# Build with default settings (Vivado 2025.1)
./build_vivado_container.sh

# Build specific version
./build_vivado_container.sh --vivado-version 2024.2

# Build and test
./build_vivado_container.sh --test
```

### 3. Run Container

#### With License File

```bash
podman run --rm -it \
  -v /path/to/your/project:/workspace \
  -v /path/to/your/license.lic:/licenses/Xilinx.lic \
  -e XILINX_LICENSE_FILE=/licenses/Xilinx.lic \
  pcileech-vivado:2025.1 --help
```

#### With Network License Server

```bash
podman run --rm -it \
  -v /path/to/your/project:/workspace \
  -e XILINX_LICENSE_FILE=27000@your-license-server \
  pcileech-vivado:2025.1 --help
```

## Usage Examples

### Build PCILeech Firmware with Vivado

```bash
# Basic firmware build
podman run --rm -it \
  --cap-add=SYS_RAWIO --cap-add=SYS_ADMIN \
  --device=/dev/vfio/GROUP --device=/dev/vfio/vfio \
  -v ./output:/app/output \
  -v /path/to/license.lic:/licenses/Xilinx.lic \
  -e XILINX_LICENSE_FILE=/licenses/Xilinx.lic \
  pcileech-vivado:2025.1 \
  build-firmware --bdf 0000:03:00.0 --board 75t

# Advanced SystemVerilog with Vivado synthesis
podman run --rm -it \
  --cap-add=SYS_RAWIO --cap-add=SYS_ADMIN \
  --device=/dev/vfio/GROUP --device=/dev/vfio/vfio \
  -v ./output:/app/output \
  -v /path/to/license.lic:/licenses/Xilinx.lic \
  -e XILINX_LICENSE_FILE=/licenses/Xilinx.lic \
  pcileech-vivado:2025.1 \
  build-firmware --bdf 0000:03:00.0 --board 75t --advanced-sv --use-vivado
```

### Run Vivado Directly

```bash
# Check Vivado version
podman run --rm \
  -e XILINX_LICENSE_FILE=/licenses/Xilinx.lic \
  -v /path/to/license.lic:/licenses/Xilinx.lic \
  pcileech-vivado:2025.1 \
  vivado -version

# Run Vivado in batch mode with TCL script
podman run --rm -it \
  -v /path/to/project:/workspace \
  -v /path/to/license.lic:/licenses/Xilinx.lic \
  -e XILINX_LICENSE_FILE=/licenses/Xilinx.lic \
  pcileech-vivado:2025.1 \
  vivado -mode batch -source build.tcl

# Interactive shell with Vivado environment
podman run --rm -it \
  -v /path/to/project:/workspace \
  -v /path/to/license.lic:/licenses/Xilinx.lic \
  -e XILINX_LICENSE_FILE=/licenses/Xilinx.lic \
  pcileech-vivado:2025.1 \
  bash
```

### GUI Mode (with X11 forwarding)

```bash
# Enable X11 forwarding for Vivado GUI
xhost +local:docker
podman run --rm -it \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /path/to/project:/workspace \
  -v /path/to/license.lic:/licenses/Xilinx.lic \
  -e XILINX_LICENSE_FILE=/licenses/Xilinx.lic \
  pcileech-vivado:2025.1 \
  vivado -gui
```

## Build Script Options

The [`build_vivado_container.sh`](build_vivado_container.sh) script supports several options:

```bash
./build_vivado_container.sh [OPTIONS]

Options:
  --vivado-version VER    Vivado version to build (default: 2025.1)
  --test                  Run tests after building
  --push                  Push image to registry after building
  --tag TAG               Use custom tag
  --container-engine ENG  Specify container engine (podman or docker)
  --help, -h              Show help message

Examples:
  ./build_vivado_container.sh                                    # Default build
  ./build_vivado_container.sh --vivado-version 2024.2 --test    # Specific version
  ./build_vivado_container.sh --tag myregistry/pcileech-vivado:latest --push
```

## Container Commands

The container supports several commands:

- `build-firmware [args]` - Build PCILeech firmware with Vivado
- `vivado [args]` - Run Vivado with arguments
- `bash` - Interactive shell
- `--help` - Show help information

## Environment Variables

- `XILINX_LICENSE_FILE` - License file path or server (required)
- `VIVADO_VER` - Vivado version (set during build)
- `XILINX_VIVADO` - Vivado installation path

## File Structure

```
vivado-docker/
├── Containerfile.vivado          # Container definition
├── entrypoint-vivado.sh          # Container entrypoint script
├── build_vivado_container.sh     # Build script
├── .dockerignore                 # Files to ignore during build
├── README.md                     # This file
└── Xilinx_Vivado_*.bin          # Vivado installer (user provided)
```

## Troubleshooting

### Build Issues

**Problem**: "Vivado installer not found"
```bash
# Solution: Ensure installer is in vivado-docker/ directory
ls -la vivado-docker/*.bin
```

**Problem**: "Low disk space warning"
```bash
# Solution: Free up space or use different build location
df -h .
```

**Problem**: "Container build failed during Vivado installation"
```bash
# Solution: Check installer integrity and try again
md5sum Xilinx_Vivado_*.bin
```

### Runtime Issues

**Problem**: "License file not found"
```bash
# Solution: Verify license file mount
podman run --rm -v /path/to/license.lic:/licenses/Xilinx.lic pcileech-vivado:2025.1 ls -la /licenses/
```

**Problem**: "Vivado command not found"
```bash
# Solution: Check Vivado installation in container
podman run --rm pcileech-vivado:2025.1 which vivado
```

**Problem**: "Permission denied for PCI devices"
```bash
# Solution: Add required capabilities and devices
podman run --cap-add=SYS_RAWIO --cap-add=SYS_ADMIN --device=/dev/vfio/vfio ...
```

### License Issues

**Problem**: "License checkout failed"
```bash
# Solution: Verify license server connectivity or file validity
podman run --rm -e XILINX_LICENSE_FILE=27000@server pcileech-vivado:2025.1 vivado -version
```

## Performance Notes

- **Build Time**: 30-60 minutes depending on system
- **Image Size**: ~25GB final image
- **Memory Usage**: 4-8GB during Vivado operations
- **CPU Usage**: Multi-core recommended for synthesis

## Security Considerations

- Container runs as non-root user by default
- Privileged access required only for PCI device operations
- License files should be mounted read-only
- Use specific capabilities instead of `--privileged` when possible

## Integration with PCILeech

The Vivado container integrates seamlessly with the PCILeech build system:

1. **Automatic Detection**: The build system detects Vivado in the container
2. **License Handling**: Automatic license setup and validation
3. **Build Integration**: Native support for `--use-vivado` flag
4. **Output Management**: Results saved to mounted output directory

## Support

For issues specific to:
- **Container build**: Check this README and build script logs
- **Vivado installation**: Consult Xilinx documentation
- **PCILeech integration**: See main project documentation
- **Licensing**: Contact Xilinx support

## License

This container setup is provided under the same license as the main PCILeech Firmware Generator project. Vivado itself requires a separate license from Xilinx.