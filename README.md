# mebold-curation

Code to curate complex-valued, multi-echo BOLD data acquired with the CMRR sequence.

The code in this repo assumes the following:

1. The protocol was named according to ReproIn convention.
    - BOLD: `func_task-rest_acq-MBME_run-01`
    - BOLD field maps: `fmap-epi_acq-func_dir-AP`
        -   This assumes the BOLD field maps are multi-echo,
            even though we don't need multiple echoes for field maps.
    - T1w: `anat-T1w`
2. You are planning to download the DICOMs to CUBIC and convert them into a BIDS dataset with heudiconv.
    - DICOMs will go in `sourcedata/`.
    - BIDS-format data will go in `dset/`.
3. Raw data are on Flywheel, in the project `bbl/MEBOLD`.
4. Your CUBIC project directory is at `/cbica/projects/mebold`.

TODO: Create conda environment config file.
