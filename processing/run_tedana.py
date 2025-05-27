"""Run tedana using fMRIPrep and fMRIPost-AROMA outputs."""

import json
import os
from glob import glob

import nibabel as nb
import numpy as np
import pandas as pd
from nilearn import image, masking
from scipy import stats
from tedana.workflows import tedana_workflow


def minimum_image_regression(
    *,
    data_optcom: np.ndarray,
    mixing: np.ndarray,
    mask: np.ndarray,
    component_table: pd.DataFrame,
):
    """Perform minimum image regression (MIR) to remove T1-like effects from BOLD-like components.

    This is a slightly modified version of the minimum image regression function in tedana.
    The main difference is that I have dropped the io_generator and the function just returns
    the relevant outputs.

    Parameters
    ----------
    data_optcom : (S x T) array_like
        Optimally combined time series data
    mixing : (T x C) array_like
        Mixing matrix for converting input data to component space, where ``C``
        is components and ``T`` is the same as in ``data_optcom``
    mask : niimg
        Boolean mask array
    component_table : (C x X) :obj:`pandas.DataFrame`
        Component metric table. One row for each component, with a column for
        each metric. The index should be the component number.

    Returns
    -------
    t1_img : niimg
        T1-like effect 3D map
    glsig_df : :obj:`pandas.DataFrame`
        Global signal time series (1D)
    mixing_df : :obj:`pandas.DataFrame`
        Mixing matrix with T1-like effect removed.
        The columns are the component names, and the rows are the time series.

    Notes
    -----
    Minimum image regression operates by constructing a amplitude-normalized form of the multi-echo
    high Kappa (MEHK) time series from BOLD-like ICA components,
    and then taking the voxel-wise minimum over time.
    This "minimum map" serves as a voxel-wise estimate of the T1-like effect in the time series.
    From this minimum map, a T1-like global signal (i.e., a 1D time series) is estimated.
    The component time series in the mixing matrix are then corrected for the T1-like effect by
    regressing out the global signal time series from each.
    Finally, the multi-echo denoised (MEDN) and MEHK time series are reconstructed from the
    corrected mixing matrix and are written out to new files.
    """

    # Get accepted and ignored components
    # Tedana has removed the "ignored" classification,
    # so we must separate "accepted" components based on the classification tag(s).
    ignore_tags = ["low variance", "accept borderline"]
    pattern = "|".join(ignore_tags)  # Create a pattern that matches any of the ignore tags

    # Select rows where the 'classification_tags' column contains any of the ignore tags
    ign = component_table[
        component_table.classification_tags.str.contains(pattern, na=False, regex=True)
    ].index.values

    acc = component_table[component_table.classification == "accepted"].index.values
    # Ignored components are classified as "accepted", so we need to remove them from the list
    acc = sorted(np.setdiff1d(acc, ign))
    # Drop rejected components (by AROMA) from list of ignored components
    ign = sorted(np.setdiff1d(ign, acc))

    # Compute temporal regression
    data_optcom_z = stats.zscore(data_optcom, axis=-1)
    # component parameter estimates
    comp_pes = np.linalg.lstsq(mixing, data_optcom_z.T, rcond=None)[0].T

    # Build time series of just BOLD-like components (i.e., MEHK) and save T1-like effect
    mehk_ts = np.dot(comp_pes[:, acc], mixing[:, acc].T)
    t1_map = mehk_ts.min(axis=-1)  # map of T1-like effect
    t1_map -= t1_map.mean()
    t1_img = masking.unmask(t1_map, mask)
    t1_map = t1_map[:, np.newaxis]

    # Find the global signal based on the T1-like effect
    gs_ts = np.linalg.lstsq(t1_map, data_optcom_z, rcond=None)[0]
    glsig_df = pd.DataFrame(data=gs_ts.T, columns=["mir_global_signal"])

    # Orthogonalize mixing matrix w.r.t. T1-GS
    mixing_not1gs = mixing.T - np.dot(np.linalg.lstsq(gs_ts.T, mixing, rcond=None)[0].T, gs_ts)
    mixing_not1gs_z = stats.zscore(mixing_not1gs, axis=-1)
    mixing_not1gs_z = np.vstack((np.atleast_2d(np.ones(max(gs_ts.shape))), gs_ts, mixing_not1gs_z))

    # Write T1-corrected components and mixing matrix
    mixing_df = pd.DataFrame(data=mixing_not1gs.T, columns=component_table["Component"].values)
    return t1_img, glsig_df, mixing_df


