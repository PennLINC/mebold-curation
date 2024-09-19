#!/bin/bash
# Reface T1w images using afni_refacer_run.
module load afni/2022_05_03

t1w_files=$(find /cbica/projects/mebold/dset/sub-*/ses-*/anat/*T1w.nii.gz)
for t1w_file in $t1w_files
do
    echo "$t1w_file"
    @afni_refacer_run \
        -input "${t1w_file}" \
        -mode_reface \
        -no_images \
        -overwrite \
        -prefix "${t1w_file}"
done
