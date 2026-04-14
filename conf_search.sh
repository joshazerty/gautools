#!/bin/bash

xtb start.xyz --opt --gfn2 --chrg -1 --uhf 0 --T 8
crest xtbopt.xyz --gfn2 --chrg -1 --uhf 0 --T 8 --nci --ewi
crest --cregen crest_conformers.xyz --ewin 6.0 --rthr 0.125
L=$(wc -l < start.xyz)
head -n $((10 * (${L}))) crest_ensemble.xyz > top10.xyz
python3 -c "
from ase.io import read,write
a=read('top10.xyz',':')
for i in range(10):
  write(str(i+1)+'.xyz',a[i])"
for i in {1..10}; do xtb ${i}.xyz --opt tight --gfn2 --chrg -1 --uhf 0; mv xtbopt.xyz ${i}_opt.xyz;  done
python3 ~/tools/xyz2inp.py
for i in {1..10}; do subgau16 --memory 32 --cpus 8 --queue m0311 --input ${i}.inp; done

