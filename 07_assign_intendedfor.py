"""Assign IntendedFor and related metadata fields."""

import json
import os
from glob import glob

if __name__ == "__main__":
    dset_dir = "/cbica/projects/mebold/dset/"
    subject_dirs = sorted(glob(os.path.join(dset_dir, "sub-*")))
    for subject_dir in subject_dirs:
        subject = os.path.basename(subject_dir)

        session_dirs = sorted(glob(os.path.join(subject_dir, "ses-*")))
        for session_dir in session_dirs:
            session = os.path.basename(session_dir)
            prefix = f"{subject}_{session}"

            fmap_dir = os.path.join(session_dir, "fmap")
            func_dir = os.path.join(session_dir, "func")

            # Remove intendedfor-related fields from multi-echo field maps.
            me_fmaps = sorted(
                glob(os.path.join(fmap_dir, "*_acq-ME*_echo-*_sbref.json"))
                + glob(os.path.join(fmap_dir, "*_acq-ME*_echo-*_epi.json"))
            )
            for me_fmap in me_fmaps:
                with open(me_fmap, "r") as fo:
                    json_metadata = json.load(fo)

                if "B0FieldIdentifier" in json_metadata.keys():
                    json_metadata.pop("B0FieldIdentifier")

                if "B0FieldSource" in json_metadata.keys():
                    json_metadata.pop("B0FieldSource")

                if "IntendedFor" in json_metadata.keys():
                    json_metadata.pop("IntendedFor")

                os.remove(me_fmap)
                with open(me_fmap, "w") as fo:
                    json.dump(json_metadata, fo, sort_keys=True, indent=4)

            # Add intendedfor-related fields to single-echo field maps.
            se_fmaps = sorted(glob(os.path.join(fmap_dir, "*_dir-AP_epi.json")))
            for ap_fmap in se_fmaps:
                pa_fmap = ap_fmap.replace("_dir-AP_", "_dir-PA_")
                with open(ap_fmap, "r") as fo:
                    ap_metadata = json.load(fo)

                with open(pa_fmap, "r") as fo:
                    pa_metadata = json.load(fo)

                b0fieldname = f"{prefix}_{ap_metadata['ProtocolName'].replace('_dir-AP', '')}"
                b0fieldname = b0fieldname.replace(":", "_").replace("-", "_")

                if "acq-ME" in ap_fmap:
                    acq = "MBME"
                elif "acq-SESE" in ap_fmap:
                    acq = "MBSE"
                else:
                    raise Exception(f"What is {ap_fmap}?")

                target_files = sorted(
                    glob(os.path.join(func_dir, f"*acq-{acq}*bold.nii.gz"))
                )
                target_jsons = [f.replace(".nii.gz", ".json") for f in target_files]
                ap_metadata["B0FieldIdentifier"] = [b0fieldname]
                pa_metadata["B0FieldIdentifier"] = [b0fieldname]
                # TODO: Fix paths
                # target_filenames = [
                #     "bids::" + tf.replace(dset_dir, "") for tf in target_files
                # ]
                # ap_metadata["IntendedFor"] = target_filenames
                # pa_metadata["IntendedFor"] = target_filenames

                os.remove(ap_fmap)
                with open(ap_fmap, "w") as fo:
                    json.dump(ap_metadata, fo, sort_keys=True, indent=4)

                os.remove(pa_fmap)
                with open(pa_fmap, "w") as fo:
                    json.dump(pa_metadata, fo, sort_keys=True, indent=4)

                for target_json in target_jsons:
                    with open(target_json, "r") as fo:
                        target_metadata = json.load(fo)

                    # if "B0FieldSource" not in target_metadata.keys():
                    target_metadata["B0FieldSource"] = []

                    if "MESE" in b0fieldname or "SESE" in b0fieldname:
                        target_metadata["B0FieldSource"].append(b0fieldname)

                    os.remove(target_json)
                    with open(target_json, "w") as fo:
                        json.dump(target_metadata, fo, sort_keys=True, indent=4)
