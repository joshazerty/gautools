#!/usr/bin/env python3
"""
Extract IRC endpoints from a Gaussian IRC output and create optimization input files.
Reads route/header/footer from the original input file (same approach as ts2irc.py).

Usage: irc2opt.py <irc_output.log>
"""

import sys
import re
import os
from pathlib import Path

# --- Colors & Formatting ---
class Colors:
    HEADER  = '\033[95m'
    OKBLUE  = '\033[94m'
    OKCYAN  = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL    = '\033[91m'
    ENDC    = '\033[0m'
    BOLD    = '\033[1m'

TICK  = f"{Colors.OKGREEN}✔{Colors.ENDC}"
CROSS = f"{Colors.FAIL}✘{Colors.ENDC}"
WARN  = f"{Colors.WARNING}⚠{Colors.ENDC}"
INFO  = f"{Colors.OKCYAN}ℹ{Colors.ENDC}"

def log_header(title):
    print(f"\n{Colors.HEADER}{'='*60}\n {title}\n{'='*60}{Colors.ENDC}")

def log_info(msg):    print(f" {INFO}  {msg}")
def log_success(msg): print(f" {TICK}  {msg}")
def log_error(msg):   print(f" {CROSS}  {msg}")
def log_warn(msg):    print(f" {WARN}  {msg}")

# --- Full Periodic Table ---
PERIODIC_TABLE = {
    1: 'H',  2: 'He', 3: 'Li', 4: 'Be', 5: 'B',  6: 'C',  7: 'N',  8: 'O',  9: 'F',  10: 'Ne',
    11: 'Na', 12: 'Mg', 13: 'Al', 14: 'Si', 15: 'P',  16: 'S',  17: 'Cl', 18: 'Ar', 19: 'K',  20: 'Ca',
    21: 'Sc', 22: 'Ti', 23: 'V',  24: 'Cr', 25: 'Mn', 26: 'Fe', 27: 'Co', 28: 'Ni', 29: 'Cu', 30: 'Zn',
    31: 'Ga', 32: 'Ge', 33: 'As', 34: 'Se', 35: 'Br', 36: 'Kr', 37: 'Rb', 38: 'Sr', 39: 'Y',  40: 'Zr',
    41: 'Nb', 42: 'Mo', 43: 'Tc', 44: 'Ru', 45: 'Rh', 46: 'Pd', 47: 'Ag', 48: 'Cd', 49: 'In', 50: 'Sn',
    51: 'Sb', 52: 'Te', 53: 'I',  54: 'Xe', 55: 'Cs', 56: 'Ba', 57: 'La', 58: 'Ce', 59: 'Pr', 60: 'Nd',
    61: 'Pm', 62: 'Sm', 63: 'Eu', 64: 'Gd', 65: 'Tb', 66: 'Dy', 67: 'Ho', 68: 'Er', 69: 'Tm', 70: 'Yb',
    71: 'Lu', 72: 'Hf', 73: 'Ta', 74: 'W',  75: 'Re', 76: 'Os', 77: 'Ir', 78: 'Pt', 79: 'Au', 80: 'Hg',
    81: 'Tl', 82: 'Pb', 83: 'Bi', 84: 'Po', 85: 'At', 86: 'Rn', 87: 'Fr', 88: 'Ra', 89: 'Ac', 90: 'Th',
    91: 'Pa', 92: 'U',  93: 'Np', 94: 'Pu', 95: 'Am', 96: 'Cm', 97: 'Bk', 98: 'Cf', 99: 'Es', 100: 'Fm',
    101: 'Md', 102: 'No', 103: 'Lr',
}

def get_symbol(atomic_num):
    return PERIODIC_TABLE.get(int(atomic_num), f'X{atomic_num}')


# --- Find original input file ---
def find_input_file(log_file_path):
    """Locate the matching .inp/.gjf/.com for a given log file."""
    base = Path(log_file_path).stem
    parent = Path(log_file_path).parent

    # Exact match first
    for ext in ['.inp', '.gjf', '.com']:
        candidate = parent / (base + ext)
        if candidate.exists():
            return candidate

    # Try stripping _irc suffix (ts2irc.py names its output <base>_irc.inp)
    clean_base = re.sub(r'_irc$', '', base, flags=re.IGNORECASE)
    if clean_base != base:
        for ext in ['.inp', '.gjf', '.com']:
            candidate = parent / (clean_base + ext)
            if candidate.exists():
                return candidate

    return None


