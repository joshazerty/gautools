# gautools

A Python package providing command-line tools for [Gaussian 16](https://gaussian.com/) quantum chemistry workflows. Covers the full transition-state search pipeline: geometry conversion, relaxed scan analysis, TS optimisation, IRC path following, endpoint optimisation, and batch energy analysis.

## Installation

```bash
git clone https://github.com/joshazerty/gautools.git
cd gautools
pip install -e .           # core tools only (no scan2qst2)
pip install -e ".[scan]"   # include cclib/numpy/matplotlib for scan2qst2
```

## Typical workflow

```
XYZ files ──► xyz2inp ──► Gaussian Opt/Freq
                                │
                     scan2qst2 (relaxed scan → QST2 guess)
                                │
                         Gaussian QST2/QST3/TS
                                │
                            ts2irc ──► Gaussian IRC
                                            │
                                       irc2opt ──► Gaussian Opt+Freq
                                                   (fwd & rev endpoints)

At any stage: gau2xyz any.log    # extract geometry → XYZ
              gau-status *.log   # batch job status table
              gau-energy *.log   # thermochemical energy table
```

---

## Commands

### `gau2xyz`
Extract the final geometry from one or more Gaussian log files.

```bash
gau2xyz calc.log
gau2xyz ts1.log ts2.log ts3.log          # batch
gau2xyz --frame all opt.log              # every geometry step → multi-frame XYZ
gau2xyz --no-warn-imag opt.log           # suppress imaginary freq warning
```
Output: `<basename>.xyz` per file.

---

### `ts2irc`
Set up an IRC calculation from a converged TS log.

```bash
ts2irc ts_opt.log
ts2irc ts.log --inp ts.inp               # explicit input file
ts2irc ts.log --irc-opts "CalcFC,MaxPoints=50,StepSize=5"
```
Reads route/basis/charge from the matching `.inp`/`.gjf`/`.com`. Removes `Opt`/`Freq`/`QST` keywords, appends `IRC=(...)`.  
Output: `<clean_basename>_irc.inp`

---

### `irc2opt`
Create Opt+Freq input files for both IRC endpoints.

```bash
irc2opt ts_irc.log
irc2opt ts_irc.log --suffix-fwd _fwd --suffix-rev _rev
```
Uses `Following the Reaction Path in the FORWARD/REVERSE direction` markers for reliable endpoint assignment. Falls back to first/last frame if markers are absent.  
Output: `<basename>_irc_fwd.inp` and `<basename>_irc_rev.inp`

---

### `scan2qst2`
Parse a relaxed scan log, plot the PES, and optionally write a QST2 input.

```bash
scan2qst2 scan.log
scan2qst2 scan.log --no-plot --qst2      # headless: skip plot, always write QST2
scan2qst2 scan.log --output my_qst2.gjf
```
Requires `gautools[scan]` extras. Detects Bond/Angle/Dihedral scan type automatically from the matching `.inp` file.  
Output: interactive PES plot + `<basename>_qst2.gjf`

---

### `xyz2inp`
Convert XYZ file(s) to Gaussian input files.

```bash
xyz2inp mol.xyz
xyz2inp conf1.xyz conf2.xyz conf3.xyz    # batch
xyz2inp mol.xyz --charge 0 --mult 1
xyz2inp mol.xyz --template other.inp
```
Uses a 4-tier template system (see [Template system](#template-system) below).  
Output: `<basename>.inp` per file.

---

### `gau-status`  *(new)*
Batch status check — report termination status, atom count, and imaginary frequencies.

```bash
gau-status                               # scan CWD for *.log
gau-status ts-*.log
gau-status /path/to/calcs/
gau-status --csv *.log > results.csv
```

Example output:
```
File                     Status      Atoms  Imaginary Freqs
ts-11.log                Normal         37  1  (-64.2 cm⁻¹)
ts-11_irc.log            Normal         37  —
ts-11_bis.log            Error           —  —
ts-11_preopt.log         Incomplete     37  —
```
Exit code 1 if any files did not terminate normally (useful in shell scripts after batch jobs).

---

### `gau-energy`  *(new)*
Extract and compare thermochemical energies.

```bash
gau-energy ts-11.log ts-11_irc_fwd_opt.log ts-11_irc_rev_opt.log
gau-energy *.log --sort g                # sort by Gibbs energy
gau-energy *.log --unit kj --csv        # kJ/mol, CSV output
gau-energy *.log --ref reactant.log     # set reference explicitly
```

Example output:
```
File                       SCF (Ha)      ZPE (Ha)    G (Ha)   ΔG (kcal/mol)
ts-11_irc_rev_opt.log   -882.200883    0.263585  -881.985         0.0
ts-11.log               -882.198621    0.263012  -881.982        +1.9
ts-11_irc_fwd_opt.log   -882.193441    0.262198  -881.975        +6.3
```

---

### `gautools` (umbrella group)

All commands are also accessible under the `gautools` group:

```bash
gautools --help
gautools gau2xyz ts.log
gautools gau-status *.log
gautools init                  # create ~/.gautools/template.inp
```

---

## Template system

`xyz2inp` picks up its route section, charge/multiplicity, and basis set footer from the first `template.inp` it finds, in this order:

| Priority | Location | How to use |
|---|---|---|
| 1 | `--template path/to/file.inp` | explicit CLI flag |
| 2 | `./template.inp` or XYZ file directory | place a template in your project dir |
| 3 | `~/.gautools/template.inp` | your personal default |
| 4 | Built-in | Re/B3LYP-D3BJ/def2SVP+SDD/PCM(1-Pentanol), charge -1 1 |

A template file is a normal Gaussian input with an **empty geometry block** — take any working `.inp`, delete the coordinates, and save as `template.inp`:

```bash
gautools init    # writes ~/.gautools/template.inp from the built-in default
```

The `%mem`, `%NProcShared`, and `%chk` values in any generated input are overwritten at job submission time by the `subgau16` script.

---

## Dependencies

| Command | Extra deps needed |
|---|---|
| `gau2xyz`, `ts2irc`, `irc2opt`, `xyz2inp`, `gau-status`, `gau-energy` | none (stdlib + click) |
| `scan2qst2` | `cclib`, `numpy`, `matplotlib` |

```bash
pip install gautools[scan]    # install with scan dependencies
```

---

## Package structure

```
src/gautools/
├── _constants.py      # PERIODIC_TABLE (single source of truth)
├── _console.py        # coloured output helpers
├── route.py           # route keyword manipulation
├── template.py        # template resolution system
├── parsers/
│   ├── log.py         # Gaussian log parser (geometry, freq, energies, IRC)
│   ├── inp.py         # Gaussian input parser and writer
│   └── xyz.py         # XYZ reader/writer
└── commands/          # one module per CLI command
```

## Running tests

```bash
pip install -e ".[dev]"
pytest
pytest --cov=gautools --cov-report=term-missing
```
