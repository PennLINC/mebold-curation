#!/bin/bash
#SBATCH --job-name=xcpd
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=1-12
#SBATCH --cpus-per-task=20
#SBATCH --mem-per-cpu=4gb
#SBATCH --time=36:00:00
# Outputs ----------------------------------
#SBATCH --output=/cbica/projects/pafin/code/processing/jobs/xcpd_%A-%a.out
#SBATCH --error=/cbica/projects/pafin/code/processing/jobs/xcpd_%A-%a.err
# ------------------------------------------

pwd; hostname; date
set -e

#==============Shell script==============#
# Location of the *reduced* BIDS dataset
BIDS_DIR="/cbica/projects/pafin/dset"
INPUT_DIR="/cbica/projects/pafin/derivatives"
CODE_DIR="/cbica/projects/pafin/code"
SCRATCH_DIR="/cbica/comp_space/pafin/pafin-xcp_d"
DERIVS_DIR="/cbica/projects/pafin/derivatives/xcp_d"
mkdir -p ${SCRATCH_DIR}
mkdir -p ${DERIVS_DIR}

# Parse the participants.tsv file and extract one subject ID from the line corresponding to this SLURM task.
subject=$( sed -n -E "$((${SLURM_ARRAY_TASK_ID} + 1))s/sub-(\S*)\>.*/\1/gp" ${BIDS_DIR}/participants.tsv )

# Compose the command line
cmd="apptainer run --cleanenv \
    -B ${INPUT_DIR}:/data \
    -B ${DERIVS_DIR}:/out \
    -B ${SCRATCH_DIR}:/work \
    -B ${CODE_DIR}:/code \
    /cbica/projects/pafin/apptainer/xcp_d-0.10.6.sif \
    /data/fmriprep \
    /out \
    participant \
    --datasets tedana_aroma=/data/tedana+aroma \
    --participant-label ${subject} \
    -w /work/ \
    --omp-nthreads ${SLURM_CPUS_PER_TASK} \
    --nprocs ${SLURM_CPUS_PER_TASK} \
    --mem-gb 79 \
    --mode linc \
    --dummy-scans auto \
    --nuisance-regressors /code/processing/xcp_d_tedana+aroma+gsr.yml"

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
