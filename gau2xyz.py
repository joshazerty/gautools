#!/usr/bin/env python3
import sys
import os
import re

# --- Configuration for Professional Output ---
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Symbols
TICK = f"{Colors.OKGREEN}✔{Colors.ENDC}"
CROSS = f"{Colors.FAIL}✘{Colors.ENDC}"
WARN  = f"{Colors.WARNING}⚠{Colors.ENDC}"
INFO  = f"{Colors.OKCYAN}ℹ{Colors.ENDC}"

# Periodic Table Mapping (Atomic Number -> Symbol)
PERIODIC_TABLE = {
    1: "H", 2: "He", 3: "Li", 4: "Be", 5: "B", 6: "C", 7: "N", 8: "O", 9: "F", 10: "Ne",
    11: "Na", 12: "Mg", 13: "Al", 14: "Si", 15: "P", 16: "S", 17: "Cl", 18: "Ar", 19: "K", 20: "Ca",
    21: "Sc", 22: "Ti", 23: "V", 24: "Cr", 25: "Mn", 26: "Fe", 27: "Co", 28: "Ni", 29: "Cu", 30: "Zn",
    31: "Ga", 32: "Ge", 33: "As", 34: "Se", 35: "Br", 36: "Kr", 37: "Rb", 38: "Sr", 39: "Y", 40: "Zr",
    41: "Nb", 42: "Mo", 43: "Tc", 44: "Ru", 45: "Rh", 46: "Pd", 47: "Ag", 48: "Cd", 49: "In", 50: "Sn",
    51: "Sb", 52: "Te", 53: "I", 54: "Xe", 55: "Cs", 56: "Ba", 57: "La", 58: "Ce", 59: "Pr", 60: "Nd",
    61: "Pm", 62: "Sm", 63: "Eu", 64: "Gd", 65: "Tb", 66: "Dy", 67: "Ho", 68: "Er", 69: "Tm", 70: "Yb",
    71: "Lu", 72: "Hf", 73: "Ta", 74: "W", 75: "Re", 76: "Os", 77: "Ir", 78: "Pt", 79: "Au", 80: "Hg",
    81: "Tl", 82: "Pb", 83: "Bi", 84: "Po", 85: "At", 86: "Rn", 87: "Fr", 88: "Ra", 89: "Ac", 90: "Th",
    91: "Pa", 92: "U", 93: "Np", 94: "Pu", 95: "Am", 96: "Cm", 97: "Bk", 98: "Cf", 99: "Es", 100: "Fm",
    101: "Md", 102: "No", 103: "Lr"
}

def get_xyz_filename(log_filename):
    """Generates the output XYZ filename based on input."""
    base, _ = os.path.splitext(log_filename)
    return f"{base}.xyz"

def extract_and_convert(filepath):
    """
    Parses Gaussian log file.
    Returns: (is_terminated_normally, atom_list)
    atom_list format: [(Symbol, X, Y, Z), ...]
    """
    if not os.path.exists(filepath):
        print(f"{CROSS} File '{filepath}' not found.")
        sys.exit(1)

    print(f"{INFO} Reading file: {Colors.BOLD}{filepath}{Colors.ENDC}")

    normal_termination = False
    atoms = []
    
    # Regex to capture the geometry lines
    # Example line:    1          6           0        0.000000    0.000000    0.000000
    atom_regex = re.compile(r'^\s+\d+\s+(\d+)\s+\d+\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)')

    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            
        # 1. Check for Normal Termination
        # We check the last few lines (Gaussian usually puts it at the very end)
        for line in lines[-20:]: 
            if "Normal termination" in line:
                normal_termination = True
                break
        
        # 2. Extract Geometry
        # We look for "Standard orientation" (preferred) or "Input orientation"
        # We iterate through the whole file and keep overwriting 'atoms' 
        # so we end up with the LAST frame.
        
        i = 0
        while i < len(lines):
            if "Standard orientation:" in lines[i] or "Input orientation:" in lines[i]:
                current_frame_atoms = []
                # The actual coordinates start 5 lines down from the header
                # Header:
                # -----------------------------------------
                # Center     Atomic ...
                # Number     Number ...
                # -----------------------------------------
                i += 5 
                
                while i < len(lines):
                    # Check for the dashes that end the block
                    if "----------------" in lines[i]:
                        break
                    
                    match = atom_regex.match(lines[i])
                    if match:
                        atomic_num = int(match.group(1))
                        x = float(match.group(2))
                        y = float(match.group(3))
                        z = float(match.group(4))
                        
                        symbol = PERIODIC_TABLE.get(atomic_num, "X")
                        current_frame_atoms.append((symbol, x, y, z))
                    i += 1
                
                # If we successfully extracted atoms, update the main variable
                if current_frame_atoms:
                    atoms = current_frame_atoms
            i += 1

    except Exception as e:
        print(f"{CROSS} Error reading file: {e}")
        sys.exit(1)

    return normal_termination, atoms

def write_xyz(atoms, output_path, source_file):
    """Writes the atom list to an XYZ file."""
    try:
        with open(output_path, 'w') as f:
            f.write(f"{len(atoms)}\n")
            f.write(f"Generated from {source_file}\n")
            for atom in atoms:
                f.write(f"{atom[0]:<4} {atom[1]:12.6f} {atom[2]:12.6f} {atom[3]:12.6f}\n")
        return True
    except IOError as e:
        print(f"{CROSS} Failed to write XYZ: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print(f"{WARN} Usage: python log2xyz.py <gaussian_output_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = get_xyz_filename(input_file)

    # --- Processing ---
    terminated_correctly, atoms = extract_and_convert(input_file)

    # --- Reporting Termination Status ---
    if terminated_correctly:
        print(f"{TICK} Gaussian Status: {Colors.OKGREEN}Normal termination{Colors.ENDC}")
    else:
        print(f"{CROSS} Gaussian Status: {Colors.FAIL}Error / Incomplete{Colors.ENDC}")
        print(f"    {Colors.WARNING}(Extracting last available geometry regardless of error){Colors.ENDC}")

    # --- Reporting Extraction ---
    if atoms:
        print(f"{TICK} Geometry Extraction: {len(atoms)} atoms found")
        
        # --- Writing Output ---
        success = write_xyz(atoms, output_file, input_file)
        if success:
            print(f"{TICK} Output Saved: {Colors.OKBLUE}{output_file}{Colors.ENDC}")
        else:
            print(f"{CROSS} Output Failed.")
    else:
        print(f"{CROSS} Geometry Extraction: {Colors.FAIL}No geometry found in file{Colors.ENDC}")

if __name__ == "__main__":
    main()