# --- Parse original input file ---
def parse_original_input(inp_file):
    """
    State-machine parser — identical approach to ts2irc.py.
    Extracts Link0, route section, title, charge/mult, and footer.
    """
    log_info(f"Reading configuration from: {inp_file.name}")
    with open(inp_file, 'r') as f:
        lines = f.readlines()

    header_lines = []
    title_lines  = []
    chg_mult_line = ""
    footer_lines  = []
    state = 'header'

    for line in lines:
        stripped = line.strip()
        if state == 'header':
            header_lines.append(line.rstrip())
            if stripped.startswith('#'):
                state = 'route_end_check'
        elif state == 'route_end_check':
            if not stripped or stripped.startswith('---'):
                state = 'title'
            else:
                header_lines.append(line.rstrip())
        elif state == 'title':
            if not stripped:
                state = 'charge'
            else:
                title_lines.append(line.rstrip())
        elif state == 'charge':
            if stripped:
                chg_mult_line = line.rstrip()
                state = 'geom'
        elif state == 'geom':
            if not stripped:
                state = 'footer'
        elif state == 'footer':
            footer_lines.append(line.rstrip())

    link0_cmds   = [l for l in header_lines if l.strip().startswith('%')]
    route_lines  = [l for l in header_lines if l.strip().startswith('#') or
                    (l.strip() and not l.strip().startswith('%'))]
    route_section = " ".join(route_lines)

    return link0_cmds, route_section, title_lines, chg_mult_line, footer_lines


# --- Modify route: IRC → Opt ---
def process_route_for_opt(route_line):
    """Remove IRC keyword from route and add Opt(CalcFC,MaxCycles=200) Freq."""
    r = route_line
    # Remove IRC (with and without options)
    r = re.sub(r'IRC\s*=\s*\([^)]*\)', '', r, flags=re.IGNORECASE)
    r = re.sub(r'IRC\s*=\s*\S+',       '', r, flags=re.IGNORECASE)
    r = re.sub(r'\bIRC\b',             '', r, flags=re.IGNORECASE)
    # Remove any existing Opt/Freq (we'll add our own)
    r = re.sub(r'Opt\s*=\s*\([^)]*\)', '', r, flags=re.IGNORECASE)
    r = re.sub(r'Opt\s*=\s*\S+',       '', r, flags=re.IGNORECASE)
    r = re.sub(r'\bOpt\b',             '', r, flags=re.IGNORECASE)
    r = re.sub(r'Freq\s*=\s*\([^)]*\)','', r, flags=re.IGNORECASE)
    r = re.sub(r'Freq\s*=\s*\S+',      '', r, flags=re.IGNORECASE)
    r = re.sub(r'\bFreq\b',            '', r, flags=re.IGNORECASE)
    r = " ".join(r.split())
    return f"{r} Opt=(CalcFC,MaxCycles=200) Freq"


# --- Parse IRC log for endpoint geometries ---
def parse_irc_endpoints(filepath):
    """
    Extract the final geometry from the FORWARD and REVERSE IRC directions.

    Strategy:
      - Track 'Following the Reaction Path in the REVERSE/FORWARD direction' markers
        to assign each geometry block to a direction.
      - Take the last geometry of each direction as the endpoint.
      - Fall back to geometries[1] / geometries[-1] if no direction markers found.
    """
    with open(filepath, 'r') as f:
        lines = f.readlines()

    atom_re = re.compile(
        r'^\s+\d+\s+(\d+)\s+\d+\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)'
    )

    reverse_geoms = []
    forward_geoms = []
    all_geoms     = []
    direction     = None  # 'reverse' | 'forward' | None

    i = 0
    while i < len(lines):
        line = lines[i]

        # Update direction from path-following markers
        if re.search(r'Following the Reaction Path in the REVERSE', line, re.IGNORECASE):
            direction = 'reverse'
        elif re.search(r'Following the Reaction Path in the FORWARD', line, re.IGNORECASE):
            direction = 'forward'

        # Parse geometry block
        if "Standard orientation:" in line or "Input orientation:" in line:
            frame = []
            i += 5  # skip the 4-line table header + separator
            while i < len(lines):
                if "----------------" in lines[i]:
                    break
                m = atom_re.match(lines[i])
                if m:
                    sym = get_symbol(int(m.group(1)))
                    x, y, z = float(m.group(2)), float(m.group(3)), float(m.group(4))
                    frame.append((sym, x, y, z))
                i += 1
            if frame:
                all_geoms.append(frame)
                if direction == 'reverse':
                    reverse_geoms.append(frame)
                elif direction == 'forward':
                    forward_geoms.append(frame)
        i += 1

    # Prefer direction-tagged geometries
    if reverse_geoms and forward_geoms:
        log_success(
            f"Direction markers found: "
            f"{len(reverse_geoms)} reverse + {len(forward_geoms)} forward steps"
        )
        return reverse_geoms[-1], forward_geoms[-1], 'directed'

    # Fallback: TS = geom[0], remaining split between directions
    if len(all_geoms) >= 3:
        log_warn("No direction markers found — using first/last geometry as endpoints")
        return all_geoms[1], all_geoms[-1], 'fallback'

    raise ValueError(
        f"Not enough geometries in IRC output (found {len(all_geoms)}, need >= 3)"
    )


