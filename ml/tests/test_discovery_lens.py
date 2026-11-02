"""Scientific contract tests for the offline Discovery Lens summaries."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import pytest

from ml.discovery_lens import (
    APPLICATION_DATA,
    EXPECTED_METHOD_COUNTS,
    OUTPUTS,
    PROJECT_ROOT,
    analyze_discovery_lens,
    run_discovery_lens,
    validate_application_data,
)


@pytest.fixture(scope="module")
def application_data() -> pd.DataFrame:
    return pd.read_csv(PROJECT_ROOT / APPLICATION_DATA, low_memory=False)


@pytest.fixture(scope="module")
def analysis(application_data: pd.DataFrame):
    return analyze_discovery_lens(application_data)


def test_full_catalogue_method_counts_and_host_summary(application_data, analysis):
    _, report = analysis
    assert len(application_data) == 6_451
    assert report["dataset"]["unique_planet_identifiers"] == 6_451
    assert report["dataset"]["unique_host_systems"] == 4_847
    assert report["dataset"]["multi_planet_hosts"] == 1_069
    assert report["dataset"]["records_in_multi_planet_hosts"] == 2_673
    assert report["dataset"]["maximum_planets_per_host"] == 8
    assert report["method_counts"] == EXPECTED_METHOD_COUNTS
    assert len(report["methods"]) == 11
    assert sum(report["method_counts"].values()) == 6_451


def test_timeline_has_all_years_zero_1993_partial_2026_and_reconciles(analysis):
    tables, report = analysis
    timeline = tables["timeline"]
    assert timeline["discovery_year"].nunique() == 35
    assert timeline["discovery_year"].tolist()[::11] == list(range(1992, 2027))
    assert int(timeline.loc[timeline["discovery_year"] == 1993, "planet_count"].sum()) == 0
    assert timeline.loc[timeline["discovery_year"] == 2026, "is_partial_year"].all()
    assert int(timeline["planet_count"].sum()) == 6_451
    assert report["validation_checks"]["timeline_totals_reconcile_to_source"] is True


def test_facility_and_property_missingness_keep_catalogue_values(analysis):
    tables, report = analysis
    assert tables["facility_counts"]["facility"].nunique() == 73
    assert int(tables["facility_counts"]["planet_count"].sum()) == 6_451
    assert report["property_missingness"]["pl_rade"]["missing_count"] == 50
    assert report["property_missingness"]["pl_orbper"]["missing_count"] == 354
    assert report["property_missingness"]["pl_eqt"]["missing_count"] == 540
    assert report["property_missingness"]["pl_orbeccen"]["missing_count"] == 1_068
    assert report["property_missingness"]["pl_orbeccen"]["zero_measurement_count"] == 3_156
    assert len(tables["property_summary"]) == 11 * 4
    assert len(tables["property_values"]) == sum(
        6_451 - report["property_missingness"][key]["missing_count"]
        for key in ("pl_rade", "pl_orbper", "pl_eqt", "pl_orbeccen")
    )


def test_small_method_sample_and_asymmetric_uncertainties_are_preserved(analysis):
    tables, _ = analysis
    summary = tables["property_summary"].set_index(["discovery_method", "property"])
    assert bool(summary.loc[("Disk Kinematics", "pl_rade"), "sample_size_is_small"])
    observations = tables["property_values"]
    # In this catalogue err1 is the positive offset and err2 the negative
    # offset; preserve the original field values instead of relabelling them.
    error_1 = observations["error_1"].dropna()
    error_2 = observations["error_2"].dropna()
    assert (error_1 > 0).any()
    assert (error_2 < 0).any()
    assert (summary["uncertainty_count"] <= summary["measured_count"]).all()


def test_pipeline_writes_a_hashed_manifest_without_touching_scientific_inputs():
    with TemporaryDirectory(prefix="exoatlas-discovery-lens-test-", dir=PROJECT_ROOT) as temporary:
        output_root = Path(temporary)
        report = run_discovery_lens(PROJECT_ROOT, output_root)
        report_path = output_root / OUTPUTS["report"]
        written = json.loads(report_path.read_text(encoding="utf-8"))
        assert written["dataset"]["planet_records"] == 6_451
        assert set(written["outputs"]) == {
            OUTPUTS[name].as_posix()
            for name in ("timeline", "property_summary", "facility_counts", "property_values")
        }
        assert all(len(digest) == 64 for digest in written["outputs"].values())
        assert written["frozen_artifacts_sha256"] == report["frozen_artifacts_sha256"]
        assert written["source"]["raw_source_present"] is True
        assert len(written["source"]["raw_source_sha256"]) == 64
        assert written["source"]["download_date"] == "2026-10-30"
        assert written["source"]["download_timestamp"] == "Fri Oct 30 13:47:46 2026"
        assert written["source"]["raw_source_records"] == 6_451
        assert written["source"]["raw_source_columns"] == 84
        assert written["source"]["raw_source_base_columns_match_application"] is True


def test_validation_rejects_duplicate_planets_invalid_hosts_and_new_methods(application_data):
    duplicate = pd.concat([application_data, application_data.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate pl_name"):
        validate_application_data(duplicate)

    invalid_host = application_data.copy()
    invalid_host.loc[0, "hostname"] = "  "
    with pytest.raises(ValueError, match="hostname"):
        validate_application_data(invalid_host)

    new_method = application_data.copy()
    new_method.loc[0, "discoverymethod"] = "Unreviewed Method"
    with pytest.raises(ValueError, match="categories changed"):
        validate_application_data(new_method)
