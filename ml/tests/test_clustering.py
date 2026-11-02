"""Integrity and metric tests for the K-means experiment outputs."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import adjusted_rand_score

from ml.clustering import (
    K_VALUES,
    PRIMARY_SEED,
    STABILITY_SEEDS,
    feature_columns,
    fit_kmeans,
    validate_feature_frame,
)
from ml.clustering_pipeline import (
    EXPERIMENT_OUTPUT_DIR,
    MASTER_RELATIVE_PATH,
    MODEL_OUTPUT_DIR,
    ROOT,
    SCALER_WITH_TEMP_RELATIVE_PATH,
    SCALER_WITHOUT_TEMP_RELATIVE_PATH,
    SOURCE_RELATIVE_PATH,
    WITH_TEMP_RELATIVE_PATH,
    WITHOUT_TEMP_RELATIVE_PATH,
)
from ml.data_audit import sha256_file


@pytest.fixture(scope="module")
def clustering_outputs():
    directory = ROOT / EXPERIMENT_OUTPUT_DIR
    report = json.loads((directory / "clustering_report.json").read_text(encoding="utf-8"))
    return {
        "directory": directory,
        "report": report,
        "master": pd.read_csv(ROOT / MASTER_RELATIVE_PATH, low_memory=False),
        "matrices": {
            "with_temp": pd.read_csv(ROOT / WITH_TEMP_RELATIVE_PATH, low_memory=False),
            "without_temp": pd.read_csv(ROOT / WITHOUT_TEMP_RELATIVE_PATH, low_memory=False),
        },
        "assignments": {
            experiment: {
                k: pd.read_csv(directory / f"cluster_assignments_{experiment}_k{k}.csv")
                for k in K_VALUES
            }
            for experiment in ("with_temp", "without_temp")
        },
        "metrics": pd.read_csv(directory / "experiment_metrics.csv"),
        "stability": pd.read_csv(directory / "stability_metrics.csv"),
        "profiles": {
            "with_temp": pd.read_csv(directory / "cluster_profiles_with_temp.csv"),
            "without_temp": pd.read_csv(directory / "cluster_profiles_without_temp.csv"),
        },
        "sensitivity": pd.read_csv(directory / "temperature_sensitivity.csv"),
    }


def test_both_experiments_use_the_same_ordered_planet_identifiers(clustering_outputs) -> None:
    with_ids = clustering_outputs["matrices"]["with_temp"]["pl_name"].tolist()
    without_ids = clustering_outputs["matrices"]["without_temp"]["pl_name"].tolist()
    assert with_ids == without_ids
    assert len(with_ids) == 5_273
    assert clustering_outputs["report"]["dataset"]["ordered_identifiers_match_between_experiments"]


def test_feature_selection_excludes_temperature_from_experiment_b(clustering_outputs) -> None:
    with_columns = feature_columns("with_temp")
    without_columns = feature_columns("without_temp")
    assert with_columns == (
        "scaled_log10_pl_rade",
        "scaled_log10_pl_orbper",
        "scaled_pl_eqt",
        "scaled_pl_orbeccen",
    )
    assert without_columns == (
        "scaled_log10_pl_rade",
        "scaled_log10_pl_orbper",
        "scaled_pl_orbeccen",
    )
    frame = clustering_outputs["matrices"]["without_temp"]
    assert "pl_eqt" in frame.columns  # Preserved physical measurement.
    assert "scaled_pl_eqt" not in frame.columns
    assert "scaled_pl_eqt" not in without_columns
    assert validate_feature_frame(frame, "without_temp").shape == (5_273, 3)


def test_k_values_two_through_eight_are_reported_for_both_experiments(clustering_outputs) -> None:
    metrics = clustering_outputs["metrics"]
    assert set(metrics["k"].astype(int)) == set(K_VALUES)
    assert len(metrics) == 2 * len(K_VALUES)
    assert set(metrics.groupby("experiment")["k"].nunique()) == {len(K_VALUES)}


def test_report_records_the_complete_kmeans_configuration(clustering_outputs) -> None:
    config = clustering_outputs["report"]["configuration"]
    assert config["estimator"] == "sklearn.cluster.KMeans"
    assert config["init"] == "k-means++"
    assert config["n_init"] == 20
    assert config["max_iter"] == 300
    assert config["primary_random_state"] == 42
    assert config["algorithm"] == "lloyd"
    assert config["tol"] == pytest.approx(1e-4)
    assert config["copy_x"] is True
    assert config["verbose"] == 0


def test_seed42_assignments_cover_all_observations_without_missing_labels(clustering_outputs) -> None:
    for experiment, by_k in clustering_outputs["assignments"].items():
        matrix = clustering_outputs["matrices"][experiment]
        for assignment in by_k.values():
            assert list(assignment.columns) == ["pl_name", "cluster_id"]
            assert len(assignment) == 5_273
            assert assignment["pl_name"].tolist() == matrix["pl_name"].tolist()
            assert assignment["pl_name"].is_unique
            assert assignment["cluster_id"].notna().all()


def test_cluster_sizes_sum_to_5273_and_have_no_empty_clusters(clustering_outputs) -> None:
    for row in clustering_outputs["metrics"].to_dict(orient="records"):
        sizes = json.loads(row["cluster_sizes"])
        assert sum(sizes.values()) == 5_273
        assert len(sizes) == int(row["k"])
        assert all(int(size) > 0 for size in sizes.values())
        assert json.loads(row["empty_cluster_ids"]) == []


def test_profiles_use_original_physical_units_and_correct_medians(clustering_outputs) -> None:
    master = clustering_outputs["master"].set_index("pl_name")
    feature_units = {
        "pl_rade": "Earth radii",
        "pl_orbper": "days",
        "pl_eqt": "K",
        "pl_orbeccen": "dimensionless",
    }
    assert set(feature_units) == {"pl_rade", "pl_orbper", "pl_eqt", "pl_orbeccen"}
    for experiment, profiles in clustering_outputs["profiles"].items():
        for profile in profiles.to_dict(orient="records"):
            assignment = clustering_outputs["assignments"][experiment][int(profile["k"])]
            members = assignment.loc[
                assignment["cluster_id"] == profile["cluster_id"], "pl_name"
            ]
            assert int(profile["planet_count"]) == len(members)
            assert profile["planet_percent"] == pytest.approx(len(members) / 5_273 * 100)
            physical = master.loc[members.tolist()]
            for feature in feature_units:
                assert profile[f"{feature}_median"] == pytest.approx(
                    physical[feature].median()
                )
                assert profile[f"{feature}_iqr"] == pytest.approx(
                    physical[feature].quantile(0.75) - physical[feature].quantile(0.25)
                )


def test_seed42_primary_models_reproduce_assignments(clustering_outputs) -> None:
    experiment = "with_temp"
    values = validate_feature_frame(clustering_outputs["matrices"][experiment], experiment)
    for k in K_VALUES:
        assignments = clustering_outputs["assignments"][experiment][k]
        saved = joblib.load(ROOT / MODEL_OUTPUT_DIR / f"kmeans_{experiment}_k{k}.joblib")
        np.testing.assert_array_equal(saved.predict(values), assignments["cluster_id"])
    first = fit_kmeans(values, k=2, random_state=PRIMARY_SEED)
    second = fit_kmeans(values, k=2, random_state=PRIMARY_SEED)
    np.testing.assert_array_equal(first.labels_, second.labels_)
    assert first.inertia_ == pytest.approx(second.inertia_, rel=0, abs=1e-10)


def test_stability_seed_count_and_ari_calculation(clustering_outputs) -> None:
    stability = clustering_outputs["stability"]
    summaries = clustering_outputs["report"]["stability"]["summary"]
    for experiment in ("with_temp", "without_temp"):
        for k in K_VALUES:
            group = stability.loc[
                (stability["experiment"] == experiment) & (stability["k"] == k)
            ]
            assert set(group["seed"].astype(int)) == set(STABILITY_SEEDS)
            primary = group.loc[group["seed"] == PRIMARY_SEED].iloc[0]
            assert primary["ari_vs_seed42"] == pytest.approx(1.0)
            summary = next(
                row for row in summaries if row["experiment"] == experiment and row["k"] == k
            )
            independent = group.loc[group["seed"] != PRIMARY_SEED]
            assert summary["seed_count"] == len(STABILITY_SEEDS)
            assert summary["inertia_mean"] == pytest.approx(group["inertia"].mean())
            assert summary["inertia_std"] == pytest.approx(group["inertia"].std(ddof=1))
            assert summary["silhouette_mean"] == pytest.approx(group["silhouette_score"].mean())
            assert summary["silhouette_std"] == pytest.approx(
                group["silhouette_score"].std(ddof=1)
            )
            assert summary["ari_mean_excluding_primary_self_comparison"] == pytest.approx(
                independent["ari_vs_seed42"].mean()
            )

    experiment = "with_temp"
    k = 2
    values = validate_feature_frame(clustering_outputs["matrices"][experiment], experiment)
    primary_labels = clustering_outputs["assignments"][experiment][k]["cluster_id"].to_numpy()
    independent_seed = 17
    rerun = fit_kmeans(values, k=k, random_state=independent_seed)
    expected_ari = adjusted_rand_score(primary_labels, rerun.labels_)
    row = clustering_outputs["stability"].loc[
        (clustering_outputs["stability"]["experiment"] == experiment)
        & (clustering_outputs["stability"]["k"] == k)
        & (clustering_outputs["stability"]["seed"] == independent_seed)
    ].iloc[0]
    assert row["ari_vs_seed42"] == pytest.approx(expected_ari)


def test_temperature_sensitivity_uses_matching_ids_and_primary_labels(clustering_outputs) -> None:
    for k in K_VALUES:
        with_assignment = clustering_outputs["assignments"]["with_temp"][k]
        without_assignment = clustering_outputs["assignments"]["without_temp"][k]
        assert with_assignment["pl_name"].tolist() == without_assignment["pl_name"].tolist()
    for row in clustering_outputs["sensitivity"].to_dict(orient="records"):
        k = int(row["k"])
        with_labels = clustering_outputs["assignments"]["with_temp"][k]["cluster_id"]
        without_labels = clustering_outputs["assignments"]["without_temp"][k]["cluster_id"]
        expected = adjusted_rand_score(with_labels, without_labels)
        assert row["observations"] == 5_273
        assert row["adjusted_rand_index"] == pytest.approx(expected)


def test_raw_source_and_preprocessing_artifacts_remain_unchanged(clustering_outputs) -> None:
    integrity = clustering_outputs["report"]["input_integrity"]
    assert integrity["raw_and_preprocessing_inputs_unchanged"] is True
    assert integrity["before_sha256"] == integrity["after_sha256"]
    for relative_path, digest in integrity["before_sha256"].items():
        assert sha256_file(ROOT / relative_path) == digest
    assert SOURCE_RELATIVE_PATH.as_posix() in integrity["before_sha256"]
    assert SCALER_WITH_TEMP_RELATIVE_PATH.as_posix() in integrity["before_sha256"]
    assert SCALER_WITHOUT_TEMP_RELATIVE_PATH.as_posix() in integrity["before_sha256"]
    assert WITH_TEMP_RELATIVE_PATH.as_posix() in integrity["before_sha256"]
    assert WITHOUT_TEMP_RELATIVE_PATH.as_posix() in integrity["before_sha256"]
