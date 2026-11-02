"""Build ExoAtlas application data from the frozen, previously saved model run.

This module only joins approved source/preprocessing outputs and existing K-means
assignments. It never fits a model, transforms features, imputes measurements,
or changes the raw NASA CSV.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .data_audit import PRE_MOVE_SHA256, sha256_file


ROOT = Path(__file__).resolve().parents[1]
RAW_RELATIVE = Path("data/raw/PSCompPars_2026.10.30_13.47.46.csv")
MASTER_RELATIVE = Path("data/processed/planets_master.csv")
ASSIGNMENT_RELATIVE = Path("data/cluster_experiments/cluster_assignments_with_temp_k4.csv")
PROFILE_RELATIVE = Path("data/cluster_experiments/cluster_profiles_with_temp.csv")
APPLICATION_RELATIVE = Path("data/processed/planets_application.csv")
CLUSTER_METADATA_RELATIVE = Path("data/metadata/cluster_profiles.json")
APPLICATION_REPORT_RELATIVE = Path("data/metadata/application_data_report.json")
REGISTRY_RELATIVE = Path("artifacts/clustering/model_registry.json")
FEATURES = ("pl_rade", "pl_orbper", "pl_eqt", "pl_orbeccen")
FEATURE_UNITS = {
    "pl_rade": "Earth radii",
    "pl_orbper": "days",
    "pl_eqt": "K",
    "pl_orbeccen": "dimensionless",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256(root: Path, relative: str | Path) -> str:
    return sha256_file(root / relative)


def _build_application_frame(root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Join the existing primary assignments onto every master record."""
    audit = _read_json(root / "data/metadata/dataset_audit.json")
    prep = _read_json(root / "data/metadata/preprocessing_report.json")
    cluster_report = _read_json(root / "data/cluster_experiments/clustering_report.json")
    validation = _read_json(root / "data/cluster_validation/cluster_validation_report.json")

    source_hash = _sha256(root, RAW_RELATIVE)
    if source_hash != PRE_MOVE_SHA256 or source_hash != audit["source"]["sha256_after_move"]:
        raise ValueError("Raw NASA CSV does not match the audited source snapshot.")
    if source_hash != prep["dataset"]["source_sha256_after"]:
        raise ValueError("Preprocessing report references a different source checksum.")
    if source_hash != cluster_report["dataset"]["source_sha256"]:
        raise ValueError("Clustering report references a different source checksum.")
    if source_hash != validation["dataset"]["source_sha256"]:
        raise ValueError("Validation report references a different source checksum.")

    expected_master_hash = prep["outputs"]["sha256"][MASTER_RELATIVE.as_posix()]
    if _sha256(root, MASTER_RELATIVE) != expected_master_hash:
        raise ValueError("The approved preprocessing master file has changed.")
    expected_assignment_hash = cluster_report["outputs"]["sha256"][ASSIGNMENT_RELATIVE.as_posix()]
    if _sha256(root, ASSIGNMENT_RELATIVE) != expected_assignment_hash:
        raise ValueError("The saved primary K=4 assignments have changed.")

    master = pd.read_csv(root / MASTER_RELATIVE, low_memory=False, dtype={"pl_name": "string"})
    assignments = pd.read_csv(
        root / ASSIGNMENT_RELATIVE,
        low_memory=False,
        dtype={"pl_name": "string", "cluster_id": "int64"},
    )
    expected_records = int(audit["dataset_overview"]["records"])
    expected_cohort = int(prep["eligibility"]["eligible_four_feature_records"])
    if len(master) != expected_records or len(master) != int(prep["outputs"]["master_records"]):
        raise ValueError("The preprocessing master does not contain all audited records.")
    if "pl_name" not in master or master["pl_name"].isna().any() or master["pl_name"].duplicated().any():
        raise ValueError("The master must have a unique, nonmissing pl_name for every record.")
    if list(assignments.columns) != ["pl_name", "cluster_id"]:
        raise ValueError("Unexpected primary assignment schema; expected pl_name,cluster_id.")
    if len(assignments) != expected_cohort or assignments["pl_name"].isna().any():
        raise ValueError("Primary assignments do not match the approved cohort size.")
    if assignments["pl_name"].duplicated().any():
        raise ValueError("Primary assignments contain duplicate planet identifiers.")
    if set(assignments["cluster_id"].unique()) != {0, 1, 2, 3}:
        raise ValueError("Primary K=4 assignment labels are not exactly 0 through 3.")
    if "eligible_four_feature_clustering" not in master:
        raise ValueError("The master is missing its approved four-feature eligibility indicator.")
    eligible_ids = master.loc[
        master["eligible_four_feature_clustering"].astype(bool), "pl_name"
    ].tolist()
    if eligible_ids != assignments["pl_name"].tolist():
        raise ValueError("Assignment IDs/order differ from the approved primary cohort.")
    if not set(assignments["pl_name"]).issubset(set(master["pl_name"])):
        raise ValueError("An assignment identifier is not present in the master dataset.")

    application = master.merge(
        assignments,
        how="left",
        on="pl_name",
        sort=False,
        validate="one_to_one",
    )
    application["cluster_id"] = application["cluster_id"].astype("Int64")
    application["assignment_status"] = application["cluster_id"].notna().map(
        {True: "assigned", False: "unassigned"}
    )
    if len(application) != expected_records or application["pl_name"].tolist() != master["pl_name"].tolist():
        raise AssertionError("Application data did not preserve every master record in source order.")
    if int(application["cluster_id"].notna().sum()) != expected_cohort:
        raise AssertionError("Application assigned count differs from the primary cohort size.")
    return application, {
        "source_records": expected_records,
        "assigned_records": expected_cohort,
        "unassigned_records": expected_records - expected_cohort,
        "source_sha256": source_hash,
        "source_columns": int(audit["dataset_overview"]["columns"]),
    }


