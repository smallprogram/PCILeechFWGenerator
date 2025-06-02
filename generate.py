#!/usr/bin/env python3
"""
Host-side orchestrator for DMA firmware generation.

This script:
• Enumerates PCIe devices
• Allows user to select a donor device
• Re-binds donor to vfio-pci driver
• Launches Podman container (image: dma-fw) that runs build.py
• Optionally flashes output/firmware.bin with usbloader
• Restores original driver afterwards

Requires root privileges (sudo) for driver rebinding and VFIO operations.
"""

import argparse
import logging
import os
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap
import time
from typing import Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("generate.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)


def validate_bdf_format(bdf: str) -> bool:
    """
    Validate BDF (Bus:Device.Function) format.
    Expected format: DDDD:BB:DD.F where D=hex digit, B=hex digit, F=0-7
    Example: 0000:03:00.0
    """
    bdf_pattern = re.compile(r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]$")
    return bool(bdf_pattern.match(bdf))


def run_command(cmd: str, **kwargs) -> str:
    """Execute a shell command and return stripped output."""
    return subprocess.check_output(cmd, shell=True, text=True, **kwargs).strip()


def list_pci_devices() -> List[Dict[str, str]]:
    """List all PCIe devices with their details."""
    pattern = re.compile(
        r"(?P<bdf>[0-9a-fA-F:.]+) .*?\["
        r"(?P<class>[0-9a-fA-F]{4})\]: .*?\["
        r"(?P<ven>[0-9a-fA-F]{4}):(?P<dev>[0-9a-fA-F]{4})\]"
    )

    devices = []
    for line in run_command("lspci -Dnn").splitlines():
        match = pattern.match(line)
        if match:
            device_info = match.groupdict()
            device_info["pretty"] = line
            devices.append(device_info)

    return devices


def choose_device(devices: List[Dict[str, str]]) -> Dict[str, str]:
    """Interactive device selection from the list of PCIe devices."""
    print("\nSelect donor PCIe device:")
    for i, device in enumerate(devices):
        print(f" [{i}] {device['pretty']}")

    while True:
        try:
            selection = input("Enter number: ")
            index = int(selection)
            return devices[index]
        except (ValueError, IndexError):
            print("  Invalid selection — please try again.")


def get_current_driver(bdf: str) -> Optional[str]:
    """Get the current driver bound to a PCIe device."""
    if not validate_bdf_format(bdf):
        raise ValueError(
            f"Invalid BDF format: {bdf}. Expected format: DDDD:BB:DD.F (e.g., 0000:03:00.0)"
        )

    driver_path = f"/sys/bus/pci/devices/{bdf}/driver"
    if os.path.exists(driver_path):
        return os.path.basename(os.path.realpath(driver_path))
    return None


def get_iommu_group(bdf: str) -> str:
    """Get the IOMMU group for a PCIe device."""
    if not validate_bdf_format(bdf):
        raise ValueError(
            f"Invalid BDF format: {bdf}. Expected format: DDDD:BB:DD.F (e.g., 0000:03:00.0)"
        )

    iommu_link = f"/sys/bus/pci/devices/{bdf}/iommu_group"
    return os.path.basename(os.path.realpath(iommu_link))


def list_usb_devices() -> List[Tuple[str, str]]:
    """Return list of USB devices as (vid:pid, description) tuples."""
    try:
        output = subprocess.check_output("lsusb", shell=True, text=True).splitlines()
    except subprocess.CalledProcessError:
        return []

    devices = []
    for line in output:
        match = re.match(
            r"Bus.*Device.*ID\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\s+(.*)", line
        )
        if match:
            vid_pid = match.group(1)
            description = match.group(2)
            devices.append((vid_pid, description))

    return devices


def select_usb_device() -> str:
    """Interactive USB device selection for flashing."""
    devices = list_usb_devices()
    if not devices:
        error_msg = "No USB devices found"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    print("\nSelect FPGA board / USB programmer:")
    for i, (vid_pid, description) in enumerate(devices):
        print(f" [{i}] {vid_pid}  {description}")

    while True:
        try:
            selection = input("Enter number: ")
            index = int(selection)
            return devices[index][0]  # Return VID:PID
        except (ValueError, IndexError):
            print("  Invalid selection — please try again.")
        except KeyboardInterrupt:
            logger.warning("USB device selection interrupted by user")
            raise


def flash_firmware(bitfile: pathlib.Path) -> None:
    """Flash firmware to FPGA board using usbloader."""
    logger.info("Starting firmware flash process")

    if shutil.which("usbloader") is None:
        error_msg = "usbloader not found in PATH — install λConcept usbloader first"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    try:
        vid_pid = select_usb_device()
        logger.info(f"Selected USB device: {vid_pid}")
        print(f"[*] Flashing firmware using VID:PID {vid_pid}")

        subprocess.run(
            f"usbloader --vidpid {vid_pid} -f {bitfile}", shell=True, check=True
        )
        logger.info("Firmware flashed successfully")
        print("[✓] Firmware flashed successfully")

    except subprocess.CalledProcessError as e:
        error_msg = f"Flash failed: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error during firmware flash: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


def bind_to_vfio(
    bdf: str, vendor: str, device: str, original_driver: Optional[str]
) -> None:
    """Bind PCIe device to vfio-pci driver"""
    if not validate_bdf_format(bdf):
        raise ValueError(
            f"Invalid BDF format: {bdf}. Expected format: DDDD:BB:DD.F (e.g., 0000:03:00.0)"
        )

    logger.info(
        f"Binding device {bdf} to vfio-pci driver (current driver: {original_driver or 'none'})"
    )
    print("[*] Binding device to vfio-pci driver...")

    try:
        # Check if vfio-pci driver is available
        if not os.path.exists("/sys/bus/pci/drivers/vfio-pci"):
            error_msg = (
                "vfio-pci driver not available. Ensure VFIO is enabled in kernel."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Add device ID to vfio-pci
        logger.debug(f"Adding device ID {vendor}:{device} to vfio-pci")
        run_command(f"echo {vendor} {device} > /sys/bus/pci/drivers/vfio-pci/new_id")

        # Unbind from current driver if present
        if original_driver:
            logger.debug(f"Unbinding from current driver: {original_driver}")
            run_command(f"echo {bdf} > /sys/bus/pci/devices/{bdf}/driver/unbind")

        # Bind to vfio-pci
        logger.debug(f"Binding {bdf} to vfio-pci")
        run_command(f"echo {bdf} > /sys/bus/pci/drivers/vfio-pci/bind")

        logger.info(f"Successfully bound {bdf} to vfio-pci")

    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to bind device to vfio-pci: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error during vfio binding: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


def restore_original_driver(bdf: str, original_driver: Optional[str]) -> None:
    """Restore the original driver binding for the PCIe device"""
    if not validate_bdf_format(bdf):
        logger.warning(f"Invalid BDF format during restore: {bdf}")
        return

    logger.info(
        f"Restoring original driver binding for {bdf} (target driver: {original_driver or 'none'})"
    )
    print("[*] Restoring original driver binding...")

    try:
        # Check if device is still bound to vfio-pci before attempting unbind
        current_driver = get_current_driver(bdf)
        if current_driver == "vfio-pci":
            logger.debug(f"Unbinding {bdf} from vfio-pci")
            run_command(f"echo {bdf} > /sys/bus/pci/drivers/vfio-pci/unbind")
        else:
            logger.info(
                f"Device {bdf} not bound to vfio-pci (current: {current_driver or 'none'})"
            )

        # Bind back to original driver if it existed
        if original_driver:
            # Check if original driver is available
            driver_path = f"/sys/bus/pci/drivers/{original_driver}"
            if os.path.exists(driver_path):
                logger.debug(f"Binding {bdf} back to {original_driver}")
                run_command(f"echo {bdf} > /sys/bus/pci/drivers/{original_driver}/bind")
                logger.info(f"Successfully restored {bdf} to {original_driver}")
            else:
                logger.warning(
                    f"Original driver {original_driver} not available for restore"
                )
        else:
            logger.info(f"No original driver to restore for {bdf}")

    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to restore original driver for {bdf}: {e}")
        print(f"Warning: Failed to restore original driver: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error during driver restore for {bdf}: {e}")
        print(f"Warning: Unexpected error during driver restore: {e}")


def run_build_container(bdf: str, board: str, vfio_device: str) -> None:
    """Run the firmware build in a Podman container"""
    if not validate_bdf_format(bdf):
        raise ValueError(
            f"Invalid BDF format: {bdf}. Expected format: DDDD:BB:DD.F (e.g., 0000:03:00.0)"
        )

    logger.info(f"Starting container build for device {bdf} on board {board}")

    # Ensure output directory exists
    os.makedirs("output", exist_ok=True)

    # Validate VFIO device exists
    if not os.path.exists(vfio_device):
        error_msg = f"VFIO device {vfio_device} not found"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # Construct Podman command
    container_cmd = textwrap.dedent(
        f"""
        podman run --rm -it --privileged \
          --device={vfio_device} \
          --device=/dev/vfio/vfio \
          -v {os.getcwd()}/output:/app/output \
          dma-fw \
          sudo python3 /app/build.py --bdf {bdf} --board {board}
    """
    ).strip()

    logger.debug(f"Container command: {container_cmd}")
    print("[*] Launching build container...")
    start_time = time.time()

    try:
        subprocess.run(container_cmd, shell=True, check=True)
        elapsed_time = time.time() - start_time
        logger.info(f"Build completed successfully in {elapsed_time:.1f} seconds")
        print(f"[✓] Build completed in {elapsed_time:.1f} seconds")

    except subprocess.CalledProcessError as e:
        elapsed_time = time.time() - start_time
        error_msg = f"Container build failed after {elapsed_time:.1f} seconds: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e
    except Exception as e:
        elapsed_time = time.time() - start_time
        error_msg = f"Unexpected error during container build after {elapsed_time:.1f} seconds: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


def validate_environment() -> None:
    """Validate that the environment is properly set up."""
    if os.geteuid() != 0:
        error_msg = "This script requires root privileges. Run with sudo."
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # Check if Podman is available
    if shutil.which("podman") is None:
        error_msg = "Podman not found in PATH. Please install Podman first."
        logger.error(error_msg)
        raise RuntimeError(error_msg)


def main() -> int:
    """Main entry point for the firmware generator"""
    bdf = None
    original_driver = None

    try:
        logger.info("Starting PCILeech firmware generation process")
        validate_environment()

        # Parse command line arguments
        parser = argparse.ArgumentParser(
            description="Generate DMA firmware from donor PCIe device",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=textwrap.dedent(
                """
                Examples:
                  sudo python3 generate.py --board 75t
                  sudo python3 generate.py --board 100t --flash
            """
            ),
        )

        parser.add_argument(
            "--flash",
            action="store_true",
            help="Flash output/firmware.bin with usbloader after build",
        )

        parser.add_argument(
            "--board",
            choices=["35t", "75t", "100t"],
            default="35t",
            help="Target FPGA board type (default: 35t/Squirrel)",
        )

        args = parser.parse_args()
        logger.info(f"Configuration: board={args.board}, flash={args.flash}")

        # List and select PCIe device
        devices = list_pci_devices()
        if not devices:
            error_msg = "No PCIe devices found"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        selected_device = choose_device(devices)
        bdf = selected_device["bdf"]
        vendor = selected_device["ven"]
        device = selected_device["dev"]

        logger.info(f"Selected device: {bdf} (VID:{vendor} DID:{device})")
        print(f"\nSelected device: {bdf} (VID:{vendor} DID:{device})")

        # Get device information
        iommu_group = get_iommu_group(bdf)
        vfio_device = f"/dev/vfio/{iommu_group}"
        original_driver = get_current_driver(bdf)

        logger.info(
            f"Device info - IOMMU group: {iommu_group}, Current driver: {original_driver or 'none'}"
        )
        print(f"IOMMU group: {iommu_group}")
        print(f"Current driver: {original_driver or 'none'}")

        # Bind device to vfio-pci
        bind_to_vfio(bdf, vendor, device, original_driver)

        # Run the build container
        run_build_container(bdf, args.board, vfio_device)

        # Flash firmware if requested
        if args.flash:
            firmware_path = pathlib.Path("output/firmware.bin")
            if not firmware_path.exists():
                error_msg = "ERROR: firmware.bin not found in ./output directory"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            flash_firmware(firmware_path)

        logger.info("Firmware generation process completed successfully")
        print("[✓] Process completed successfully")
        return 0

    except KeyboardInterrupt:
        logger.warning("Process interrupted by user")
        print("\n[!] Process interrupted by user")
        # Don't use sys.exit() - let finally block handle cleanup
        return 1
    except Exception as e:
        logger.error(f"Fatal error during firmware generation: {e}")
        print(f"\n[✗] Fatal error: {e}")
        # Don't use sys.exit() - let finally block handle cleanup
        return 1
    finally:
        # Always attempt to restore the original driver if we have the info
        if bdf and original_driver is not None:
            try:
                restore_original_driver(bdf, original_driver)
                logger.info("Driver restoration completed successfully")
            except Exception as e:
                logger.error(f"Failed to restore driver during cleanup: {e}")
                print(f"[!] Warning: Failed to restore driver during cleanup: {e}")

        # Ensure any temporary files are cleaned up
        try:
            # Clean up any temporary VFIO state if needed
            logger.debug("Cleanup completed")
        except Exception as e:
            logger.warning(f"Minor cleanup issue: {e}")


if __name__ == "__main__":
    sys.exit(main())
