#!/usr/bin/env python3
"""
Convert XYZ file(s) to Gaussian input files.

Usage: xyz2inp.py <file1.xyz> [file2.xyz ...]
"""

import os
import sys

# --- Colors & Formatting ---
class Colors:
    OKGREEN = '\033[92m'
    FAIL    = '\033[91m'
    OKCYAN  = '\033[96m'
    ENDC    = '\033[0m'
    BOLD    = '\033[1m'

TICK  = f"{Colors.OKGREEN}✔{Colors.ENDC}"
CROSS = f"{Colors.FAIL}✘{Colors.ENDC}"
INFO  = f"{Colors.OKCYAN}ℹ{Colors.ENDC}"


def read_xyz_file(filename):
    """Read XYZ file and return list of coordinate lines."""
    try:
        with open(filename, 'r') as f:
            lines = f.readlines()
        num_atoms = int(lines[0].strip())
        coords = []
        for i in range(2, 2 + num_atoms):
            line = lines[i].strip()
            if line:
                coords.append(line)
        return coords
    except FileNotFoundError:
        print(f" {CROSS}  File not found: '{filename}'")
        return None
    except (ValueError, IndexError) as e:
        print(f" {CROSS}  Invalid XYZ format in '{filename}': {e}")
        return None


def create_gaussian_input(xyz_file, inp_file):
    """Create a Gaussian optimisation input file from an XYZ file."""
    coords = read_xyz_file(xyz_file)
    if coords is None:
        return False

    base = os.path.splitext(os.path.basename(inp_file))[0]
    chk_name = f"{base}.chk"

    header = (
        f"%chk={chk_name}\n"
        "%NProcShared=8\n"
        "%mem=24000MB\n"
        "#p B3LYP/gen pseudo=read EmpiricalDispersion=GD3BJ Int=UltraFine "
        "SCF=(MaxCycle=512,XQC) SCRF=(PCM,Solvent=1-Pentanol) "
        "Opt(MaxCycles=2000,CalcFC) Freq\n"
        "\n"
        "Title Card: Optimization\n"
        "\n"
        "-1 1\n"
    )

    footer = (
        "\n"
        "C O H 0\n"
        "def2SVP\n"
        "****\n"
        "Re 0\n"
        "SDD\n"
        "****\n"
        "\n"
        "Re 0\n"
        "SDD\n"
        "\n"
    )

    try:
        with open(inp_file, 'w') as f:
            f.write(header)
            for line in coords:
                f.write(line + '\n')
            f.write(footer)
        print(f" {TICK}  Created: {Colors.BOLD}{inp_file}{Colors.ENDC}")
        return True
    except IOError as e:
        print(f" {CROSS}  Error writing '{inp_file}': {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print(f" {INFO}  Usage: xyz2inp.py <file1.xyz> [file2.xyz ...]")
        sys.exit(1)

    print(f"\n{Colors.BOLD}XYZ → Gaussian Input Converter{Colors.ENDC}")
    print("=" * 40)

    success = fail = 0
    for xyz_file in sys.argv[1:]:
        base = os.path.splitext(xyz_file)[0]
        inp_file = base + '.inp'
        print(f"\n {INFO}  {xyz_file} → {inp_file}")
        if create_gaussian_input(xyz_file, inp_file):
            success += 1
        else:
            fail += 1

    print("\n" + "=" * 40)
    print(f" Done — {success} succeeded, {fail} failed\n")


if __name__ == "__main__":
    main()
