#!/usr/bin/env python3

import sys
import os
import re
from pathlib import Path

# --- Configuration & Constants ---
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

PERIODIC_TABLE = {
    1: 'H', 2: 'He', 3: 'Li', 4: 'Be', 5: 'B', 6: 'C', 7: 'N', 8: 'O', 9: 'F', 10: 'Ne',
    11: 'Na', 12: 'Mg', 13: 'Al', 14: 'Si', 15: 'P', 16: 'S', 17: 'Cl', 18: 'Ar', 19: 'K', 20: 'Ca',
    21: 'Sc', 22: 'Ti', 23: 'V', 24: 'Cr', 25: 'Mn', 26: 'Fe', 27: 'Co', 28: 'Ni', 29: 'Cu', 30: 'Zn',
    31: 'Ga', 32: 'Ge', 33: 'As', 34: 'Se', 35: 'Br', 36: 'Kr', 37: 'Rb', 38: 'Sr', 39: 'Y', 40: 'Zr',
    41: 'Nb', 42: 'Mo', 43: 'Tc', 44: 'Ru', 45: 'Rh', 46: 'Pd', 47: 'Ag', 48: 'Cd', 49: 'In', 50: 'Sn',
    51: 'Sb', 52: 'Te', 53: 'I', 54: 'Xe', 55: 'Cs', 56: 'Ba', 57: 'La', 58: 'Ce', 59: 'Pr', 60: 'Nd',
    61: 'Pm', 62: 'Sm', 63: 'Eu', 64: 'Gd', 65: 'Tb', 66: 'Dy', 67: 'Ho', 68: 'Er', 69: 'Tm', 70: 'Yb',
    71: 'Lu', 72: 'Hf', 73: 'Ta', 74: 'W', 75: 'Re', 76: 'Os', 77: 'Ir', 78: 'Pt', 79: 'Au', 80: 'Hg',
    81: 'Tl', 82: 'Pb', 83: 'Bi', 84: 'Po', 85: 'At', 86: 'Rn'
}

def log_info(message):
    print(f" {Colors.OKBLUE}[i]{Colors.ENDC}  {message}")

def log_success(message):
    print(f" {Colors.OKGREEN}[✓]{Colors.ENDC}  {message}")

def log_error(message):
    print(f" {Colors.FAIL}[✗]{Colors.ENDC}  {message}")

def log_header(title):
    print(f"\n{Colors.HEADER}{'='*60}")
    print(f" {title}")
    print(f"{'='*60}{Colors.ENDC}")

def get_atomic_symbol(atomic_number):
    return PERIODIC_TABLE.get(int(atomic_number), 'X')

# --- 1. Find Original Input File ---
def find_input_file(log_file_path):
    """
    Locates the corresponding .inp, .gjf, or .com file for a given log file.
    """
    base = Path(log_file_path).stem
    parent = Path(log_file_path).parent
    
    # Priority 1: Exact match (e.g., ts-8.log -> ts-8.inp)
    for ext in ['.inp', '.gjf', '.com']:
        candidate = parent / (base + ext)
        if candidate.exists(): 
            return candidate

    # Priority 2: Try stripping suffixes like _opt, _log, etc if no exact match
    clean_base = re.sub(r'_(log|out)$', '', base, flags=re.IGNORECASE)
    if clean_base != base:
        for ext in ['.inp', '.gjf', '.com']:
            candidate = parent / (clean_base + ext)
            if candidate.exists(): 
                return candidate
                
    return None