def _cluster_profiles(root: Path, cohort_size: int) -> dict[str, Any]:
    """Create compact physical-unit profiles from the saved K=4 profile table."""
    profiles = pd.read_csv(root / PROFILE_RELATIVE, low_memory=False)
    rows = profiles.loc[(profiles["experiment"] == "with_temp") & (profiles["k"] == 4)]
    if len(rows) != 4 or rows["cluster_id"].astype(int).tolist() != [0, 1, 2, 3]:
        raise ValueError("Expected exactly four saved with-temperature K=4 profiles.")

    result: list[dict[str, Any]] = []
    for row in rows.to_dict(orient="records"):
        cluster_id = int(row["cluster_id"])
        count = int(row["planet_count"])
        physical: dict[str, Any] = {}
        for feature in FEATURES:
            physical[feature] = {
                "unit": FEATURE_UNITS[feature],
                "median": float(row[f"{feature}_median"]),
                "q1": float(row[f"{feature}_q1"]),
                "q3": float(row[f"{feature}_q3"]),
                "iqr": float(row[f"{feature}_iqr"]),
            }
        summary = (
            f"In this assigned cohort, median measured radius is {physical['pl_rade']['median']:g} Earth radii, "
            f"median orbital period is {physical['pl_orbper']['median']:g} days, median equilibrium temperature "
            f"is {physical['pl_eqt']['median']:g} K, and median eccentricity is "
            f"{physical['pl_orbeccen']['median']:g}. These are descriptive sample statistics."
        )
        result.append({
            "cluster_id": cluster_id,
            "planet_count": count,
            "percent_of_eligible_cohort": float(count / cohort_size * 100.0),
            "physical_features": physical,
            "descriptive_summary": summary,
        })
    if sum(item["planet_count"] for item in result) != cohort_size:
        raise ValueError("Saved K=4 profile counts do not sum to the eligible cohort.")
    return {
        "schema_version": 1,
        "model_id": "exoatlas-kmeans-with-temperature-k4",
        "cohort_size": cohort_size,
        "interpretation": "Cluster IDs are exploratory partition labels, not established astronomical types.",
        "clusters": result,
    }


