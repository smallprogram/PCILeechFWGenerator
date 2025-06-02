# DMA Firmware Generator

Generate spoofed PCIe DMA firmware from real donor hardware with a single command. The workflow rips the donor's configuration space, builds a personalized FPGA bit‑stream in an isolated container, and (optionally) flashes your DMA card over USB‑JTAG.

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
sudo python3 generate.py              # interactive – pick the donor device
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

## 5. Cleanup & Safety

- Rebind the donor back to its original driver if you keep it around.
- Keep the generated firmware private; it contains identifiers from the donor.

## 6. Disclaimer

For educational research and legitimate PCIe development only. Misuse may violate laws and void warranties. The authors assume no liability.