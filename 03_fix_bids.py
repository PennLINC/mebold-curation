"""Fix BIDS files after heudiconv conversion.

This script should deal with steps 1-6 below.

The necessary steps are:

1.  Deal with duplicates.
2.  Rename multi-echo magnitude BOLD files to part-mag_bold.
3.  Rename phase files to part-phase_bold.
4.  Split out noRF noise scans from multi-echo BOLD scans.
    -   Also copy the JSON.
5.  Copy first echo of each multi-echo field map without echo entity.
6.  Update filenames in the scans.tsv files.
7.  Remove events files.
"""

import os
import shutil
from glob import glob

import nibabel as nb
import pandas as pd

# Number of EPI noise scans to split out of the BOLD scans.
N_NOISE_VOLS = 3

FULL_RUN_LENGTHS = (240, 204, 200)


if __name__ == "__main__":
    dset_dir = "/cbica/projects/mebold/dset/"
    subject_dirs = sorted(glob(os.path.join(dset_dir, "sub-*")))
    for subject_dir in subject_dirs:
        sub_id = os.path.basename(subject_dir)
        session_dirs = sorted(glob(os.path.join(subject_dir, "ses-*")))
        for session_dir in session_dirs:
            ses_id = os.path.basename(session_dir)
            anat_dir = os.path.join(session_dir, "anat")
            fmap_dir = os.path.join(session_dir, "fmap")
            func_dir = os.path.join(session_dir, "func")

            # Remove empty events files created by heudiconv
            events_files = sorted(glob(os.path.join(func_dir, "*_events.tsv")))
            for events_file in events_files:
                os.remove(events_file)

            # Load scans file
            scans_file = os.path.join(session_dir, f"{sub_id}_{ses_id}_scans.tsv")
            assert os.path.isfile(scans_file), f"Scans file DNE: {scans_file}"
            scans_df = pd.read_table(scans_file)

            # Heudiconv's reproin heuristic currently (as of v1.2.0) names magnitude and phase
            # files as _bold and _phase, respectively.
            # The better way to do it is to call them part-mag_bold and part-phase_bold.
            mag_files = sorted(glob(os.path.join(func_dir, "*echo-*_bold.*")))
            for mag_file in mag_files:
                if "part-" in mag_file:
                    print(f"Skipping {mag_file}")
                    continue

                new_mag_file = mag_file.replace("_bold.", "_part-mag_bold.")
                os.rename(mag_file, new_mag_file)

                mag_filename = os.path.join("func", os.path.basename(mag_file))
                new_mag_filename = os.path.join("func", os.path.basename(new_mag_file))

                # Replace the filename in the scans.tsv file
                scans_df = scans_df.replace({"filename": {mag_filename: new_mag_filename}})

            # Rename phase files from _phase to _part-phase_bold.
            phase_files = sorted(glob(os.path.join(func_dir, "*_phase.*")))
            for phase_file in phase_files:
                new_phase_file = phase_file.replace("_phase.", "_part-phase_bold.")
                os.rename(phase_file, new_phase_file)

                phase_filename = os.path.join("func", os.path.basename(phase_file))
                new_phase_filename = os.path.join("func", os.path.basename(new_phase_file))

                # Replace the filename in the scans.tsv file
                scans_df = scans_df.replace({"filename": {phase_filename: new_phase_filename}})

            # Split out noise scans from all multi-echo BOLD files.
            # There is no metadata to distinguish noise scans from BOLD scans,
            # so we need to hardcode the number of noise scans to split out.
            # In order to handle partial scans where the last N volumes aren't noise scans,
            # we also need to hardcode valid scan lengths.
            me_bolds = sorted(glob(os.path.join(func_dir, "*acq-MBME*_bold.nii.gz")))
            for me_bold in me_bolds:
                noise_scan = me_bold.replace("_bold.nii.gz", "_noRF.nii.gz")
                if os.path.isfile(noise_scan):
                    print(f"File exists: {os.path.basename(noise_scan)}")
                    continue

                img = nb.load(me_bold)
                n_vols = img.shape[-1]
                if n_vols not in FULL_RUN_LENGTHS:
                    print(f"File is a partial scan: {os.path.basename(me_bold)}")
                    continue

                noise_img = img.slicer[..., -N_NOISE_VOLS:]
                bold_img = img.slicer[..., :-N_NOISE_VOLS]

                # Overwrite the BOLD scan
                os.remove(me_bold)
                bold_img.to_filename(me_bold)
                noise_img.to_filename(noise_scan)

                # Copy the JSON as well
                shutil.copyfile(
                    me_bold.replace(".nii.gz", ".json"),
                    noise_scan.replace(".nii.gz", ".json"),
                )

                # Add noise scans to scans DataFrame
                i_row = len(scans_df.index)
                me_bold_fname = os.path.join("func", os.path.basename(me_bold))
                noise_fname = os.path.join("func", os.path.basename(noise_scan))
                scans_df.loc[i_row] = scans_df.loc[scans_df["filename"] == me_bold_fname].iloc[0]
                scans_df.loc[i_row, "filename"] = noise_fname

            # In this protocol, we have multi-echo field maps.
            # In practice, multi-echo field maps aren't useful, so we just grab the first echo's
            # data and label it as a single-echo field map.
            # Copy first echo's sbref of multi-echo field maps without echo entity.
            me_fmaps = sorted(glob(os.path.join(fmap_dir, "*_acq-ME*_echo-1_sbref.*")))
            for me_fmap in me_fmaps:
                out_fmap = me_fmap.replace("_echo-1_", "_").replace("_sbref", "_epi")
                if os.path.isfile(out_fmap):
                    print(f"File exists: {os.path.basename(out_fmap)}")
                    continue

                me_fmap_fname = os.path.join("fmap", os.path.basename(me_fmap))
                out_fmap_fname = os.path.join("fmap", os.path.basename(out_fmap))
                shutil.copyfile(me_fmap, out_fmap)
                if me_fmap.endswith(".nii.gz"):
                    i_row = len(scans_df.index)
                    scans_df.loc[i_row] = scans_df.loc[
                        scans_df["filename"] == me_fmap_fname
                    ].iloc[0]
                    scans_df.loc[i_row, "filename"] = out_fmap_fname

            # Save out the modified scans.tsv file.
            scans_df = scans_df.sort_values(by=["acq_time", "filename"])
            os.remove(scans_file)
            scans_df.to_csv(scans_file, sep="\t", na_rep="n/a", index=False)
