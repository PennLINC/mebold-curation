"""Remove unneeded fields from bottom-level JSON files."""

import json
import os
from glob import glob

if __name__ == "__main__":
    dset_dir = "/cbica/projects/mebold/dset/"
    drop_keys = [
        "AcquisitionTime",
        "CogAtlasID",
        "InstitutionAddress",
        "TaskName",
        "ImageComments",
    ]

    json_files = sorted(glob(os.path.join(dset_dir, "sub-*/ses-*/*/*.json")))
    for json_file in json_files:
        with open(json_file, "r") as fo:
            json_data = json.load(fo)

        for drop_key in drop_keys:
            if drop_key in json_data.keys():
                json_data.pop(drop_key)

        os.remove(json_file)
        with open(json_file, "w") as fo:
            json.dump(json_data, fo, indent=4, sort_keys=True)
