#!/bin/bash
#SBATCH --job-name=aroma
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=1-12
#SBATCH --cpus-per-task=20
#SBATCH --mem-per-cpu=4gb
#SBATCH --time=48:00:00
# Outputs ----------------------------------
#SBATCH --output=/cbica/projects/pafin/code/processing/jobs/aroma_%A-%a.out
#SBATCH --error=/cbica/projects/pafin/code/processing/jobs/aroma_%A-%a.err
# ------------------------------------------

pwd; hostname; date
set -e

#==============Shell script==============#
# Location of the *reduced* BIDS dataset
BIDS_DIR="/cbica/projects/pafin/dset"
CODE_DIR="/cbica/projects/pafin/code"
SCRATCH_DIR="/cbica/comp_space/pafin/pafin-aroma-nordic"
DERIVS_DIR="/cbica/projects/pafin/derivatives"
mkdir -p ${SCRATCH_DIR}

# Make sure FS_LICENSE is defined in the container.
FS_LICENSE="/cbica/projects/pafin/tokens/freesurfer_license.txt"

# Parse the participants.tsv file and extract one subject ID from the line corresponding to this SLURM task.
subject=$( sed -n -E "$((${SLURM_ARRAY_TASK_ID} + 1))s/sub-(\S*)\>.*/\1/gp" ${BIDS_DIR}/participants.tsv )

cmd="apptainer run --home $HOME --cleanenv --containall --writable-tmpfs \
      -B ${DERIVS_DIR}:/deriv \
      -B ${SCRATCH_DIR}:/work \
      -B ${CODE_DIR}:/code \
      -B ${FS_LICENSE}:/license.txt \
      /cbica/projects/pafin/apptainer/fmripost_aroma-0.0.10.sif \
      /deriv/fmriprep \
      /deriv/fmripost_aroma \
      participant \
      --participant-label ${subject} \
      --denoising-method orthaggr \
      -w /work \
      --omp-nthreads ${SLURM_CPUS_PER_TASK} \
      --nprocs ${SLURM_CPUS_PER_TASK} \
      --mem_mb 79000 \
      --stop-on-first-crash"

# Setup done, run the command
echo Running task "${SLURM_ARRAY_TASK_ID}"
echo Commandline: "$cmd"
eval "$cmd"
exitcode=$?

# Output results to a table
echo "sub-$subject   ${SLURM_ARRAY_TASK_ID}    $exitcode" \
      >> ${CODE_DIR}/processing/jobs/"${SLURM_JOB_NAME}"."${SLURM_ARRAY_JOB_ID}".tsv
echo Finished tasks "${SLURM_ARRAY_TASK_ID}" with exit code $exitcode
exit $exitcode