# --- Write optimisation input file ---
def format_atoms(atoms):
    return [f" {sym:<2} {x:>14.8f} {y:>14.8f} {z:>14.8f}" for sym, x, y, z in atoms]


def write_opt_input(filename, link0, route, title, chg_mult, atoms, footer):
    chk_name = os.path.splitext(filename)[0] + ".chk"
    new_link0 = [l for l in link0 if not l.lower().startswith('%chk')]
    new_link0.insert(0, f"%chk={chk_name}")

    with open(filename, 'w') as f:
        for l in new_link0:
            f.write(f"{l}\n")
        f.write(f"{route}\n\n")
        for t in title:
            f.write(f"{t}\n")
        f.write("\n")
        f.write(f"{chg_mult}\n")
        for a in format_atoms(atoms):
            f.write(f"{a}\n")
        f.write("\n")
        if footer:
            for line in footer:
                f.write(f"{line}\n")
            if footer and footer[-1].strip():
                f.write("\n")


# --- Main ---
def main():
    log_header("IRC Endpoint → Optimisation Setup")

    if len(sys.argv) != 2:
        log_error("Usage: irc2opt.py <irc_output.log>")
        sys.exit(1)

    log_file = sys.argv[1]
    if not os.path.exists(log_file):
        log_error(f"File not found: {log_file}")
        sys.exit(1)

    log_info(f"Log file: {Colors.BOLD}{log_file}{Colors.ENDC}")

    # 1. Extract IRC endpoints
    try:
        rev_geom, fwd_geom, method = parse_irc_endpoints(log_file)
        log_success(f"Extracted {len(rev_geom)}-atom geometries via '{method}' method")
    except Exception as e:
        log_error(f"Failed to extract IRC endpoints: {e}")
        sys.exit(1)

    # 2. Read route/footer from original input
    inp_file = find_input_file(log_file)
    if inp_file:
        log_success(f"Found input file: {inp_file.name}")
        try:
            link0, route, title, chg_mult, footer = parse_original_input(inp_file)
        except Exception as e:
            log_error(f"Failed to parse input file: {e}")
            sys.exit(1)
    else:
        log_error("No matching .inp/.gjf/.com file found — cannot read route/footer.")
        log_info("The IRC .inp must share the same basename as the .log file.")
        sys.exit(1)

    # 3. Build optimisation route
    opt_route = process_route_for_opt(route)
    log_info(f"Route: {opt_route}")

    # 4. Build output filenames
    base = os.path.splitext(os.path.basename(log_file))[0]
    clean_base = re.sub(r'_irc$', '', base, flags=re.IGNORECASE)
    rev_out = f"{clean_base}_irc_rev.inp"
    fwd_out = f"{clean_base}_irc_fwd.inp"

    # 5. Write files
    for outfile, geom, label in [(rev_out, rev_geom, "reverse"), (fwd_out, fwd_geom, "forward")]:
        try:
            write_opt_input(outfile, link0, opt_route, title, chg_mult, geom, footer)
            log_success(f"Written ({label}): {outfile}")
        except Exception as e:
            log_error(f"Failed to write {outfile}: {e}")

    log_header("Done")


if __name__ == "__main__":
    main()