# --- 2. Parse Original Input (Clean Header/Footer) ---
def parse_original_input(inp_file):
    """
    Parses the original Gaussian Input file to extract Header, Title, Charge/Mult, and Footer.
    This logic mimics the robust state-machine approach from irc2opt.py.
    """
    log_info(f"Reading configuration from: {inp_file.name}")
    
    with open(inp_file, 'r') as f:
        lines = f.readlines()

    header_lines = [] # Link 0 + Route
    title_lines = []
    chg_mult_line = ""
    footer_lines = []
    
    state = 'header'
    
    for line in lines:
        stripped = line.strip()
        
        if state == 'header':
            header_lines.append(line.rstrip())
            if stripped.startswith('#'):
                state = 'route_end_check'
        
        elif state == 'route_end_check':
            # Gaussian requires a blank line after route
            if not stripped:
                state = 'title'
            elif stripped.startswith('---'): # Handle separators
                state = 'title'
            else:
                # Still in route (multi-line) or comments
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
            # If blank, ignore (allow multiple blanks before charge)
            
        elif state == 'geom':
            # Skip the geometry in the input file (we will use the LOG geometry)
            # We look for the blank line ending the geometry block
            if not stripped:
                state = 'footer'
                
        elif state == 'footer':
            # Collect everything else (Basis sets, ModRedundant, etc.)
            footer_lines.append(line.rstrip())

    # Separate Link0 and Route for processing
    link0_cmds = [l for l in header_lines if l.strip().startswith('%')]
    route_lines = [l for l in header_lines if l.strip().startswith('#') or (l.strip() and not l.strip().startswith('%'))]
    route_section = " ".join(route_lines)

    return link0_cmds, route_section, title_lines, chg_mult_line, footer_lines

# --- 3. Parse Log (Optimized Geometry Only) ---
def parse_log_geometry(filepath):
    """
    Parses the Gaussian log file to find the FINAL Optimized Geometry.
    """
    with open(filepath, 'r') as f:
        lines = f.readlines()

    atoms = []
    
    # Find the last occurrence of standard orientation
    start_indices = [i for i, line in enumerate(lines) if "Standard orientation:" in line]
    if not start_indices:
        start_indices = [i for i, line in enumerate(lines) if "Input orientation:" in line]
    
    if not start_indices:
        raise ValueError("Could not find coordinate table in log file.")

    last_table_start = start_indices[-1]
    
    current_idx = last_table_start + 5
    while True:
        if current_idx >= len(lines): break
        line = lines[current_idx]
        if "----------------" in line:
            break
        
        parts = line.split()
        if len(parts) >= 6:
            atomic_num = int(parts[1])
            symbol = get_atomic_symbol(atomic_num)
            x = float(parts[3])
            y = float(parts[4])
            z = float(parts[5])
            atoms.append(f" {symbol:<2} {x:>14.8f} {y:>14.8f} {z:>14.8f}")
        
        current_idx += 1

    return atoms

# --- 4. Fallback Log Parser (If .inp missing) ---
def parse_log_fallback(filepath):
    # This is the "robust" log parser from previous version as a backup
    with open(filepath, 'r') as f:
        lines = f.readlines()
        
    link0_cmds = []
    route_section = ""
    chg_mult_line = ""
    
    # Header
    capturing_route = False
    for line in lines[:100]:
        s = line.strip()
        if s.startswith('%'): link0_cmds.append(s)
        if s.startswith('#'): 
            capturing_route = True
            route_section += s
            continue
        if capturing_route:
            if s.startswith('---') or not s: capturing_route = False
            else: route_section += " " + s

    # Charge/Mult
    for line in lines:
        if "Charge =" in line and "Multiplicity =" in line:
            parts = line.split()
            try:
                c = parts[parts.index("Charge")+2]
                m = parts[parts.index("Multiplicity")+2]
                chg_mult_line = f"{c} {m}"
                break
            except: continue
            
    # Footer (Using the simplified robust logic)
    # ... (Logic omitted for brevity in fallback, usually not needed if .inp exists)
    return link0_cmds, route_section, [f"IRC from {filepath}"], chg_mult_line, []

