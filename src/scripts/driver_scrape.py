#!/usr/bin/env python3
"""
driver_scrape.py  <vendor_id_hex> <device_id_hex>
Example:
    python3 driver_scrape.py 8086 1533
Outputs JSON list:
[
  {"offset": 0x400, "name": "reg_ctrl", "value": "0x0", "rw": "rw",
   "context": {"function": "init_device", "dependencies": ["reg_status"],
   "timing": "early", "access_pattern": "write_then_read"}},
  ...
]
"""

import ast
import json
import os
import pathlib
import re
import subprocess
import sys
import tarfile
import tempfile

# Module-level variables will be set in main()
VENDOR = None
DEVICE = None


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
            # Security: validate tar members before extraction
            def is_safe_path(path):
                return not (path.startswith("/") or ".." in path)

            safe_members = [m for m in t.getmembers() if is_safe_path(m.name)]
            t.extractall("/usr/src", members=safe_members)
    return untar_dir


def ko_name_from_alias():
    alias_line = run(
        f"modprobe --resolve-alias pci:v0000{VENDOR}d0000{DEVICE}*"
    ).splitlines()
    if not alias_line:
        sys.exit("No driver module found for that VID:DID in modules.alias")
    return alias_line[-1].strip()  # e.g. snd_hda_intel


def analyze_function_context(file_content, reg_name):
    """Analyze the function context where a register is used."""
    context = {
        "function": None,
        "dependencies": [],
        "timing": "unknown",
        "access_pattern": "unknown",
    }

    # Find function containing the register usage
    func_pattern = re.compile(
        r"(\w+)\s*\([^)]*\)\s*\{[^}]*" + re.escape(reg_name) + r"[^}]*\}", re.DOTALL
    )
    func_match = func_pattern.search(file_content)

    if func_match:
        context["function"] = func_match.group(1)
        func_body = func_match.group(0)

        # Analyze dependencies - other registers used in same function
        dep_pattern = re.compile(r"\b(REG_[A-Z0-9_]+)\b")
        deps = set(dep_pattern.findall(func_body))
        deps.discard(reg_name)  # Remove self
        context["dependencies"] = list(deps)[:5]  # Limit to 5 most relevant

        # Determine timing based on function name patterns
        if any(
            keyword in context["function"].lower()
            for keyword in ["init", "probe", "start"]
        ):
            context["timing"] = "early"
        elif any(
            keyword in context["function"].lower()
            for keyword in ["exit", "remove", "stop"]
        ):
            context["timing"] = "late"
        elif any(
            keyword in context["function"].lower()
            for keyword in ["irq", "interrupt", "handler"]
        ):
            context["timing"] = "interrupt"
        else:
            context["timing"] = "runtime"

        # Analyze access patterns
        write_count = len(
            re.findall(r"write[blwq]?\s*\([^)]*" + re.escape(reg_name), func_body)
        )
        read_count = len(
            re.findall(r"read[blwq]?\s*\([^)]*" + re.escape(reg_name), func_body)
        )

        if write_count > 0 and read_count > 0:
            context["access_pattern"] = "read_write"
        elif write_count > read_count:
            context["access_pattern"] = "write_heavy"
        elif read_count > write_count:
            context["access_pattern"] = "read_heavy"
        else:
            context["access_pattern"] = "balanced"

    return context


def analyze_register_sequences(file_content, registers):
    """Analyze register access sequences and timing dependencies."""
    sequences = {}

    # Find sequences of register accesses within functions
    func_pattern = re.compile(r"(\w+)\s*\([^)]*\)\s*\{([^}]*)\}", re.DOTALL)

    for func_match in func_pattern.finditer(file_content):
        func_name = func_match.group(1)
        func_body = func_match.group(2)

        # Find all register accesses in order
        access_pattern = re.compile(
            r"(write|read)[blwq]?\s*\([^)]*\b(REG_[A-Z0-9_]+)\b"
        )
        accesses = []

        for access_match in access_pattern.finditer(func_body):
            operation = access_match.group(1)
            reg_name = access_match.group(2)
            if reg_name in registers:
                accesses.append((operation, reg_name, access_match.start()))

        if len(accesses) > 1:
            sequences[func_name] = accesses

    return sequences


