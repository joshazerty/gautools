#!/usr/bin/env python3
"""
Gaussian Relaxed Scan Analyzer (Pro Edition)
- Professional CLI Output
- cclib-based Parsing
- Publication Quality Plots (Angstroms/kcal)
- QST2 Input Generation
"""

import sys
import re
import numpy as np
import matplotlib.pyplot as plt
import cclib
from pathlib import Path

# --- UI / Formatting Helpers ---
def print_banner(text, style='='):
    """Prints a professional looking banner."""
    width = 60
    print(f"\n{style*width}")
    print(f"{text.center(width)}")
    print(f"{style*width}\n")

def print_status(step, message):
    """Prints a formatted status message."""
    print(f"[{step}] {message}")

def print_success(message):
    print(f" \033[92m✓ {message}\033[0m") # Green checkmark

def print_error(message):
    print(f" \033[91m✗ ERROR: {message}\033[0m") # Red text

# --- Math Helpers ---
def calc_distance(p1, p2):
    return np.linalg.norm(p1 - p2)

def calc_angle(p1, p2, p3):
    v1 = p1 - p2
    v2 = p3 - p2
    cosine_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    return np.degrees(np.arccos(np.clip(cosine_angle, -1.0, 1.0)))

def calc_dihedral(p1, p2, p3, p4):
    b1 = -1.0 * (p2 - p1)
    b2 = p3 - p2
    b3 = p4 - p3
    b2 /= np.linalg.norm(b2)
    v = b1 - np.dot(b1, b2) * b2
    w = b3 - np.dot(b3, b2) * b2
    x = np.dot(v, w)
    y = np.dot(np.cross(b2, v), w)
    return np.degrees(np.arctan2(y, x))

# --- Parsing ---
def find_input_file(log_file_path):
    base = Path(log_file_path).stem
    parent = Path(log_file_path).parent
    for ext in ['.gjf', '.com', '.inp']:
        candidate = parent / (base + ext)
        if candidate.exists(): return candidate
    return None

def parse_with_cclib(log_file):
    print_status("PARSING", f"Reading {Path(log_file).name}...")
    try:
        data = cclib.io.ccread(log_file)
    except Exception as e:
        print_error(f"cclib failed: {e}")
        sys.exit(1)

    # Filter for Converged Steps
    if hasattr(data, 'optstatus') and len(data.optstatus) > 0:
        valid_indices = [i for i, status in enumerate(data.optstatus) if status & cclib.parser.data.ccData.OPT_DONE]
        if not valid_indices:
            print_status("WARNING", "No converged steps found. Using all geometries.")
            valid_indices = range(len(data.scfenergies))
    else:
        valid_indices = range(len(data.scfenergies))

    print_success(f"Found {len(valid_indices)} converged scan points")
    return data.scfenergies[valid_indices], data.atomcoords[valid_indices], data.atomnos

def get_scan_atoms(inp_file):
    if not inp_file: return [], 'Unknown'
    
    print_status("INPUT", f"Reading definition from {inp_file.name}")
    scan_atoms = []
    scan_type = 'Unknown'

    with open(inp_file, 'r') as f:
        lines = f.readlines()[::-1] # Read backward

    regex = r'^\s*(?:[a-zA-Z]\s+)?((?:\d+\s+){2,4})[Ss]\s+\d+'
    for line in lines:
        match = re.search(regex, line)
        if match:
            indices_str = match.group(1).strip().split()
            scan_atoms = [int(x)-1 for x in indices_str] # 0-based
            n = len(scan_atoms)
            if n == 2: scan_type = 'Bond'
            elif n == 3: scan_type = 'Angle'
            elif n == 4: scan_type = 'Dihedral'
            break
            
    if scan_type != 'Unknown':
        print_success(f"Detected {scan_type} Scan on atoms: {scan_atoms}")
    return scan_atoms, scan_type

# --- QST2 Logic ---
def parse_original_input(inp_file):
    if not inp_file: return None, None
    with open(inp_file, 'r') as f: lines = f.readlines()

    header_lines = []
    footer_lines = []
    state = 'header'
    
    for line in lines:
        if state == 'header':
            header_lines.append(line)
            if line.strip().startswith('#'): state = 'route'
        elif state == 'route':
            header_lines.append(line)
            if not line.strip(): state = 'title'
        elif state == 'title':
            header_lines.append(line)
            if not line.strip(): state = 'charge'
        elif state == 'charge':
            header_lines.append(line)
            state = 'geom'
        elif state == 'geom':
            if not line.strip(): state = 'footer'
        elif state == 'footer':
            # Remove scan definitions
            if not re.search(r'^\s*((?:\d+\s+)+)[Ss]\s+\d+', line):
                footer_lines.append(line)

    return "".join(header_lines), "".join(footer_lines)

def modify_header(header, chk_name):
    lines = header.splitlines()
    new_lines = []
    for line in lines:
        if line.strip().lower().startswith('%chk'):
            new_lines.append(f"%chk={chk_name}")
        elif line.strip().startswith('#'):
            # Strip old opts, add QST2
            clean = re.sub(r'Opt(?:=\([^\)]+\)|=[^\s]+)?', '', line, flags=re.IGNORECASE)
            rep = '#p Opt=(QST2,CalcFC) ' if '#p' in clean.lower() else '# Opt=(QST2,CalcFC) '
            # Replace regex ensures we respect #P vs #
            if '#p' in clean.lower(): clean = clean.replace('#p', rep, 1)
            elif '#P' in clean: clean = clean.replace('#P', rep, 1)
            else: clean = clean.replace('#', rep, 1)
            new_lines.append(re.sub(r'\s+', ' ', clean))
        else:
            new_lines.append(line)
    return "\n".join(new_lines) + "\n"