def _model_registry(root: Path) -> dict[str, Any]:
    """Record model metadata and comparison artifact references from saved reports."""
    clustering = _read_json(root / "data/cluster_experiments/clustering_report.json")
    validation = _read_json(root / "data/cluster_validation/cluster_validation_report.json")
    preprocessing = _read_json(root / "data/metadata/preprocessing_report.json")
    preprocessing_path = Path("data/metadata/preprocessing_report.json")
    clustering_path = Path("data/cluster_experiments/clustering_report.json")
    validation_path = Path("data/cluster_validation/cluster_validation_report.json")
    primary = next(
        item for item in clustering["primary_metrics"]
        if item["experiment"] == "with_temp" and int(item["k"]) == 4
    )
    stability = next(
        item for item in clustering["stability"]["summary"]
        if item["experiment"] == "with_temp" and int(item["k"]) == 4
    )
    val_silhouette = next(
        item for item in validation["silhouette_cluster_summary"]
        if item["experiment"] == "with_temp" and item["cluster_id"] == "ALL"
    )
    feature_columns = clustering["configuration"]["standardized_feature_columns_passed_to_kmeans"]["with_temp"]
    scaler_path = Path("artifacts/preprocessing/scaler_with_temp.joblib")
    scaler_hash = _sha256(root, scaler_path)
    if scaler_hash != preprocessing["outputs"]["sha256"].get(scaler_path.as_posix()):
        raise ValueError("The saved with-temperature StandardScaler differs from the approved preprocessing report.")

    def candidate(experiment: str, k: int) -> dict[str, Any]:
        assignment = Path(f"data/cluster_experiments/cluster_assignments_{experiment}_k{k}.csv")
        model = Path(f"artifacts/clustering/kmeans_{experiment}_k{k}.joblib")
        metric = next(
            item for item in clustering["primary_metrics"]
            if item["experiment"] == experiment and int(item["k"]) == k
        )
        model_hash = _sha256(root, model)
        assignment_hash = _sha256(root, assignment)
        if model_hash != clustering["outputs"]["sha256"].get(model.as_posix()):
            raise ValueError(f"Saved model artifact differs from the clustering report: {model.as_posix()}")
        if assignment_hash != clustering["outputs"]["sha256"].get(assignment.as_posix()):
            raise ValueError(f"Saved assignment file differs from the clustering report: {assignment.as_posix()}")
        return {
            "experiment": experiment,
            "k": k,
            "cohort_size": int(metric["observations"]),
            "silhouette": float(metric["silhouette_score"]),
            "random_seed": int(metric["primary_seed"]),
            "model_artifact": model.as_posix(),
            "model_sha256": model_hash,
            "assignment_file": assignment.as_posix(),
            "assignment_sha256": assignment_hash,
            "feature_columns_passed_to_kmeans": metric["feature_columns_passed_to_kmeans"],
        }

    primary_candidate = candidate("with_temp", 4)
    return {
        "schema_version": 1,
        "primary_model": {
            "model_id": "exoatlas-kmeans-with-temperature-k4",
            "version": "1.0.0",
            "status": "frozen_exploratory_primary",
            "experiment": "with_temp",
            "k": 4,
            "ordered_features": ["log10_pl_rade", "log10_pl_orbper", "pl_eqt", "pl_orbeccen"],
            "standardized_input_columns": feature_columns,
            "feature_definitions": [
                {"name": "log10_pl_rade", "source_column": "pl_rade", "transformation": "log10", "unit": "Earth radii before log10"},
                {"name": "log10_pl_orbper", "source_column": "pl_orbper", "transformation": "log10", "unit": "days before log10"},
                {"name": "pl_eqt", "source_column": "pl_eqt", "transformation": "raw value; standardized by saved StandardScaler", "unit": "K"},
                {"name": "pl_orbeccen", "source_column": "pl_orbeccen", "transformation": "raw value; standardized by saved StandardScaler; zeros preserved", "unit": "dimensionless"},
            ],
            "scaler": {
                "type": "sklearn.preprocessing.StandardScaler",
                "path": scaler_path.as_posix(),
                "sha256": scaler_hash,
            },
            "fitted_model": {
                "type": "sklearn.cluster.KMeans",
                "path": primary_candidate["model_artifact"],
                "sha256": primary_candidate["model_sha256"],
            },
            "assignments": {
                "path": primary_candidate["assignment_file"],
                "sha256": primary_candidate["assignment_sha256"],
            },
            "cohort_size": int(primary["observations"]),
            "random_seed": int(primary["primary_seed"]),
            "kmeans_configuration": {
                "init": primary["init"],
                "n_init": int(primary["n_init"]),
                "max_iter": int(primary["max_iter"]),
                "tol": float(primary["tol"]),
                "algorithm": primary["algorithm"],
                "copy_x": bool(primary["copy_x"]),
                "verbose": int(primary["verbose"]),
                "iterations_observed": int(primary["n_iter"]),
                "reached_max_iter": bool(primary["reached_max_iter"]),
            },
            "dataset": {
                "source_name": clustering["dataset"]["source_name"],
                "snapshot_date": clustering["dataset"]["source_snapshot_date"],
                "source_sha256": clustering["dataset"]["source_sha256"],
            },
            "reports": {
                "preprocessing": {"path": preprocessing_path.as_posix(), "sha256": _sha256(root, preprocessing_path)},
                "clustering": {"path": clustering_path.as_posix(), "sha256": _sha256(root, clustering_path)},
                "validation": {"path": validation_path.as_posix(), "sha256": _sha256(root, validation_path)},
            },
            "evaluation": {
                "silhouette_euclidean": float(val_silhouette["mean_silhouette"]),
                "stability_ari_mean_excluding_seed42_self_comparison": float(stability["ari_mean_excluding_primary_self_comparison"]),
                "stability_ari_sample_sd": float(stability["ari_std_excluding_primary_self_comparison"]),
                "negative_silhouette_count": int(val_silhouette["negative_silhouette_count"]),
                "negative_silhouette_percent": float(val_silhouette["negative_silhouette_percent"]),
            },
            "selection_rationale": (
                "The project explicitly approved the existing four-feature K=4 partition as the v1 exploratory application configuration. "
                "This is an application-design decision, not objective scientific model selection. It offers four profiles using the approved "
                "temperature-inclusive cohort and preserves a direct comparison set. Validation reports a lower silhouette than K=2 and K=3, "
                "while K=5 has a slightly higher silhouette; those alternatives remain available."
            ),
            "interpretation": "An exploratory grouping of confirmed exoplanets, not an established astronomical classification.",
            "limitations": [
                "Silhouette and seed stability are geometric diagnostics, not scientific validation by themselves.",
                "Feature inclusion changes the partition: the with-temperature versus no-temperature K=4 ARI is read from validation outputs.",
                "Extreme measurements were retained; IQR flags do not establish invalidity, and StandardScaler may be influenced by extremes.",
                "Discovery-method association reflects a selected catalogue and differing detection sensitivities; it is not causal.",
                "Validation treats planets as observations and does not model dependence among planets orbiting a shared host star.",
            ],
        },
        "comparison_configurations": [
            candidate("with_temp", 2),
            candidate("with_temp", 3),
            candidate("with_temp", 5),
            candidate("without_temp", 4),
        ],
        "source_sha256": clustering["dataset"]["source_sha256"],
    }


