#!/bin/bash
# Loop over subjects and run heudiconv on each.
# Make sure to activate the conda environment with heudiconv installed before running this.

declare -a subjects=("ID1" "ID2")
for sub in "${subjects[@]}"
do
    echo "$sub"
    heudiconv \
        -f reproin \
        -o /cbica/projects/mebold/dset \
        -d "/cbica/projects/mebold/sourcedata/{subject}_{session}/*/*/*/*.dcm" \
        -s "$sub" \
        -ss 1 \
        --bids
done