def run_tedana(raw_dir, fmriprep_dir, aroma_dir, temp_dir, tedana_out_dir):
    """Run tedana on fMRIPrep derivatives.

    Parameters
    ----------
    raw_dir : str
        Path to the raw data directory.
    fmriprep_dir : str
        Path to the fMRIPrep derivatives directory.
    aroma_dir : str
        Path to the fMRIPost-AROMA derivatives directory.
    temp_dir : str
        Path to the temporary directory.
    tedana_out_dir : str
        Path to the tedana derivatives directory.
    """

    print("TEDANA")

    base_search = os.path.join(
        raw_dir,
        "sub-*",
        "ses-1",
        "func",
        "sub-*_ses-1_*_echo-1_part-mag_bold.nii.gz",
    )
    base_files = sorted(glob(base_search))
    if not base_files:
        raise FileNotFoundError(base_search)

    for base_file in base_files:
        raw_files = sorted(glob(base_file.replace("echo-1", "echo-*")))

        base_filename = os.path.basename(base_file)
        print(f"\t{base_filename}")
        subject = base_filename.split("_")[0]
        prefix = base_filename.split("_echo-1")[0]

        # Get the fMRIPrep brain mask
        mask_base = base_filename.split("_echo-1")[0]
        mask = os.path.join(
            fmriprep_dir,
            subject,
            "ses-1",
            "func",
            f"{mask_base}_part-mag_desc-brain_mask.nii.gz",
        )
        assert os.path.isfile(mask), mask

        # Get the fMRIPrep confounds file and identify the number of non-steady-state volumes
        confounds_file = os.path.join(
            fmriprep_dir,
            subject,
            "ses-1",
            "func",
            f"{mask_base}_part-mag_desc-confounds_timeseries.tsv",
        )
        confounds_df = pd.read_table(confounds_file)
        nss_cols = [c for c in confounds_df.columns if c.startswith("non_steady_state_outlier")]

        dummy_scans = 0
        if nss_cols:
            initial_volumes_df = confounds_df[nss_cols]
            dummy_scans = np.any(initial_volumes_df.to_numpy(), axis=1)
            dummy_scans = np.where(dummy_scans)[0]

            # reasonably assumes all NSS volumes are contiguous
            dummy_scans = int(dummy_scans[-1] + 1)

        print(f"\t\t{dummy_scans} dummy scans")

        # Get the fMRIPost-AROMA mixing file
        mask_base = "_".join([p for p in mask_base.split("_") if not p.startswith("dir")])

        t2star = os.path.join(
            fmriprep_dir,
            subject,
            "ses-1",
            "func",
            f"{mask_base}_space-boldref_T2starmap.nii.gz",
        )
        assert os.path.isfile(t2star), t2star

        mixing = os.path.join(
            aroma_dir,
            subject,
            "ses-1",
            "func",
            f"{mask_base}_part-mag_space-MNI152NLin6Asym_res-2_desc-melodic_mixing.tsv",
        )
        assert os.path.isfile(mixing), mixing

        mixing_arr = np.loadtxt(mixing)
        # remove dummy volumes
        mixing_arr = mixing_arr[dummy_scans:, :]
        mixing_df = pd.DataFrame(
            data=mixing_arr,
            columns=[f"ICA_{i}" for i in range(mixing_arr.shape[1])],
        )
        mixing2 = os.path.join(temp_dir, os.path.basename(mixing))
        mixing_df.to_csv(mixing2, sep="\t", index=False)

        echo_times = []
        fmriprep_files = []
        for raw_file in raw_files:
            base_query = os.path.basename(raw_file).split("_bold.nii.gz")[0]

            # Get echo time from json file
            with open(raw_file.replace(".nii.gz", ".json"), "r") as f:
                echo_times.append(json.load(f)["EchoTime"] * 1000)

            # Get the fMRIPrep BOLD files
            fmriprep_file = os.path.join(
                fmriprep_dir,
                subject,
                "ses-1",
                "func",
                f"{base_query}_desc-preproc_bold.nii.gz",
            )
            assert os.path.isfile(fmriprep_file), fmriprep_file

            # Remove non-steady-state volumes
            echo_img = nb.load(fmriprep_file)
            echo_img = echo_img.slicer[:, :, :, dummy_scans:]
            temporary_file = os.path.join(
                temp_dir,
                os.path.basename(fmriprep_file),
            )
            echo_img.to_filename(temporary_file)
            fmriprep_files.append(temporary_file)

        tedana_run_out_dir = os.path.join(tedana_out_dir, subject, "ses-1", "func")
        os.makedirs(tedana_run_out_dir, exist_ok=True)
        if os.path.isfile(os.path.join(tedana_run_out_dir, f"{prefix}_tedana_report.html")):
            print(f"DONE: {prefix}")
            continue

        tedana_workflow(
            data=fmriprep_files,
            tes=echo_times,
            mask=mask,
            out_dir=tedana_run_out_dir,
            prefix=prefix,
            fittype="curvefit",
            combmode="t2s",
            tree="minimal",
            mixm=mixing2,
            gscontrol=["mir"],
            tedort=True,
            # t2smap=t2star,
        )


