"""Anonymize acquisition datetimes for a dataset.

Anonymize acquisition datetimes for a dataset. Works for both longitudinal
and cross-sectional studies. The time of day is preserved, but the first
scan is set to January 1st, 1800. In a longitudinal study, each session is
anonymized relative to the first session, so that time between sessions is
preserved.

Overwrites scan tsv files in dataset. Only run this *after* data collection
is complete for the study, especially if it's longitudinal.
"""

import os
from glob import glob

import pandas as pd
from dateutil import parser

if __name__ == "__main__":
    dset_dir = "/cbica/projects/mebold/dset"

    bl_dt = parser.parse("1800-01-01")

    subject_dirs = sorted(glob(os.path.join(dset_dir, "sub-*")))
    for subject_dir in subject_dirs:
        sub_id = os.path.basename(subject_dir)
        print(f"Processing {sub_id}")

        scans_files = sorted(glob(os.path.join(subject_dir, "ses-*/*_scans.tsv")))

        for i_ses, scans_file in enumerate(scans_files):
            ses_dir = os.path.dirname(scans_file)
            ses_name = os.path.basename(ses_dir)
            print(f"\t{ses_name}")

            df = pd.read_table(scans_file)
            if i_ses == 0:
                # Anonymize in terms of first scan for subject.
                first_scan = df["acq_time"].min()
                first_dt = parser.parse(first_scan.split("T")[0])
                diff = first_dt - bl_dt

            acq_times = df["acq_time"].apply(parser.parse)
            acq_times = (acq_times - diff).astype(str)
            df["acq_time"] = acq_times
            df["acq_time"] = df["acq_time"].str.replace(" ", "T")

            os.remove(scans_file)
            df.to_csv(
                scans_file,
                sep="\t",
                lineterminator="\n",
                na_rep="n/a",
                index=False,
            )
