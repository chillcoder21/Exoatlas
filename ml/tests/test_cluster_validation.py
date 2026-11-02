"""Integrity and reproducibility tests for cluster validation outputs."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import chi2_contingency
from sklearn.metrics import adjusted_rand_score, silhouette_samples

from ml.cluster_validation import (
    EXPERIMENTS,
    PHYSICAL_FEATURES,
    _ordered_join,
    discovery_method_validation,
    silhouette_validation,
)
from ml.clustering import feature_columns
from ml.clustering_pipeline import EXPERIMENT_OUTPUT_DIR, ROOT
from ml.data_audit import PRE_MOVE_SHA256, sha256_file
from ml.validation_pipeline import OUTPUT_DIR, run_validation_pipeline


@pytest.fixture(scope="module")
def validation_outputs():
    directory = ROOT / OUTPUT_DIR
    report = json.loads((directory / "cluster_validation_report.json").read_text(encoding="utf-8"))
    return {
        "directory": directory,
        "report": report,
        "source": pd.read_csv(ROOT / "data/raw/PSCompPars_2026.10.30_13.47.46.csv", comment="#", low_memory=False),
        "matrices": {
            experiment: pd.read_csv(
                ROOT / ("data/processed/clustering_features_with_temp.csv" if experiment == "with_temp"
                        else "data/processed/clustering_features_without_temp.csv"),
                low_memory=False,
            ) for experiment in EXPERIMENTS
        },
        "assignments": {
            experiment: pd.read_csv(
                ROOT / EXPERIMENT_OUTPUT_DIR / f"cluster_assignments_{experiment}_k4.csv",
                dtype={"pl_name": "string"},
            )
            for experiment in EXPERIMENTS
        },
        "distribution": pd.read_csv(directory / "cluster_distribution_validation.csv"),
        "silhouettes": pd.read_csv(directory / "cluster_silhouette_validation.csv"),
        "separation": pd.read_csv(directory / "cluster_separation.csv"),
        "k_selection": pd.read_csv(directory / "k_selection_comparison.csv"),
        "counts": pd.read_csv(directory / "discovery_method_counts.csv"),
        "row_percentages": pd.read_csv(directory / "discovery_method_row_percentages.csv"),
        "column_percentages": pd.read_csv(directory / "discovery_method_column_percentages.csv"),
        "method_tests": json.loads((directory / "discovery_method_tests.json").read_text(encoding="utf-8")),
        "temperature_comparison": pd.read_csv(directory / "temperature_feature_comparison.csv"),
        "changed": pd.read_csv(directory / "temperature_feature_membership_changes.csv"),
    }


def test_source_joins_and_primary_assignments_use_unique_stable_ids(validation_outputs) -> None:
    identifiers = validation_outputs["matrices"]["with_temp"]["pl_name"].astype(str).tolist()
    assert len(identifiers) == 5_273
    assert len(set(identifiers)) == 5_273
    for experiment in EXPERIMENTS:
        assignment = validation_outputs["assignments"][experiment]
        assert assignment["pl_name"].astype(str).tolist() == identifiers
        assert assignment["pl_name"].is_unique
        assert assignment["cluster_id"].notna().all()
        assert assignment["cluster_id"].astype(int).value_counts().sum() == 5_273
        joined = _ordered_join(validation_outputs["source"], assignment, identifiers)
        assert len(joined) == 5_273
        assert joined["pl_name"].astype(str).tolist() == identifiers

    duplicate = validation_outputs["assignments"]["with_temp"].copy()
    duplicate.loc[1, "pl_name"] = duplicate.loc[0, "pl_name"]
    with pytest.raises(ValueError, match="unique"):
        _ordered_join(validation_outputs["source"], duplicate, identifiers)


def test_distribution_statistics_are_original_physical_values(validation_outputs) -> None:
    report = validation_outputs["report"]
    assert report["dataset"]["primary_cohort_records"] == 5_273
    assert report["dataset"]["primary_cohort_unique_planet_ids"] == 5_273
    distribution = validation_outputs["distribution"]
    assert len(distribution) == 2 * 4 * 4
    source = validation_outputs["source"].set_index("pl_name")
    for experiment in EXPERIMENTS:
        assignment = validation_outputs["assignments"][experiment]
        for row in distribution.loc[distribution.experiment == experiment].to_dict(orient="records"):
            members = assignment.loc[assignment.cluster_id == row["cluster_id"], "pl_name"].astype(str).tolist()
            values = pd.to_numeric(source.loc[members, row["feature"]], errors="coerce")
            assert row["planet_count"] == len(members)
            assert row["planet_percent"] == pytest.approx(len(members) / 5_273 * 100)
            assert row["minimum"] == pytest.approx(values.min())
            assert row["q1"] == pytest.approx(values.quantile(0.25))
            assert row["median"] == pytest.approx(values.median())
            assert row["q3"] == pytest.approx(values.quantile(0.75))
            assert row["iqr"] == pytest.approx(values.quantile(0.75) - values.quantile(0.25))
            assert row["mean"] == pytest.approx(values.mean())
            assert row["standard_deviation"] == pytest.approx(values.std(ddof=1))
            assert row["maximum"] == pytest.approx(values.max())
            assert row["zero_value_count"] == int(values.eq(0).sum())
    cluster_percentages = distribution.drop_duplicates(["experiment", "cluster_id"])
    for _, group in cluster_percentages.groupby("experiment"):
        assert group["planet_percent"].sum() == pytest.approx(100.0)
    # Zero eccentricities are measurements and must survive the validation tables.
    eccentricity = distribution.loc[distribution.feature == "pl_orbeccen"]
    ids = validation_outputs["matrices"]["with_temp"]["pl_name"].astype(str).tolist()
    source_zeros = int(source.loc[ids, "pl_orbeccen"].eq(0).sum())
    assert eccentricity["zero_value_count"].sum() == 2 * source_zeros
    assert eccentricity["minimum"].eq(0).any()


def test_silhouette_helper_uses_the_exact_matrix_and_assignment_labels() -> None:
    ids = [f"p{i}" for i in range(8)]
    labels = np.repeat(np.arange(4), 2)
    matrices = {}
    assignments = {}
    for experiment in EXPERIMENTS:
        feature_names = feature_columns(experiment)
        center = np.array([[0.0] * len(feature_names), [10.0] * len(feature_names),
                           [20.0] * len(feature_names), [30.0] * len(feature_names)])
        values = np.repeat(center, 2, axis=0) + np.array([[0.0] * len(feature_names), [0.1] * len(feature_names)] * 4)
        matrices[experiment] = pd.DataFrame({"pl_name": ids, **{name: values[:, i] for i, name in enumerate(feature_names)}})
        assignments[experiment] = pd.DataFrame({"pl_name": ids, "cluster_id": labels})
    observations, summary = silhouette_validation(matrices, assignments)
    for experiment in EXPERIMENTS:
        expected = silhouette_samples(
            matrices[experiment].loc[:, feature_columns(experiment)].to_numpy(),
            labels,
            metric="euclidean",
        )
        actual = observations.loc[observations.experiment == experiment, "silhouette_score"].to_numpy()
        np.testing.assert_allclose(actual, expected)
    assert len(observations) == 16
    assert (summary.loc[summary.cluster_id == "ALL", "planet_count"] == 8).all()


def test_silhouette_output_reconciles_and_contains_one_score_per_planet(validation_outputs) -> None:
    scores = validation_outputs["silhouettes"]
    assert len(scores) == 2 * 5_273
    assert not scores["silhouette_score"].isna().any()
    for experiment in EXPERIMENTS:
        subset = scores.loc[scores.experiment == experiment]
        assert subset["pl_name"].is_unique
        assert subset["silhouette_score"].between(-1, 1).all()
        counts = subset.groupby("cluster_id").size()
        assignment_counts = validation_outputs["assignments"][experiment]["cluster_id"].value_counts().sort_index()
        pd.testing.assert_series_equal(counts.sort_index(), assignment_counts, check_names=False)


def test_centroid_and_profile_overlap_diagnostics_cover_k2_through_k5(validation_outputs) -> None:
    separation = validation_outputs["separation"]
    for k in (2, 3, 4, 5):
        group = separation.loc[(separation.experiment == "with_temp") & (separation.k == k)]
        pairs = k * (k - 1) // 2
        assert len(group.loc[group.diagnostic == "standardized_centroid_distance"]) == pairs
        assert len(group.loc[group.diagnostic == "binned_univariate_overlap_coefficient"]) == pairs * 4
        assert group["distance_or_overlap"].notna().all()
    assert set(separation.loc[separation.experiment == "without_temp", "k"]) == {4}
    assert separation.loc[
        separation.diagnostic == "binned_univariate_overlap_coefficient", "distance_or_overlap"
    ].between(0, 1).all()
    assert set(validation_outputs["k_selection"]["k"].astype(int)) == {2, 3, 4, 5}
    assert validation_outputs["k_selection"]["profile_medians_by_cluster_original_units"].notna().all()
    assert validation_outputs["k_selection"].loc[
        validation_outputs["k_selection"].k == 5, "transition_from_previous_k"
    ].notna().all()


def test_discovery_tables_reconcile_with_full_source_and_primary_cohort(validation_outputs) -> None:
    source = validation_outputs["source"]
    counts = validation_outputs["counts"]
    whole = counts.loc[(counts.experiment == "all_source") & (counts.scope == "full_source")]
    assert whole["planet_count"].sum() == len(source) == 6_451
    expected_source = source["discoverymethod"].fillna("Unreported").astype(str).value_counts().to_dict()
    assert dict(zip(whole.discoverymethod, whole.planet_count.astype(int), strict=True)) == expected_source
    for experiment in EXPERIMENTS:
        cohort = counts.loc[(counts.experiment == experiment) & (counts.scope == "primary_cohort")]
        clusters = counts.loc[(counts.experiment == experiment) & (counts.scope == "cluster")]
        assert cohort["planet_count"].sum() == 5_273
        assert clusters["planet_count"].sum() == 5_273
        observed_cluster_counts = {
            int(cluster): int(count)
            for cluster, count in clusters.groupby("cluster_id")["planet_count"].sum().items()
        }
        expected_cluster_counts = {
            int(cluster): int(count)
            for cluster, count in validation_outputs["assignments"][experiment]["cluster_id"].value_counts().sort_index().items()
        }
        assert observed_cluster_counts == expected_cluster_counts
    for _, group in validation_outputs["row_percentages"].groupby(["experiment", "cluster_id"]):
        assert group["percent_of_cluster"].sum() == pytest.approx(100.0)
    for _, group in validation_outputs["column_percentages"].groupby(["experiment", "discoverymethod"]):
        assert group["percent_of_discovery_method"].sum() == pytest.approx(100.0)


def test_chi_square_and_cramers_v_reconcile_with_reported_contingencies(validation_outputs) -> None:
    tests = validation_outputs["method_tests"]
    for experiment in EXPERIMENTS:
        result = tests[experiment]
        table = pd.DataFrame(result["observed_contingency_table"]).T.sort_index(axis=0).sort_index(axis=1)
        statistic, p_value, dof, expected = chi2_contingency(table.to_numpy(dtype=int), correction=False)
        n = int(table.to_numpy().sum())
        dimensions = min(table.shape[0] - 1, table.shape[1] - 1)
        cramers_v = np.sqrt(statistic / (n * dimensions))
        assert result["sample_size"] == n == 5_273
        assert result["chi_square_statistic"] == pytest.approx(statistic)
        assert result["p_value"] == pytest.approx(p_value)
        assert result["degrees_of_freedom"] == dof
        assert result["cramers_v"] == pytest.approx(cramers_v)
        assert result["expected_cells_below_5"] == int((expected < 5).sum())
        assert result["expected_cells_below_1"] == int((expected < 1).sum())
        assert result["expected_cell_count"] == expected.size


def test_temperature_comparison_aligns_by_overlap_and_lists_changed_planets(validation_outputs) -> None:
    report_summary = validation_outputs["report"]["temperature_comparison"]
    a = validation_outputs["assignments"]["with_temp"].set_index("pl_name")["cluster_id"].astype(int)
    b = validation_outputs["assignments"]["without_temp"].set_index("pl_name")["cluster_id"].astype(int)
    assert a.index.tolist() == b.index.tolist()
    assert adjusted_rand_score(a, b) == pytest.approx(report_summary["adjusted_rand_index"])
    mapping = {int(k): int(v) for k, v in report_summary["matched_clusters_by_maximum_membership_overlap"].items()}
    right_to_left = {right: left for left, right in mapping.items()}
    changed = b.map(right_to_left).to_numpy() != a.to_numpy()
    changed_frame = validation_outputs["changed"]
    assert int(changed.sum()) == report_summary["changed_planet_count"] == len(changed_frame)
    assert changed_frame["pl_name"].is_unique
    comparison = validation_outputs["temperature_comparison"]
    assert len(comparison) == 16
    assert comparison["cluster_with_temp"].nunique() == 4
    assert comparison["cluster_without_temp"].nunique() == 4
    assert int(comparison["is_one_to_one_profile_match"].sum()) == 4
    assert comparison["jaccard_membership_overlap"].between(0, 1).all()
    assert comparison["discovery_method_composition_total_variation_distance"].between(0, 1).all()
    matched = comparison.loc[comparison.is_one_to_one_profile_match]
    assert matched["discovery_method_composition_total_variation_distance"].mean() == pytest.approx(
        report_summary["matched_cluster_discovery_method_composition_total_variation_mean"]
    )

    source = validation_outputs["source"].set_index("pl_name")
    for row in comparison.to_dict(orient="records"):
        ids_a = validation_outputs["assignments"]["with_temp"].loc[
            validation_outputs["assignments"]["with_temp"].cluster_id == row["cluster_with_temp"], "pl_name"
        ].astype(str)
        ids_b = validation_outputs["assignments"]["without_temp"].loc[
            validation_outputs["assignments"]["without_temp"].cluster_id == row["cluster_without_temp"], "pl_name"
        ].astype(str)
        methods_a = source.loc[ids_a, "discoverymethod"].fillna("Unreported").astype(str).value_counts()
        methods_b = source.loc[ids_b, "discoverymethod"].fillna("Unreported").astype(str).value_counts()
        categories = set(methods_a.index) | set(methods_b.index)
        tv = sum(abs(methods_a.get(cat, 0) / len(ids_a) - methods_b.get(cat, 0) / len(ids_b)) for cat in categories) / 2
        assert row["discovery_method_composition_total_variation_distance"] == pytest.approx(tv)


def test_outputs_include_valid_labelled_svg_plots_and_expected_files(validation_outputs) -> None:
    directory = validation_outputs["directory"]
    expected = {
        "cluster_distribution_validation.csv", "cluster_silhouette_validation.csv", "cluster_separation.csv",
        "discovery_method_counts.csv", "discovery_method_row_percentages.csv",
        "discovery_method_column_percentages.csv", "discovery_method_tests.json",
        "temperature_feature_comparison.csv", "temperature_feature_membership_changes.csv",
        "k_selection_comparison.csv", "cluster_validation_report.md", "cluster_validation_report.json",
    }
    assert expected.issubset({path.name for path in directory.iterdir()})
    plots = sorted((directory / "plots").glob("*.svg"))
    assert len(plots) == 8
    for plot in plots:
        tree = ET.parse(plot)
        text = " ".join(node.text or "" for node in tree.iter() if node.tag.endswith("text"))
        assert "K=4" in text
        assert "Source:" in text
        assert "Fraction of cluster per histogram bin" in text
        assert any(unit in text for unit in ("Earth radii", "days", "K", "dimensionless"))
        if any(feature in plot.name for feature in ("pl_rade", "pl_orbper", "pl_eqt")):
            assert "logarithmic axis" in text
        else:
            assert "logarithmic axis" not in text


def test_source_and_preprocessing_hashes_remain_unchanged(validation_outputs) -> None:
    integrity = validation_outputs["report"]["integrity"]
    assert integrity["preserved_inputs_unchanged"] is True
    assert integrity["input_sha256_before"] == integrity["input_sha256_after"]
    for relative_path, expected in integrity["input_sha256_before"].items():
        assert sha256_file(ROOT / relative_path) == expected
    source_key = "data/raw/PSCompPars_2026.10.30_13.47.46.csv"
    assert integrity["input_sha256_before"][source_key] == PRE_MOVE_SHA256


def test_validation_pipeline_outputs_are_reproducible(validation_outputs) -> None:
    first = validation_outputs["report"]
    second = run_validation_pipeline(ROOT)
    assert second["integrity"]["generated_output_sha256"] == first["integrity"]["generated_output_sha256"]
    assert second["temperature_comparison"] == first["temperature_comparison"]
    assert second["discovery_method_tests"] == first["discovery_method_tests"]
    saved = json.loads((validation_outputs["directory"] / "cluster_validation_report.json").read_text(encoding="utf-8"))
    assert saved["integrity"]["generated_output_sha256"] == first["integrity"]["generated_output_sha256"]