def run_tedana_aroma(raw_dir, fmriprep_dir, aroma_dir, tedana_out_dir, tedana_aroma_out_dir):
    """Combine tedana and AROMA classifications using tedana and fMRIPost-AROMA outputs.

    Parameters
    ----------
    raw_dir : str
        Path to the raw data directory.
    fmriprep_dir : str
        Path to the fMRIPrep derivatives directory.
    aroma_dir : str
        Path to the fMRIPost-AROMA derivatives directory.
    tedana_out_dir : str
        Path to the tedana derivatives directory.
    tedana_aroma_out_dir : str
        Path to the tedana+aroma derivatives directory.
    """
    print("TEDANA+AROMA")

    base_files = sorted(
        glob(
            os.path.join(
                raw_dir,
                "sub-*",
                "ses-1",
                "func",
                "sub-*_ses-1_*_echo-1_part-mag_bold.nii.gz",
            )
        )
    )
    for base_file in base_files:
        base_filename = os.path.basename(base_file)
        print(f"\t{base_filename}")
        subject = base_filename.split("_")[0]
        prefix = base_filename.split("_echo-1")[0]

        tedana_run_out_dir = os.path.join(tedana_out_dir, subject, "ses-1", "func")
        # Get the fMRIPrep brain mask
        fname_base = base_filename.split("_echo-1")[0]

        # Get the fMRIPrep confounds file and identify the number of non-steady-state volumes
        confounds_file = os.path.join(
            fmriprep_dir,
            subject,
            "ses-1",
            "func",
            f"{fname_base}_part-mag_desc-confounds_timeseries.tsv",
        )
        confounds_df = pd.read_table(confounds_file)
        nss_cols = [c for c in confounds_df.columns if c.startswith("non_steady_state_outlier")]

        dummy_scans = 0
        if nss_cols:
            initial_volumes_df = confounds_df[nss_cols]
            dummy_scans = np.any(initial_volumes_df.to_numpy(), axis=1)
            dummy_scans = np.where(dummy_scans)[0]

            # reasonably assumes all NSS volumes are contiguous
            dummy_scans = int(dummy_scans[-1] + 1)

        print(f"\t\t{dummy_scans} dummy scans")

        fname_base = "_".join([p for p in fname_base.split("_") if not p.startswith("dir")])

        # Combine the classifications from tedana with the AROMA classifications
        # and save the combined classifications to the derivatives folder
        # Get the AROMA classifications
        aroma_classifications = os.path.join(
            aroma_dir,
            subject,
            "ses-1",
            "func",
            f"{fname_base}_part-mag_desc-aroma_metrics.tsv",
        )
        aroma_df = pd.read_table(aroma_classifications)

        # Get the tedana classifications
        tedana_classifications = os.path.join(
            tedana_run_out_dir,
            f"{prefix}_desc-tedana_metrics.tsv",
        )
        tedana_df = pd.read_table(tedana_classifications)

        assert aroma_df.shape[0] == tedana_df.shape[0], (
            "AROMA and tedana have different numbers of components"
        )

        # Combine the classifications
        for i_row, aroma_row in aroma_df.iterrows():
            aroma_clf = aroma_row["classification"]
            tedana_rationale = tedana_df.loc[i_row, "classification_tags"]
            tedana_rationales = tedana_rationale.split(";")

            aroma_rationales = []
            if aroma_clf == "rejected":
                aroma_rationales = aroma_row["rationale"].split(";")
                aroma_rationales = [f"AROMA {rationale}" for rationale in aroma_rationales]
                tedana_df.loc[i_row, "classification"] = "rejected"

            tedana_rationales = [f"TEDANA {rationale}" for rationale in tedana_rationales]
            rationales = tedana_rationales + aroma_rationales
            tedana_df.loc[i_row, "classification_tags"] = ";".join(rationales)

            # Add other columns from aroma_df to tedana_df
            other_cols = [
                "edge_fract",
                "csf_fract",
                "max_RP_corr",
                "HFC",
                "model_variance_explained",
                "total_variance_explained",
            ]
            for col in other_cols:
                tedana_df.loc[i_row, col] = aroma_row[col]

        # Save the combined classifications
        tedana_aroma_run_out_dir = os.path.join(
            tedana_aroma_out_dir,
            subject,
            "ses-1",
            "func",
        )
        os.makedirs(tedana_aroma_run_out_dir, exist_ok=True)

        # Write out updated component table
        combined_classifications = os.path.join(
            tedana_aroma_run_out_dir,
            f"{prefix}_desc-tedana+aroma_metrics.tsv",
        )
        tedana_df.to_csv(
            combined_classifications,
            sep="\t",
            index=False,
        )

        # Load optimally combined data, mixing matrix, adaptive mask
        optcom = os.path.join(
            tedana_run_out_dir,
            f"{prefix}_desc-optcom_bold.nii.gz",
        )
        mixing = os.path.join(
            tedana_run_out_dir,
            f"{prefix}_desc-ICA_mixing.tsv",
        )
        adaptive_mask = os.path.join(
            tedana_run_out_dir,
            f"{prefix}_desc-adaptiveGoodSignal_mask.nii.gz",
        )
        assert os.path.isfile(optcom), optcom
        assert os.path.isfile(mixing), mixing
        assert os.path.isfile(adaptive_mask), adaptive_mask

        mixing_df = pd.read_table(mixing)
        mixing_arr = mixing_df.to_numpy()

        # Orthogonalize rejected components with respect to accepted components
        comps_accepted = tedana_df.loc[tedana_df["classification"] == "accepted"].index.values
        comps_rejected = tedana_df.loc[tedana_df["classification"] == "rejected"].index.values
        acc_ts = mixing_arr[:, comps_accepted]
        rej_ts = mixing_arr[:, comps_rejected]
        betas = np.linalg.lstsq(acc_ts, rej_ts, rcond=None)[0]
        pred_rej_ts = np.dot(acc_ts, betas)
        resid = rej_ts - pred_rej_ts
        mixing_arr[:, comps_rejected] = resid

        # Write out orthogonalized mixing matrix
        mixing_df = pd.DataFrame(columns=mixing_df.columns, data=mixing_arr)
        mixing_df.to_csv(
            os.path.join(
                tedana_aroma_run_out_dir,
                f"{prefix}_desc-ICAOrth_mixing.tsv",
            ),
            sep="\t",
        )

        # Perform minimum image regression on orthogonalized mixing matrix
        mask_img = image.math_img("(img > 0).astype(int)", img=adaptive_mask)
        optcom_arr = masking.apply_mask(optcom, mask_img).T
        t1_img, glsig_df, mixing_df = minimum_image_regression(
            data_optcom=optcom_arr,
            mixing=mixing_arr,
            mask=mask_img,
            component_table=tedana_df,
        )
        t1_img.to_filename(os.path.join(tedana_aroma_run_out_dir, f"{prefix}_desc-t1_map.nii.gz"))
        glsig_df.to_csv(
            os.path.join(tedana_aroma_run_out_dir, f"{prefix}_desc-glsig_timeseries.tsv"),
            sep="\t",
            index=False,
        )
        mixing_df.to_csv(
            os.path.join(tedana_aroma_run_out_dir, f"{prefix}_desc-ICAOrthMIR_mixing.tsv"),
            sep="\t",
        )
        mixing_arr = mixing_df.to_numpy()
        confounds_arr = mixing_arr[:, comps_rejected]
        rej_columns = [mixing_df.columns[i] for i in comps_rejected]

        # Add dummy volumes to confounds_arr
        dummy_confounds = np.zeros((dummy_scans, confounds_arr.shape[1]))
        confounds_arr = np.vstack((dummy_confounds, confounds_arr))

        confounds_df = pd.DataFrame(columns=rej_columns, data=confounds_arr)
        confounds_df.to_csv(
            os.path.join(tedana_aroma_run_out_dir, f"{prefix}_desc-confounds_timeseries.tsv"),
            sep="\t",
            index=False,
        )


if __name__ == "__main__":
    raw_dir_ = "/cbica/projects/pafin/dset"
    fmriprep_dir_ = "/cbica/projects/pafin/derivatives/fmriprep"
    aroma_dir_ = "/cbica/projects/pafin/derivatives/fmripost_aroma"
    temp_dir_ = "/cbica/comp_space/pafin/tedana_temp"
    tedana_out_dir_ = "/cbica/projects/pafin/derivatives/tedana"
    tedana_aroma_out_dir_ = "/cbica/projects/pafin/derivatives/tedana+aroma"

    os.makedirs(temp_dir_, exist_ok=True)

    # Apply tedana classification to the data, using the AROMA mixing matrix
    run_tedana(raw_dir_, fmriprep_dir_, aroma_dir_, temp_dir_, tedana_out_dir_)
    # Combine the tedana classifications with the AROMA classifications
    run_tedana_aroma(raw_dir_, fmriprep_dir_, aroma_dir_, tedana_out_dir_, tedana_aroma_out_dir_)
