#!/usr/bin/env python3
"""
driver_scrape.py  <vendor_id_hex> <device_id_hex>
Example:
    python3 driver_scrape.py 8086 1533
Outputs JSON list:
[
  {"offset": 0x400, "name": "reg_ctrl", "value": "0x0", "rw": "rw"},
  ...
]
"""

import subprocess, re, sys, json, pathlib, tarfile, os, tempfile

if len(sys.argv) != 3:
    sys.exit("Usage: driver_scrape.py <vendor_id hex> <device_id hex>")

VENDOR = sys.argv[1].lower()
DEVICE = sys.argv[2].lower()


# ------------------------------------------------------------------ helpers
def run(cmd):
    return subprocess.check_output(cmd, shell=True, text=True)


def ensure_kernel_source():
    """Extract /usr/src/linux-source-*.tar.* if not untarred yet."""
    src_pkg = next(pathlib.Path("/usr/src").glob("linux-source-*.tar*"), None)
    if not src_pkg:
        sys.exit("linux-source package not found inside container.")
    untar_dir = src_pkg.with_suffix("").with_suffix("")  # strip .tar.xz
    if not (untar_dir / "drivers").exists():
        print("[driver_scrape] Extracting kernel source…")
        with tarfile.open(src_pkg) as t:
            t.extractall("/usr/src")
    return untar_dir


def ko_name_from_alias():
    alias_line = run(
        f"modprobe --resolve-alias pci:v0000{VENDOR}d0000{DEVICE}*"
    ).splitlines()
    if not alias_line:
        sys.exit("No driver module found for that VID:DID in modules.alias")
    return alias_line[-1].strip()  # e.g. snd_hda_intel


# ------------------------------------------------------------------ main
ksrc = ensure_kernel_source()
driver = ko_name_from_alias()
print(f"[driver_scrape] Driver module: {driver}")

# find .c/.h files containing driver name
src_files = list(ksrc.rglob(f"{driver}*.c")) + list(ksrc.rglob(f"{driver}*.h"))
if not src_files:
    # heuristic: fallback to any file inside drivers/ with module name inside it
    src_files = [
        p for p in ksrc.rglob("*.c") if driver in p.read_text(errors="ignore")
    ][:20]

if not src_files:
    sys.exit("[]")  # nothing – let caller abort build

REG = re.compile(r"#define\s+(REG_[A-Z0-9_]+)\s+0x([0-9A-Fa-f]+)")
WR = re.compile(r"write[blwq]?\s*\(.*?\b(REG_[A-Z0-9_]+)\b")

regs, writes = {}, set()
for path in src_files:
    txt = path.read_text(errors="ignore")
    for m in REG.finditer(txt):
        regs[m.group(1)] = int(m.group(2), 16)
    for w in WR.finditer(txt):
        writes.add(w.group(1))
        if len(writes) > 64:
            break

items = []
for sym, off in regs.items():
    items.append(
        dict(
            offset=off,
            name=sym.lower(),
            value="0x0",
            rw="rw" if sym in writes else "ro",
        )
    )

print(json.dumps(items, indent=2))