def run_application_data_pipeline(root: Path = ROOT) -> dict[str, Any]:
    """Generate app-ready CSV and metadata without refitting or changing inputs."""
    root = Path(root)
    application, counts = _build_application_frame(root)
    application_path = root / APPLICATION_RELATIVE
    application_path.parent.mkdir(parents=True, exist_ok=True)
    application.to_csv(
        application_path,
        index=False,
        encoding="utf-8",
        float_format="%.17g",
        lineterminator="\n",
    )

    cluster_metadata = _cluster_profiles(root, counts["assigned_records"])
    _write_json(root / CLUSTER_METADATA_RELATIVE, cluster_metadata)
    registry = _model_registry(root)
    _write_json(root / REGISTRY_RELATIVE, registry)

    report = {
        "schema_version": 1,
        "dataset": {
            "name": "NASA Exoplanet Archive PSCompPars",
            "source_snapshot_date": "2026-10-30",
            "source_sha256": counts["source_sha256"],
            "source_records": counts["source_records"],
            "source_columns": counts["source_columns"],
            "application_records": len(application),
            "original_source_columns_preserved": True,
            "planet_identifiers_unique_and_nonmissing": True,
            "assignment_status_counts": {
                "assigned": counts["assigned_records"],
                "unassigned": counts["unassigned_records"],
            },
        },
        "primary_model_id": registry["primary_model"]["model_id"],
        "outputs": {
            APPLICATION_RELATIVE.as_posix(): _sha256(root, APPLICATION_RELATIVE),
            CLUSTER_METADATA_RELATIVE.as_posix(): _sha256(root, CLUSTER_METADATA_RELATIVE),
            REGISTRY_RELATIVE.as_posix(): _sha256(root, REGISTRY_RELATIVE),
        },
        "input_sha256": {
            RAW_RELATIVE.as_posix(): counts["source_sha256"],
            MASTER_RELATIVE.as_posix(): _sha256(root, MASTER_RELATIVE),
            ASSIGNMENT_RELATIVE.as_posix(): _sha256(root, ASSIGNMENT_RELATIVE),
            PROFILE_RELATIVE.as_posix(): _sha256(root, PROFILE_RELATIVE),
        },
    }
    _write_json(root / APPLICATION_REPORT_RELATIVE, report)
    return report


def main() -> None:
    report = run_application_data_pipeline()
    dataset = report["dataset"]
    print(
        "Application dataset ready: "
        f"{dataset['application_records']:,} total, "
        f"{dataset['assignment_status_counts']['assigned']:,} assigned, "
        f"{dataset['assignment_status_counts']['unassigned']:,} unassigned."
    )
    print(f"Output: {ROOT / APPLICATION_RELATIVE}")


if __name__ == "__main__":
    main()
