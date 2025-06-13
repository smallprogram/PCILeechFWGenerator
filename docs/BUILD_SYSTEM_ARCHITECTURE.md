# Build System Architecture

This document explains the PCILeech Firmware Generator's build system architecture and the correct entry points to use.

## Overview

The PCILeech Firmware Generator uses a multi-layered architecture with different entry points for different use cases:

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface Layer                     │
├─────────────────────────────────────────────────────────────┤
│  pcileech-tui        │  pcileech-generate  │  generate.py   │
│  (Interactive TUI)   │  (CLI orchestrator) │  (Direct CLI)  │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                   Orchestration Layer                      │
├─────────────────────────────────────────────────────────────┤
│                     generate.py                            │
│  • Device enumeration and selection                        │
│  • Driver rebinding (vfio-pci)                            │
│  • Container orchestration                                 │
│  • Firmware flashing (optional)                           │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                   Container Layer                          │
├─────────────────────────────────────────────────────────────┤
│                   Podman/Docker                            │
│  • Isolated build environment                             │
│  • Vivado synthesis tools                                 │
│  • SystemVerilog generation                               │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Build Layer                             │
├─────────────────────────────────────────────────────────────┤
│                    build.py                                │
│  • Donor device analysis                                  │
│  • SystemVerilog code generation                          │
│  • TCL script generation                                  │
│  • Bitstream synthesis                                    │
└─────────────────────────────────────────────────────────────┘
```

## Entry Points

### 1. Primary Entry Points (Recommended)

#### [`generate.py`](../generate.py) - Main Orchestrator
- **Purpose**: Complete firmware generation workflow
- **Capabilities**:
  - PCIe device enumeration and selection
  - Driver rebinding to vfio-pci
  - Container orchestration (Podman/Docker)
  - Firmware flashing via USB-JTAG
  - Error handling and cleanup
- **Usage**:
  ```bash
  # Interactive device selection
  sudo python3 generate.py
  
  # Direct device specification
  sudo python3 generate.py --bdf 0000:03:00.0 --board 75t
  
  # With advanced features
  sudo python3 generate.py --bdf 0000:03:00.0 --board 75t --advanced-sv --enable-variance
  ```

#### [`pcileech-generate`](../pyproject.toml#L78) - CLI Command
- **Purpose**: Packaged version of generate.py
- **Installation**: `pip install pcileechfwgenerator`
- **Usage**:
  ```bash
  # Same functionality as generate.py
  sudo pcileech-generate --bdf 0000:03:00.0 --board 75t
  ```

#### [`pcileech-tui`](../pyproject.toml#L79) - Interactive TUI
- **Purpose**: Text-based user interface
- **Features**: Real-time monitoring, guided workflows, device indicators
- **Usage**:
  ```bash
  sudo pcileech-tui
  # OR with sudo wrapper
  pcileech-tui-sudo
  ```

### 2. Wrapper Scripts

#### [`pcileech-build-sudo`](../pcileech-build-sudo) - Sudo Wrapper
- **Purpose**: Preserve Python paths when running with sudo
- **Implementation**: Calls `pcileech-generate` with preserved environment
- **Usage**:
  ```bash
  # Equivalent to: sudo pcileech-generate --bdf 0000:03:00.0 --board 75t
  pcileech-build-sudo --bdf 0000:03:00.0 --board 75t
  ```

#### [`pcileech-tui-sudo`](../pcileech-tui-sudo) - TUI Sudo Wrapper
- **Purpose**: Preserve Python paths for TUI
- **Usage**:
  ```bash
  pcileech-tui-sudo
  ```

### 3. Internal Components (Not for Direct Use)

#### [`src/build.py`](../src/build.py) - Modular Build System
- **Purpose**: Container-internal firmware generation
- **Status**: ⚠️ **Incomplete** - Missing `build.controller` module
- **Note**: This is called automatically by the container, not directly by users

#### [`src/build_cli.py`](../src/build_cli.py) - Build CLI Entry Point
- **Purpose**: Entry point for `pcileech-build` command
- **Status**: ⚠️ **Broken** - Tries to import non-existent `build.controller`
- **Note**: Use `pcileech-generate` instead

## Migration Guide

### From Broken Commands

If you were using these **broken** commands:

```bash
# ❌ BROKEN - tries to import non-existent build.controller
pcileech-build --bdf 0000:03:00.0 --board 75t
sudo pcileech-build --bdf 0000:03:00.0 --board 75t
```

**Migrate to these working commands:**

```bash
# ✅ WORKING - proper orchestrator
pcileech-generate --bdf 0000:03:00.0 --board 75t
sudo pcileech-generate --bdf 0000:03:00.0 --board 75t

# ✅ WORKING - sudo wrapper (preserves Python paths)
pcileech-build-sudo --bdf 0000:03:00.0 --board 75t
```

### From Direct Scripts

If you were calling scripts directly:

```bash
# ✅ Still works - direct orchestrator
sudo python3 generate.py --bdf 0000:03:00.0 --board 75t

# ✅ Recommended - packaged command
sudo pcileech-generate --bdf 0000:03:00.0 --board 75t
```

## Build Process Flow

1. **Device Selection**: [`generate.py`](../generate.py) enumerates PCIe devices
2. **Driver Binding**: Rebinds donor device to vfio-pci driver
3. **Container Launch**: Starts Podman/Docker container with build environment
4. **Firmware Generation**: Container runs [`build.py`](../src/build.py) internally
5. **Output Collection**: Bitstream files are copied to host
6. **Optional Flashing**: Firmware can be flashed via USB-JTAG
7. **Cleanup**: Original drivers are restored

## Troubleshooting

### "Could not import build module" Error

This error occurs when using the broken `pcileech-build` command:

```bash
# ❌ This will fail
pcileech-build --bdf 0000:03:00.0 --board 75t
# Error: Could not import build module.
```

**Solution**: Use the proper orchestrator:

```bash
# ✅ Use this instead
pcileech-generate --bdf 0000:03:00.0 --board 75t
# OR
pcileech-build-sudo --bdf 0000:03:00.0 --board 75t
```

### Python Path Issues with Sudo

When running with sudo, Python may not find installed packages:

```bash
# ❌ May have import issues
sudo pcileech-generate --bdf 0000:03:00.0 --board 75t
```

**Solution**: Use the sudo wrapper:

```bash
# ✅ Preserves Python paths
pcileech-build-sudo --bdf 0000:03:00.0 --board 75t
```

### Missing Container Image

If you get "Container image 'dma-fw' not found":

```bash
# Build the container image
sudo podman build -t dma-fw .
# OR
sudo docker build -t dma-fw .
```

## Summary

- **Use [`generate.py`](../generate.py) or [`pcileech-generate`](../pyproject.toml#L78)** for firmware generation
- **Use [`pcileech-tui`](../pyproject.toml#L79)** for interactive workflows
- **Use sudo wrappers** ([`pcileech-build-sudo`](../pcileech-build-sudo), [`pcileech-tui-sudo`](../pcileech-tui-sudo)) to preserve Python paths
- **Avoid [`pcileech-build`](../pyproject.toml#L80)** - it's broken and tries to import non-existent modules
- **Don't call [`src/build.py`](../src/build.py) directly** - it's designed to run inside containers

The modular build system referenced in [`src/build.py`](../src/build.py) is incomplete and missing the `build.controller` module. The [`generate.py`](../generate.py) script is the proper, complete orchestrator that handles the entire firmware generation workflow.