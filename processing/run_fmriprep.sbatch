#!/bin/bash
#SBATCH --job-name=fmriprep
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=2-12
#SBATCH --cpus-per-task=20
#SBATCH --mem-per-cpu=4gb
#SBATCH --time=48:00:00
# Outputs ----------------------------------
#SBATCH --output=/cbica/projects/pafin/code/processing/jobs/fmriprep_%A-%a.out
#SBATCH --error=/cbica/projects/pafin/code/processing/jobs/fmriprep_%A-%a.err
# ------------------------------------------

pwd; hostname; date
set -e

#==============Shell script==============#
# Location of the *reduced* BIDS dataset
BIDS_DIR="/cbica/projects/pafin/dset"
CODE_DIR="/cbica/projects/pafin/code"
SCRATCH_DIR="/cbica/comp_space/pafin/pafin-fmriprep"
DERIVS_DIR="/cbica/projects/pafin/derivatives/fmriprep"
mkdir -p ${SCRATCH_DIR}
mkdir -p ${DERIVS_DIR}

# Make sure FS_LICENSE is defined in the container.
FS_LICENSE="/cbica/projects/pafin/tokens/freesurfer_license.txt"

# Parse the participants.tsv file and extract one subject ID from the line corresponding to this SLURM task.
subject=$( sed -n -E "$((${SLURM_ARRAY_TASK_ID} + 1))s/sub-(\S*)\>.*/\1/gp" ${BIDS_DIR}/participants.tsv )

cmd="apptainer run --home $HOME --cleanenv --containall --writable-tmpfs \
      -B ${BIDS_DIR}:/data \
      -B ${DERIVS_DIR}:/out \
      -B ${SCRATCH_DIR}:/work \
      -B ${CODE_DIR}:/code \
      -B ${FS_LICENSE}:/license.txt \
      /cbica/projects/pafin/apptainer/fmriprep-24.1.1.sif \
      /data \
      /out \
      participant \
      --participant-label ${subject} \
      -w /work \
      --omp-nthreads ${SLURM_CPUS_PER_TASK} \
      --nprocs ${SLURM_CPUS_PER_TASK} \
      --mem_mb 39000 \
      --output-spaces func T1w MNI152NLin6Asym:res-2 \
      --output-layout bids \
      --me-output-echos \
      --project-goodvoxels \
      --cifti-output 91k \
      --bids-filter-file /code/processing/filter.json \
      --fs-license-file /license.txt \
      --skip_bids_validation \
      --level full"

# Setup done, run the command
echo Running task "${SLURM_ARRAY_TASK_ID}"
echo Commandline: "$cmd"
eval "$cmd"
exitcode=$?

# Output results to a table
echo "sub-$subject   ${SLURM_ARRAY_TASK_ID}    $exitcode" \
      >> ${CODE_DIR}/jobs/"${SLURM_JOB_NAME}"."${SLURM_ARRAY_JOB_ID}".tsv
echo Finished tasks "${SLURM_ARRAY_TASK_ID}" with exit code $exitcode
exit $exitcode
