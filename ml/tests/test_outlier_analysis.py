"""Scientific integrity tests for prepared outlier diagnostics."""

from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
import pytest

from ml import outlier_analysis as outliers


@pytest.fixture(scope="module")
def prepared_inputs():
    root = outliers.PROJECT_ROOT
    hashes_before = outliers.verify_input_hashes(root)
    application = pd.read_csv(root / outliers.APPLICATION_DATA, low_memory=False, dtype={"pl_name": "string"})
    features = pd.read_csv(root / outliers.FEATURE_DATA, low_memory=False, dtype={"pl_name": "string"})
    assignments = pd.read_csv(root / outliers.ASSIGNMENTS, dtype={"pl_name": "string"})
    silhouettes = pd.read_csv(root / outliers.SILHOUETTES, dtype={"pl_name": "string"})
    profiles = outliers._read_json(root, outliers.PROFILES)
    result = outliers.build_diagnostics(
        application,
        features,
        assignments,
        silhouettes,
        joblib.load(root / outliers.SCALER),
        joblib.load(root / outliers.MODEL),
        profiles,
    )
    yield application, features, assignments, silhouettes, profiles, result
    assert outliers.verify_input_hashes(root) == hashes_before


def test_centroid_distance_uses_the_assigned_centres():
    points = np.array([[1.0, 2.0], [3.0, 4.0]])
    centers = np.array([[0.0, 0.0], [3.0, 2.0]])
    assert outliers.centroid_distances(points, np.array([0, 1]), centers) == pytest.approx(
        [np.sqrt(5.0), 2.0]
    )


def test_centroid_distance_rejects_invalid_cluster_labels():
    with pytest.raises(ValueError, match="Cluster labels"):
        outliers.centroid_distances(np.ones((1, 2)), np.array([2]), np.zeros((2, 2)))


def test_within_cluster_percentiles_keep_clusters_separate_and_average_ties():
    distances = pd.Series([1.0, 2.0, 2.0, 8.0, 1.0])
    clusters = pd.Series([0, 0, 0, 0, 1])
    values = outliers.within_cluster_percentiles(distances, clusters)
    assert values.iloc[:4].tolist() == pytest.approx([25.0, 62.5, 62.5, 100.0])
    assert values.iloc[4] == pytest.approx(100.0)


def test_percentile_rejects_missing_values():
    with pytest.raises(ValueError, match="only assigned"):
        outliers.within_cluster_percentiles(pd.Series([np.nan]), pd.Series([0]))


def test_feature_relation_uses_physical_quartiles_and_zero_iqr_is_unavailable():
    reference = {"q1": 2.0, "median": 4.0, "q3": 6.0, "iqr": 4.0}
    assert outliers.feature_relation(1.0, reference) == ("below_q1", pytest.approx(-0.75))
    assert outliers.feature_relation(4.0, reference) == ("within_q1_q3", pytest.approx(0.0))
    assert outliers.feature_relation(7.0, reference) == ("above_q3", pytest.approx(0.75))
    assert outliers.feature_relation(1.0, {**reference, "iqr": 0.0}) == ("below_q1", None)


def test_real_diagnostics_preserve_full_catalogue_and_null_unassigned_rows(prepared_inputs):
    application, features, _assignments, _silhouettes, _profiles, diagnostics = prepared_inputs
    assert len(diagnostics) == len(application) == 6451
    assert diagnostics["pl_name"].tolist() == application["pl_name"].astype(str).tolist()
    assert diagnostics["assignment_status"].value_counts().to_dict() == {"assigned": 5273, "unassigned": 1178}
    assigned = diagnostics[diagnostics["assignment_status"] == "assigned"]
    unassigned = diagnostics[diagnostics["assignment_status"] == "unassigned"]
    assert np.isfinite(assigned["centroid_distance"]).all()
    assert assigned["cluster_distance_percentile"].between(0, 100).all()
    assert np.isfinite(assigned["silhouette_score"]).all()
    assert unassigned[["centroid_distance", "cluster_distance_percentile", "silhouette_score"]].isna().all().all()
    physical_columns = ["hostname", "pl_rade", "pl_orbper", "pl_eqt", "pl_orbeccen"]
    pd.testing.assert_frame_equal(
        diagnostics[physical_columns], application[physical_columns], check_dtype=False, check_exact=True
    )
    assert len(features) == len(assigned)


def test_saved_silhouettes_are_reused_and_match_assignments(prepared_inputs):
    _application, _features, assignments, silhouettes, _profiles, diagnostics = prepared_inputs
    primary = silhouettes[silhouettes["experiment"] == "with_temp"].set_index("pl_name")
    sample = assignments.iloc[[0, 250, 4000]]
    result = diagnostics.set_index("pl_name").loc[sample["pl_name"].tolist()]
    expected = primary.loc[sample["pl_name"].tolist(), "silhouette_score"].to_numpy()
    assert result["silhouette_score"].to_numpy() == pytest.approx(expected)
    assert result["cluster_id"].astype(int).tolist() == sample["cluster_id"].tolist()


def test_mismatched_identifiers_fail_loudly(prepared_inputs):
    application, features, assignments, silhouettes, profiles, _result = prepared_inputs
    broken = assignments.copy()
    broken.loc[0, "pl_name"] = "not a frozen planet id"
    with pytest.raises(ValueError, match="identical ordered identifiers"):
        outliers.build_diagnostics(
            application,
            features,
            broken,
            silhouettes,
            joblib.load(outliers.PROJECT_ROOT / outliers.SCALER),
            joblib.load(outliers.PROJECT_ROOT / outliers.MODEL),
            profiles,
        )


def test_frozen_inputs_still_match_their_saved_checksums():
    expected = outliers._expected_input_hashes(outliers.PROJECT_ROOT)
    assert outliers.verify_input_hashes(outliers.PROJECT_ROOT, expected) == expected
