#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=90G
#SBATCH --time=48:00:00

# Activate the processing Python environment
mamba activate processing

python run_tedana.py
