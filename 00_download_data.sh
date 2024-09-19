#!/bin/bash

# Flywheel project name
project="bbl/MEBOLD"

# List any subjects you want to download here
subjects="ID1 ID2"

# Include a path to your flywheel API token here
token=$(</cbica/home/salot/tokens/flywheel.txt)
fw login "$token"

# Navigate to the folder to which you want to download the data
cd /cbica/projects/mebold/sourcedata || exit

for subject in $subjects; do
    fw download --yes --zip "fw://${project}/${subject}"
done
