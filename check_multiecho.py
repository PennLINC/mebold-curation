"""Check that multi-echo scans are the right length."""

from bids import BIDSLayout
from bids.layout import Query
import nibabel as nb

layout = BIDSLayout("/cbica/projects/mebold/dset", validate=False)
files = layout.get(
    echo=1,
    reconstruction=Query.NONE,
    part="mag",
    suffix=["noRF", "bold"],
    extension=["nii.gz"],
)
for f in files:
    print(f.filename)
    size_check = {}
    file_entities = f.get_entities(metadata=False)
    file_entities["reconstruction"] = Query.NONE
    for i_echo in range(1, 6):
        file_entities["echo"] = i_echo
        echo_file = layout.get(**file_entities)
        if len(echo_file) != 1:
            raise ValueError(
                f"Something's wrong with {file_entities}\n{len(echo_file)} files found:"
                f"\n{echo_file}"
            )

        img_size = nb.load(echo_file[0].path).shape
        size_check[f"mag_{i_echo}"] = img_size

    file_entities["part"] = "phase"

    for i_echo in range(1, 6):
        file_entities["echo"] = i_echo
        echo_file = layout.get(**file_entities)
        if len(echo_file) != 1:
            raise ValueError(
                f"Something's wrong with {file_entities}\n{len(echo_file)} files found:"
                f"\n{echo_file}"
            )

        img_size = nb.load(echo_file[0].path).shape
        size_check[f"phase_{i_echo}"] = img_size

    test_size = size_check["mag_1"]
    if (len(test_size) != 4) or (test_size[3] == 0):
        print(f"Size of {f.filename} is bad: ({test_size})")

    for k, v in size_check.items():
        if test_size != v:
            print(f"Size of {k} ({v}) != {f.filename} ({test_size})")
