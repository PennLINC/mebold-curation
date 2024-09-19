"""Expand dicom zip files in order to run heudiconv."""

import os
import zipfile
from glob import glob

if __name__ == "__main__":
    zip_files = sorted(glob("/cbica/projects/mebold/sourcedata/*_*/*/*/*.dicom.zip"))
    for zip_file in zip_files:
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            zip_ref.extractall(os.path.dirname(zip_file))

        os.remove(zip_file)