def extract_timing_constraints(file_content):
    """Extract timing constraints and delays from driver code."""
    timing_info = {}

    # Look for delay patterns
    delay_pattern = re.compile(
        r"(udelay|mdelay|msleep|usleep_range)\s*\(\s*(\d+)", re.IGNORECASE
    )

    for delay_match in delay_pattern.finditer(file_content):
        delay_type = delay_match.group(1).lower()
        delay_value = int(delay_match.group(2))

        # Convert to microseconds for consistency
        if delay_type in ["mdelay", "msleep"]:
            delay_us = delay_value * 1000
        elif delay_type == "udelay":
            delay_us = delay_value
        else:  # usleep_range
            delay_us = delay_value

        # Find nearby register accesses
        context_start = max(0, delay_match.start() - 200)
        context_end = min(len(file_content), delay_match.end() + 200)
        context = file_content[context_start:context_end]

        reg_pattern = re.compile(r"\b(REG_[A-Z0-9_]+)\b")
        nearby_regs = reg_pattern.findall(context)

        if nearby_regs:
            timing_info[delay_match.start()] = {
                "delay_us": delay_us,
                "registers": list(set(nearby_regs)),
            }

    return timing_info


# ------------------------------------------------------------------ main
def main():
    """Main function to scrape driver registers."""
    global VENDOR, DEVICE

    if len(sys.argv) != 3:
        sys.exit("Usage: driver_scrape.py <vendor_id hex> <device_id hex>")

    VENDOR = sys.argv[1].lower()
    DEVICE = sys.argv[2].lower()

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
    RD = re.compile(r"read[blwq]?\s*\(.*?\b(REG_[A-Z0-9_]+)\b")

    regs, writes, reads = {}, set(), set()
    all_content = ""

    # Enhanced analysis: collect all file content and register information
    for path in src_files:
        txt = path.read_text(errors="ignore")
        all_content += txt + "\n"

        for m in REG.finditer(txt):
            regs[m.group(1)] = int(m.group(2), 16)
        for w in WR.finditer(txt):
            writes.add(w.group(1))
            if len(writes) > 64:
                break
        for r in RD.finditer(txt):
            reads.add(r.group(1))
            if len(reads) > 64:
                break

    # Analyze register sequences and timing
    sequences = analyze_register_sequences(all_content, regs.keys())
    timing_info = extract_timing_constraints(all_content)

    items = []
    for sym, off in regs.items():
        # Determine read/write capability
        rw_capability = "ro"  # default
        if sym in writes and sym in reads:
            rw_capability = "rw"
        elif sym in writes:
            rw_capability = "wo"
        elif sym in reads:
            rw_capability = "ro"

        # Analyze context for this register
        context = analyze_function_context(all_content, sym)

        # Add timing information if available
        relevant_timing = []
        for timing_pos, timing_data in timing_info.items():
            if sym in timing_data["registers"]:
                relevant_timing.append(
                    {"delay_us": timing_data["delay_us"], "context": "register_access"}
                )

        if relevant_timing:
            context["timing_constraints"] = relevant_timing[
                :3
            ]  # Limit to 3 most relevant

        # Add sequence information
        context["sequences"] = []
        for func_name, func_sequences in sequences.items():
            for i, (op, reg_name, pos) in enumerate(func_sequences):
                if reg_name == sym:
                    # Add context about surrounding operations
                    sequence_context = {
                        "function": func_name,
                        "position": i,
                        "total_ops": len(func_sequences),
                        "operation": op,
                    }

                    # Add preceding and following operations
                    if i > 0:
                        sequence_context["preceded_by"] = func_sequences[i - 1][1]
                    if i < len(func_sequences) - 1:
                        sequence_context["followed_by"] = func_sequences[i + 1][1]

                    context["sequences"].append(sequence_context)

        items.append(
            dict(
                offset=off,
                name=sym.lower(),
                value="0x0",
                rw=rw_capability,
                context=context,
            )
        )

    print(json.dumps(items, indent=2))


if __name__ == "__main__":
    main()