def get_atomic_symbol(n):
    pt = {
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
    return pt.get(n, f'X{n}')

def write_qst2(coords, atoms, max_idx, filename, inp_file):
    if max_idx == 0 or max_idx == len(coords) - 1:
        print_error("TS is at the edge of the scan. Extend your scan range!")
        return

    print_status("WRITING", f"Generating QST2 input: {filename}")
    orig_head, orig_foot = parse_original_input(inp_file)
    header = modify_header(orig_head, Path(filename).stem + ".chk")

    with open(filename, 'w') as f:
        f.write(header)
        # Reactant
        for i, z in enumerate(atoms):
            c = coords[max_idx - 1][i]
            f.write(f"{get_atomic_symbol(z):2s} {c[0]:12.8f} {c[1]:12.8f} {c[2]:12.8f}\n")
        f.write("\n")
        # Product
        for i, z in enumerate(atoms):
            c = coords[max_idx + 1][i]
            f.write(f"{get_atomic_symbol(z):2s} {c[0]:12.8f} {c[1]:12.8f} {c[2]:12.8f}\n")
        f.write("\n")
        if orig_foot: f.write(orig_foot)
        
    print_success("QST2 File Created Successfully")

# --- Plotting ---
def plot_pes(x, y, scan_type):
    print_status("PLOTTING", "Displaying Energy Profile...")
    max_idx = np.argmax(y)
    
    # Config
    if scan_type == 'Bond': xlabel = r'Bond Length ($\AA$)'
    elif scan_type in ['Angle', 'Dihedral']: xlabel = f'{scan_type} (degrees)'
    else: xlabel = 'Scan Step'

    plt.rcParams.update({
        'font.size': 12, 
        'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'DejaVu Sans', 'Liberation Sans', 'sans-serif']
    })

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(x, y, 'o-', color='#003366', lw=2, markersize=8, mfc='#4d79ff', mec='#003366')
    ax.plot(x[max_idx], y[max_idx], '*', color='#cc0000', ms=20, zorder=5)

    ax.set_xlabel(xlabel, fontsize=14, fontweight='bold')
    ax.set_ylabel(r'Relative Energy (kcal mol$^{-1}$)', fontsize=14, fontweight='bold')
    ax.set_title(f'Relaxed Scan Profile ({scan_type})', fontsize=16, pad=15)

    # Annotation
    label = f'TS Estimate\n{x[max_idx]:.3f} / {y[max_idx]:.1f} kcal/mol'
    y_off = (max(y)-min(y))*0.1 if (max(y)-min(y))>0 else 1.0
    ax.annotate(label, xy=(x[max_idx], y[max_idx]), xytext=(x[max_idx], y[max_idx]+y_off),
                arrowprops=dict(facecolor='#cc0000', shrink=0.05, width=2, headwidth=8),
                fontsize=10, ha='center', bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#cc0000", alpha=0.9))

    ax.grid(True, ls='--', alpha=0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    
    # Block until closed
    plt.show()
    return max_idx

# --- Main ---
def main():
    print_banner("Gaussian Relaxed Scan Analyzer")

    if len(sys.argv) < 2:
        print_error("Usage: python script.py <logfile>")
        sys.exit(1)

    log_file = sys.argv[1]
    inp_file = find_input_file(log_file)
    
    # 1. Parse
    energies_ev, coords, atom_nos = parse_with_cclib(log_file)
    if len(energies_ev) == 0:
        print_error("No data found.")
        sys.exit(1)

    # 2. Convert Data
    energies_kcal = (energies_ev - np.min(energies_ev)) * 23.0605
    scan_atoms, scan_type = get_scan_atoms(inp_file)
    
    x_values = []
    if scan_atoms:
        for geom in coords:
            pts = [geom[i] for i in scan_atoms]
            if scan_type == 'Bond': val = calc_distance(*pts)
            elif scan_type == 'Angle': val = calc_angle(*pts)
            elif scan_type == 'Dihedral': val = calc_dihedral(*pts)
            else: val = 0
            x_values.append(val)
    else:
        x_values = range(len(energies_ev))

    # 3. Plot
    max_idx = plot_pes(np.array(x_values), energies_kcal, scan_type)

    # 4. Interact (QST2)
    print_banner("Next Steps", style='-')
    
    if inp_file:
        try:
            choice = input("Generate QST2 input file? (y/n): ").strip().lower()
            if choice == 'y':
                out_name = f"{Path(log_file).stem}_qst2.gjf"
                write_qst2(coords, atom_nos, max_idx, out_name, inp_file)
            else:
                print_status("INFO", "QST2 generation skipped.")
        except KeyboardInterrupt:
            print("\n")
            print_status("INFO", "Operation cancelled.")
    else:
        print_error("Cannot generate QST2: No matching .inp/.gjf file found.")

    print_banner("Analysis Complete")

if __name__ == "__main__":
    main()