# --- 5. Output Generation ---
def process_route_for_irc(route_line):
    new_route = route_line
    # Remove Opt, Freq, QST keywords
    new_route = re.sub(r'opt(=|\s+|\s*\().*?\)', '', new_route, flags=re.IGNORECASE) 
    new_route = re.sub(r'opt(=|\s+)\w+', '', new_route, flags=re.IGNORECASE)
    new_route = re.sub(r'\bopt\b', '', new_route, flags=re.IGNORECASE)
    new_route = re.sub(r'freq(=|\s+|\s*\().*?\)', '', new_route, flags=re.IGNORECASE)
    new_route = re.sub(r'freq(=|\s+)\w+', '', new_route, flags=re.IGNORECASE)
    new_route = re.sub(r'\bfreq\b', '', new_route, flags=re.IGNORECASE)
    new_route = re.sub(r'qst\d', '', new_route, flags=re.IGNORECASE)

    new_route = " ".join(new_route.split())
    new_route = new_route.replace("SCF=( ", "SCF=(")
    
    irc_cmd = "IRC=(CalcFC,MaxPoints=30,StepSize=10)"
    return f"{new_route} {irc_cmd}"

def get_irc_filename(filepath):
    base = os.path.splitext(os.path.basename(filepath))[0]
    new_base = base
    while True:
        prev_base = new_base
        new_base = re.sub(r'_(qst[23]|opt|ts|guess)$', '', new_base, flags=re.IGNORECASE)
        if new_base == prev_base: break
    return f"{new_base}_irc.inp"

def write_job_file(filename, link0, route, title, chg_mult, atoms, footer):
    with open(filename, 'w') as f:
        for l in link0: f.write(f"{l}\n")
        f.write(f"{route}\n\n")
        
        for t in title: f.write(f"{t}\n")
        f.write("\n")
        
        f.write(f"{chg_mult}\n")
        for a in atoms: f.write(f"{a}\n")
        f.write("\n")
        
        if footer:
            for line in footer: f.write(f"{line}\n")
            f.write("\n") # Ensure EOF newline

def main():
    log_header("Gaussian IRC Input Generator")

    if len(sys.argv) < 2:
        log_error("Missing argument.")
        print(" Usage: python gaussian_irc_prep.py <gaussian_output_file.log>")
        sys.exit(1)

    log_file = sys.argv[1]
    log_info(f"Log File:   {log_file}")
    
    # 1. Get Optimized Geometry from Log
    try:
        atoms = parse_log_geometry(log_file)
        log_success(f"Extracted {len(atoms)} optimized atoms from Log")
    except Exception as e:
        log_error(f"Failed to read geometry from log: {e}")
        sys.exit(1)

    # 2. Find and Parse Input File (Preferred Method)
    inp_file = find_input_file(log_file)
    
    if inp_file:
        log_success(f"Found Input: {inp_file}")
        try:
            link0, route, title, chg_mult, footer = parse_original_input(inp_file)
            log_success("Extracted Header/Footer from Input file")
        except Exception as e:
            log_error(f"Failed parsing input file: {e}")
            sys.exit(1)
    else:
        log_error("Original .inp/.gjf file not found in directory.")
        log_info("Falling back to Log file echo parsing (Less reliable)")
        link0, route, title, chg_mult, footer = parse_log_fallback(log_file)

    # 3. Construct Output
    out_file = get_irc_filename(log_file)
    chk_name = os.path.splitext(out_file)[0] + ".chk"
    
    # Update Checkpoint
    new_link0 = [l for l in link0 if not l.lower().startswith('%chk')]
    new_link0.insert(0, f"%chk={chk_name}")

    # Process Route
    final_route = process_route_for_irc(route)

    # Write
    log_info(f"Writing to: {out_file}")
    try:
        write_job_file(out_file, new_link0, final_route, title, chg_mult, atoms, footer)
        log_success("File generation complete.")
    except Exception as e:
        log_error(f"Writing failed: {e}")
        sys.exit(1)

    log_header("Done")

if __name__ == "__main__":
    main()
