"""Validation tests for the pinned NASA PSCompPars preprocessing pipeline."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.data_audit import PRE_MOVE_SHA256, SOURCE_PATH, sha256_file
from ml.pipeline import run_pipeline
from ml.preprocessing import (
    EXPECTED_PRIMARY_RECORDS,
    EXPECTED_WITHOUT_TEMPERATURE_RECORDS,
    FOUR_FEATURES,
    load_source_dataset,
    prepare_frames,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def source_frame() -> pd.DataFrame:
    return load_source_dataset(SOURCE_PATH, expected_sha256=PRE_MOVE_SHA256)


@pytest.fixture(scope="session")
def prepared(source_frame: pd.DataFrame):
    return prepare_frames(source_frame)


@pytest.fixture
def workspace_tmp_path():
    """Use the ignored project venv for temporary outputs in restricted Windows sandboxes."""
    with tempfile.TemporaryDirectory(prefix="preprocessing-test-", dir=ROOT / ".venv") as path:
        yield Path(path)


def test_source_record_count_and_schema(source_frame: pd.DataFrame) -> None:
    assert source_frame.shape == (6_451, 84)
    assert set(FOUR_FEATURES).issubset(source_frame.columns)


def test_complete_case_eligibility_count(prepared) -> None:
    assert prepared.eligibility["all_four_fields_present"] == 5_273
    assert prepared.eligibility["eligible_four_feature_records"] == EXPECTED_PRIMARY_RECORDS
    assert prepared.eligibility["eligible_without_temperature_sensitivity_records"] == (
        EXPECTED_WITHOUT_TEMPERATURE_RECORDS
    )
    assert sum(prepared.eligibility["four_feature_stepwise_partition"].values()) == 6_451


def test_log_transformations_are_correct(source_frame: pd.DataFrame, prepared) -> None:
    example = prepared.with_temperature.iloc[0]
    original = source_frame.loc[source_frame["pl_name"] == example["pl_name"]].iloc[0]
    assert example["log10_pl_rade"] == pytest.approx(np.log10(original["pl_rade"]))
    assert example["log10_pl_orbper"] == pytest.approx(np.log10(original["pl_orbper"]))
    assert example["pl_eqt"] == original["pl_eqt"]


def test_eccentricity_zeros_are_preserved(source_frame: pd.DataFrame, prepared) -> None:
    primary_names = set(prepared.with_temperature["pl_name"])
    expected_zeros = source_frame.loc[
        source_frame["pl_name"].isin(primary_names), "pl_orbeccen"
    ].eq(0).sum()
    observed_zeros = prepared.with_temperature["pl_orbeccen"].eq(0).sum()
    assert observed_zeros == expected_zeros
    assert observed_zeros == prepared.eligibility["review_only_domain_flags"][
        "eccentricity_zero_primary_cohort"
    ]


def test_transformed_and_standardized_values_are_finite(prepared) -> None:
    for frame in (prepared.with_temperature, prepared.without_temperature):
        derived_columns = [
            name
            for name in frame.columns
            if name.startswith("log10_") or name.startswith("scaled_")
        ]
        assert np.isfinite(frame[derived_columns].to_numpy(dtype=np.float64)).all()


def test_each_primary_feature_matrix_is_standardized(prepared) -> None:
    columns = {
        "with_temperature": [
            "scaled_log10_pl_rade",
            "scaled_log10_pl_orbper",
            "scaled_pl_eqt",
            "scaled_pl_orbeccen",
        ],
        "without_temperature": [
            "scaled_log10_pl_rade",
            "scaled_log10_pl_orbper",
            "scaled_pl_orbeccen",
        ],
    }
    for key, output in (
        ("with_temperature", prepared.with_temperature),
        ("without_temperature", prepared.without_temperature),
    ):
        values = output[columns[key]].to_numpy(dtype=np.float64)
        np.testing.assert_allclose(values.mean(axis=0), 0.0, atol=1e-12)
        np.testing.assert_allclose(values.std(axis=0, ddof=0), 1.0, atol=1e-12)


def test_primary_experiments_have_identical_planet_ids_in_order(prepared) -> None:
    assert prepared.with_temperature["pl_name"].tolist() == prepared.without_temperature[
        "pl_name"
    ].tolist()
    assert len(prepared.with_temperature) == len(prepared.without_temperature) == 5_273


def test_raw_physical_measurements_are_preserved(source_frame: pd.DataFrame, prepared) -> None:
    by_name = source_frame.set_index("pl_name")
    for output in (prepared.with_temperature, prepared.without_temperature):
        aligned = by_name.loc[output["pl_name"].tolist(), list(FOUR_FEATURES)].reset_index(drop=True)
        actual = output.loc[:, list(FOUR_FEATURES)].reset_index(drop=True)
        pd.testing.assert_frame_equal(actual, aligned, check_dtype=False, check_exact=True)


def _tree_hashes(directory: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return result


def test_pipeline_outputs_are_reproducible(workspace_tmp_path: Path) -> None:
    first_root = workspace_tmp_path / "first"
    second_root = workspace_tmp_path / "second"
    run_pipeline(output_root=first_root)
    run_pipeline(output_root=second_root)
    assert _tree_hashes(first_root) == _tree_hashes(second_root)


def test_master_preserves_all_records_and_has_no_cluster_labels(
    source_frame: pd.DataFrame, prepared
) -> None:
    assert len(prepared.master) == len(source_frame) == 6_451
    assert prepared.master["pl_name"].tolist() == source_frame["pl_name"].tolist()
    assert prepared.master["eligible_four_feature_clustering"].sum() == 5_273
    assert prepared.master["eligible_without_temperature_sensitivity"].sum() == 5_335
    assert all(name in prepared.master.columns for name in source_frame.columns)
    assert not any("cluster" in name.lower() and "eligible" not in name.lower()
                   for name in prepared.master.columns)


def test_pipeline_keeps_original_source_hash_unchanged(workspace_tmp_path: Path) -> None:
    before = sha256_file(SOURCE_PATH)
    run_pipeline(output_root=workspace_tmp_path / "integrity")
    assert sha256_file(SOURCE_PATH) == before == PRE_MOVE_SHA256
