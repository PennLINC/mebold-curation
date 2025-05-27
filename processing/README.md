# Process multi-echo BOLD data with fMRIPrep, fMRIPost-AROMA, tedana, and XCP-D

The scripts in this directory are designed to process multi-echo BOLD data with fMRIPrep, fMRIPost-AROMA, tedana, and XCP-D.

## fMRIPrep

The first step is to run fMRIPrep. This is done by submitting the `run_fmriprep.sbatch` script to the SLURM job scheduler.

```bash
sbatch run_fmriprep.sbatch
```

## fMRIPost-AROMA

Next, we run fMRIPost-AROMA to apply ICA to the data and perform an initial classification of the components using the ICA-AROMA algorithm.

```bash
sbatch run_fmripost_aroma.sbatch
```

## tedana

Next, we run tedana to apply multi-echo denoising to the data,
using the individual echo outputs from fMRIPrep and the ICA mixing matrix from fMRIPost-AROMA.

```bash
sbatch run_tedana.sbatch
```

## XCP-D

Next, we run XCP-D to denoise the data, using the tedana+aroma-classified components and global signal as the nuisance regressors.

```bash
sbatch run_xcp_d.sbatch
```
