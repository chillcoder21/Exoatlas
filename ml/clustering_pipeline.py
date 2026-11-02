"""Run reproducible K-means experiments on the approved prepared cohorts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import adjusted_rand_score

from .clustering import (
    ALGORITHM,
    COPY_X,
    EXPERIMENT_FEATURES,
    EXPERIMENT_LABELS,
    INIT,
    K_VALUES,
    MAX_ITER,
    N_INIT,
    PHYSICAL_FEATURES,
    PHYSICAL_UNITS,
    PRIMARY_SEED,
    SILHOUETTE_METRIC,
    SMALL_CLUSTER_PERCENT,
    STABILITY_SEEDS,
    TOL,
    VERBOSE,
    cluster_size_diagnostics,
    evaluate_partition,
    feature_columns,
    feature_diagnostics,
    fit_kmeans,
    profile_clusters,
    summarize_stability,
    validate_feature_frame,
)
from .data_audit import PRE_MOVE_SHA256, sha256_file


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RELATIVE_PATH = Path("data/raw/PSCompPars_2026.10.30_13.47.46.csv")
MASTER_RELATIVE_PATH = Path("data/processed/planets_master.csv")
WITH_TEMP_RELATIVE_PATH = Path("data/processed/clustering_features_with_temp.csv")
WITHOUT_TEMP_RELATIVE_PATH = Path("data/processed/clustering_features_without_temp.csv")
SCALER_WITH_TEMP_RELATIVE_PATH = Path("artifacts/preprocessing/scaler_with_temp.joblib")
SCALER_WITHOUT_TEMP_RELATIVE_PATH = Path("artifacts/preprocessing/scaler_without_temp.joblib")
PREPROCESSING_JSON_RELATIVE_PATH = Path("data/metadata/preprocessing_report.json")
PREPROCESSING_MARKDOWN_RELATIVE_PATH = Path("data/metadata/preprocessing_report.md")
EXPERIMENT_OUTPUT_DIR = Path("data/cluster_experiments")
MODEL_OUTPUT_DIR = Path("artifacts/clustering")
REQUIRED_OUTPUT_FILES = (
    "experiment_metrics.csv",
    "stability_metrics.csv",
    "cluster_profiles_with_temp.csv",
    "cluster_profiles_without_temp.csv",
    "temperature_sensitivity.csv",
    "feature_diagnostics.json",
)
ASSIGNMENT_FILENAMES = tuple(
    f"cluster_assignments_{experiment}_k{k}.csv"
    for experiment in EXPERIMENT_FEATURES
    for k in K_VALUES
)


def _hash_paths(root: Path, paths: list[Path]) -> dict[str, str]:
    return {path.as_posix(): sha256_file(root / path) for path in paths}


def _assert_same_hashes(before: dict[str, str], after: dict[str, str]) -> None:
    changed = [name for name, digest in before.items() if after.get(name) != digest]
    if changed:
        raise RuntimeError(f"Raw or approved preprocessing inputs changed during clustering: {changed}")


def _load_inputs(root: Path) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict[str, Any], dict[str, str]]:
    """Read approved outputs and verify their provenance and feature wiring."""
    input_paths = [
        SOURCE_RELATIVE_PATH,
        MASTER_RELATIVE_PATH,
        WITH_TEMP_RELATIVE_PATH,
        WITHOUT_TEMP_RELATIVE_PATH,
        SCALER_WITH_TEMP_RELATIVE_PATH,
        SCALER_WITHOUT_TEMP_RELATIVE_PATH,
        PREPROCESSING_JSON_RELATIVE_PATH,
        PREPROCESSING_MARKDOWN_RELATIVE_PATH,
    ]
    before_hashes = _hash_paths(root, input_paths)
    if before_hashes[SOURCE_RELATIVE_PATH.as_posix()] != PRE_MOVE_SHA256:
        raise RuntimeError("The raw source SHA-256 differs from the audited snapshot.")

    preprocessing_report = json.loads(
        (root / PREPROCESSING_JSON_RELATIVE_PATH).read_text(encoding="utf-8")
    )
    if preprocessing_report["dataset"]["source_sha256_after"] != PRE_MOVE_SHA256:
        raise RuntimeError("The preprocessing report does not identify the approved source snapshot.")
    if preprocessing_report["eligibility"]["eligible_four_feature_records"] != 5_273:
        raise RuntimeError("The preprocessing report does not identify the approved 5,273-record cohort.")

    for relative_path in (
        MASTER_RELATIVE_PATH,
        WITH_TEMP_RELATIVE_PATH,
        WITHOUT_TEMP_RELATIVE_PATH,
        SCALER_WITH_TEMP_RELATIVE_PATH,
        SCALER_WITHOUT_TEMP_RELATIVE_PATH,
    ):
        expected = preprocessing_report["outputs"]["sha256"].get(relative_path.as_posix())
        if expected is None or before_hashes[relative_path.as_posix()] != expected:
            raise RuntimeError(
                f"Approved preprocessing artifact hash mismatch: {relative_path.as_posix()}"
            )

    master = pd.read_csv(root / MASTER_RELATIVE_PATH, low_memory=False)
    matrices = {
        "with_temp": pd.read_csv(root / WITH_TEMP_RELATIVE_PATH, low_memory=False),
        "without_temp": pd.read_csv(root / WITHOUT_TEMP_RELATIVE_PATH, low_memory=False),
    }
    if len(master) != 6_451 or master["pl_name"].isna().any() or master["pl_name"].duplicated().any():
        raise ValueError("The master data must preserve all 6,451 unique planet identifiers.")
    if any(len(matrix) != 5_273 for matrix in matrices.values()):
        raise ValueError("Both clustering matrices must contain exactly 5,273 observations.")
    identifiers = matrices["with_temp"]["pl_name"].tolist()
    if identifiers != matrices["without_temp"]["pl_name"].tolist():
        raise ValueError("The primary matrices do not have matching ordered planet identifiers.")
    if identifiers != master.loc[
        master["eligible_four_feature_clustering"].astype(bool), "pl_name"
    ].tolist():
        raise ValueError("Feature matrix IDs do not match the ordered eligible master cohort.")

    scalers = {
        "with_temp": joblib.load(root / SCALER_WITH_TEMP_RELATIVE_PATH),
        "without_temp": joblib.load(root / SCALER_WITHOUT_TEMP_RELATIVE_PATH),
    }
    scaler_report_names = {"with_temp": "with_temperature", "without_temp": "without_temperature"}
    for experiment, frame in matrices.items():
        values = validate_feature_frame(frame, experiment)
        scaler = scalers[experiment]
        expected_features = feature_columns(experiment)
        scaler_summary = preprocessing_report["experiments"][scaler_report_names[experiment]]["scaler"]
        if scaler.n_features_in_ != len(expected_features) or scaler.n_samples_seen_ != len(frame):
            raise ValueError(f"Scaler dimensions do not match experiment {experiment}.")
        np.testing.assert_allclose(scaler.mean_, scaler_summary["mean"], rtol=0, atol=1e-12)
        np.testing.assert_allclose(scaler.scale_, scaler_summary["scale"], rtol=0, atol=1e-12)
        np.testing.assert_allclose(values.mean(axis=0), 0.0, atol=1e-10)
        np.testing.assert_allclose(values.std(axis=0, ddof=0), 1.0, atol=1e-10)
    if "scaled_pl_eqt" in feature_columns("without_temp"):
        raise AssertionError("Experiment B must not pass equilibrium temperature to K-means.")
    return master, matrices, {**preprocessing_report, "scalers": scalers}, before_hashes


def _csv_safe_records(frame: pd.DataFrame, json_columns: tuple[str, ...] = ()) -> pd.DataFrame:
    """Serialize nested metric values as stable JSON text in CSV cells."""
    output = frame.copy()
    for column in json_columns:
        if column in output.columns:
            output[column] = output[column].map(
                lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"))
            )
    return output


def _profile_all_k(
    master: pd.DataFrame,
    assignments: dict[str, dict[int, pd.DataFrame]],
) -> dict[str, pd.DataFrame]:
    return {
        experiment: pd.concat(
            [
                profile_clusters(
                    master,
                    assignments[experiment][k],
                    experiment=experiment,
                    k=k,
                )
                for k in K_VALUES
            ],
            ignore_index=True,
        )
        for experiment in EXPERIMENT_FEATURES
    }


def _json_write(path: Path, content: Any) -> None:
    path.write_text(
        json.dumps(content, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _markdown_report(report: dict[str, Any], diagnostics: dict[str, Any]) -> str:
    lines = [
        "# ExoAtlas K-means Experiment Report",
        "",
        "## Dataset and method",
        "",
        f"- Source snapshot: `{report['dataset']['source_name']}` (download snapshot 2026-10-30).",
        f"- Source SHA-256: `{report['dataset']['source_sha256']}`; raw data and approved preprocessing artifacts were unchanged during the run.",
        "- Observations: **5,273 planets** in both experiments, with identical `pl_name` values in the same order.",
        f"- Primary K-means: `init={INIT}`, `n_init={N_INIT}`, `max_iter={MAX_ITER}`, `tol={TOL}`, `copy_x={COPY_X}`, `verbose={VERBOSE}`, primary `random_state={PRIMARY_SEED}`, algorithm `{ALGORITHM}`.",
        f"- Stability seeds: {', '.join(str(seed) for seed in STABILITY_SEEDS)} (10 total, including primary seed 42).",
        f"- Evaluation: full-cohort Euclidean silhouette; same method and observations in both feature configurations. The small-cluster review flag is under {SMALL_CLUSTER_PERCENT:g}% of the cohort ({report['diagnostics']['small_cluster_review_threshold_count']:.2f} observations), and does not filter data.",
        "",
        "Experiment A passed `scaled_log10_pl_rade`, `scaled_log10_pl_orbper`, `scaled_pl_eqt`, and `scaled_pl_orbeccen` to K-means. Experiment B passed only `scaled_log10_pl_rade`, `scaled_log10_pl_orbper`, and `scaled_pl_orbeccen`. Its raw `pl_eqt` column is retained in the CSV for context but excluded from the model input. Existing StandardScaler artifacts were loaded and verified; no new scaler was fitted and no feature was transformed again.",
        "",
        "K-means labels are arbitrary partition identifiers. These profiles describe assigned observations; they are not established scientific planet types. No K was selected automatically.",
        "",
        "## Primary seed-42 results",
        "",
        "Inertia values are specific to each feature space, so compare their trends within an experiment rather than interpreting cross-configuration differences as directly equivalent. Silhouette is a full-data Euclidean separation summary and does not alone determine a suitable K.",
        "",
        "| Experiment | K | Inertia | Silhouette | Clusters | Cluster sizes (ID: count) | Min | Max | Mean | Iterations | Reached max_iter | Clusters below 1% |",
        "|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|---|",
    ]
    for row in report["primary_metrics"]:
        sizes = ", ".join(f"{cluster}:{count}" for cluster, count in row["cluster_sizes"].items())
        tiny = ", ".join(
            f"{item['cluster_id']} ({item['planet_count']})"
            for item in row["small_clusters_below_one_percent"]
        ) or "none"
        lines.append(
            f"| {row['experiment']} | {row['k']} | {row['inertia']:.6f} | {row['silhouette_score']:.6f} | "
            f"{row['cluster_count']} | {sizes} | {row['cluster_size_min']} | {row['cluster_size_max']} | "
            f"{row['cluster_size_mean']:.2f} | {row['n_iter']} | {row['reached_max_iter']} | {tiny} |"
        )

    lines.extend([
        "",
        "## Random-initialization stability",
        "",
        "Each experiment/K has 10 runs. Inertia and silhouette mean/SD cover all 10 runs. ARI mean/SD compares the nine non-primary seeds with the seed-42 labels; the seed-42 self-comparison (ARI=1) is present in `stability_metrics.csv` but excluded from that summary to avoid inflating stability. Standard deviations below use the sample convention (ddof=1).",
        "",
        "| Experiment | K | Runs | Inertia mean +/- SD | Silhouette mean +/- SD | ARI mean +/- SD vs seed 42 (9 runs) |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for row in report["stability"]["summary"]:
        lines.append(
            f"| {row['experiment']} | {row['k']} | {row['seed_count']} | "
            f"{row['inertia_mean']:.6f} +/- {row['inertia_std']:.6f} | "
            f"{row['silhouette_mean']:.6f} +/- {row['silhouette_std']:.6f} | "
            f"{row['ari_mean_excluding_primary_self_comparison']:.6f} +/- "
            f"{row['ari_std_excluding_primary_self_comparison']:.6f} |"
        )

    lines.extend([
        "",
        "## Temperature-feature sensitivity",
        "",
        "Adjusted Rand Index (ARI) compares the two seed-42 partitions at each K. It describes partition sensitivity to the feature configuration; it does not show that temperature causes a difference.",
        "",
        "| K | ARI (A vs B) | A clusters | B clusters | Observations per experiment |",
        "|---:|---:|---:|---:|---:|",
    ])
    for row in report["temperature_sensitivity"]:
        lines.append(
            f"| {row['k']} | {row['adjusted_rand_index']:.6f} | {row['clusters_with_temp']} | "
            f"{row['clusters_without_temp']} | {row['observations']} |"
        )

    lines.extend([
        "",
        "## Cluster profiles in physical units",
        "",
        "The two profile CSVs contain one row per seed-42 cluster at each K. They report planet count and percentage, plus median, Q1, Q3, IQR, mean, and sample standard deviation for radius (Earth radii), orbital period (days), equilibrium temperature (K), and eccentricity (dimensionless). Profiles use original measurements from the master dataset, not standardized values.",
        "",
        "Cluster IDs have no physical ordering or scientific type label. A change in profile between K values reflects a different partition of the same cohort, not a validated taxonomy.",
        "",
        "## Feature distributions, correlations, and extreme observations",
        "",
        "`feature_diagnostics.json` records distributions and the Pearson correlation matrix for the exact standardized columns passed to each experiment. It also lists the five largest absolute standardized observations per input feature, with identifiers, raw physical values, and their seed-42 cluster assignment at each K.",
        "",
    ])
    for experiment in EXPERIMENT_FEATURES:
        info = diagnostics[experiment]
        strongest = info["strongest_absolute_feature_correlations"]
        if strongest:
            best = strongest[0]
            lines.append(
                f"- {experiment}: largest absolute pairwise correlation is "
                f"{best['feature_a']} vs {best['feature_b']} (r={best['pearson_r']:.4f})."
            )
        else:
            lines.append(f"- {experiment}: only one input feature is present; no feature pair correlation applies.")
    eccentricity_extremes = diagnostics["with_temp"][
        "largest_absolute_standardized_observations_by_feature"
    ]["scaled_pl_orbeccen"]
    if len(eccentricity_extremes) >= 2:
        first, second = eccentricity_extremes[:2]
        same_cluster_every_k = all(
            first["cluster_id_by_k"][str(k)] == second["cluster_id_by_k"][str(k)]
            for k in K_VALUES
        )
        if same_cluster_every_k:
            lines.append(
                "The two largest absolute standardized eccentricity observations "
                f"({first['pl_name']} and {second['pl_name']}) are assigned together at every K "
                "in both feature configurations. This is a descriptive grouping of extreme values, "
                "not evidence that they caused a boundary; no outlier-removal sensitivity run was done."
            )
    lines.append(
        "Cluster-size tables above include empty clusters and review-only under-1% clusters. No empty clusters or observations were silently removed, merged, or filtered. Extreme-value assignments are descriptive; identifying influence causally would require a separately approved sensitivity experiment."
    )

    lines.extend([
        "",
        "## Outputs and limitations",
        "",
        "- `experiment_metrics.csv`: seed-42 metrics for both experiments and K=2..8.",
        "- `stability_metrics.csv`: per-seed metrics and ARI against the seed-42 partition.",
        "- `cluster_profiles_with_temp.csv` and `cluster_profiles_without_temp.csv`: physical-unit summaries for every primary cluster.",
        "- `temperature_sensitivity.csv`: A-vs-B ARI for each K.",
        "- Assignment files named `cluster_assignments_<experiment>_k<K>.csv`: one seed-42 `pl_name,cluster_id` file for every experiment/K pair.",
        "- `feature_diagnostics.json`, `clustering_report.json`, and this report: input distributions/correlations, size diagnostics, settings, results, hashes, and interpretation limits.",
        "- `artifacts/clustering/`: 14 fitted seed-42 K-means models, one for each experiment/K combination.",
        "",
        "K-means favors compact Euclidean clusters, and silhouette, inertia, and initialization stability capture different properties. They are evidence for review, not an automatic K selector. The analysis makes no causal claims, adds no features, removes no observations, and does not establish scientific planet classes.",
        "",
    ])
    return "\n".join(lines)


def run_clustering_pipeline(root: Path = ROOT) -> dict[str, Any]:
    """Run primary and stability experiments, profiles, diagnostics, and reports."""
    root = Path(root)
    master, matrices, preprocessing, input_hashes_before = _load_inputs(root)
    output_dir = root / EXPERIMENT_OUTPUT_DIR
    model_dir = root / MODEL_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    primary_metrics: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []
    assignments: dict[str, dict[int, pd.DataFrame]] = {name: {} for name in EXPERIMENT_FEATURES}
    labels_by_experiment: dict[str, dict[int, np.ndarray]] = {name: {} for name in EXPERIMENT_FEATURES}
    model_paths: list[Path] = []

    for experiment in EXPERIMENT_FEATURES:
        frame = matrices[experiment]
        values = validate_feature_frame(frame, experiment)
        seed_labels_by_k: dict[int, dict[int, np.ndarray]] = {}
        for k in K_VALUES:
            seed_models: dict[int, Any] = {}
            seed_metrics: dict[int, dict[str, Any]] = {}
            seed_labels_by_k[k] = {}
            for seed in STABILITY_SEEDS:
                model = fit_kmeans(values, k=k, random_state=seed)
                labels = model.labels_.astype(np.int64, copy=True)
                metrics = evaluate_partition(
                    values,
                    labels,
                    k=k,
                    inertia=model.inertia_,
                    n_iter=model.n_iter_,
                )
                seed_models[seed] = model
                seed_metrics[seed] = metrics
                seed_labels_by_k[k][seed] = labels

            primary_model = seed_models[PRIMARY_SEED]
            primary_labels = seed_labels_by_k[k][PRIMARY_SEED]
            labels_by_experiment[experiment][k] = primary_labels
            metric = {
                "experiment": experiment,
                "experiment_label": EXPERIMENT_LABELS[experiment],
                "k": k,
                "observations": int(len(frame)),
                "feature_columns_passed_to_kmeans": list(feature_columns(experiment)),
                "primary_seed": PRIMARY_SEED,
                "init": INIT,
                "n_init": N_INIT,
                "max_iter": MAX_ITER,
                "algorithm": ALGORITHM,
                "tol": TOL,
                "copy_x": COPY_X,
                "verbose": VERBOSE,
                **seed_metrics[PRIMARY_SEED],
                "cluster_sizes": seed_metrics[PRIMARY_SEED]["cluster_sizes"],
                "small_clusters_below_one_percent": seed_metrics[PRIMARY_SEED][
                    "small_clusters_below_one_percent"
                ],
            }
            primary_metrics.append(metric)

            model_relative_path = MODEL_OUTPUT_DIR / f"kmeans_{experiment}_k{k}.joblib"
            model_path = root / model_relative_path
            joblib.dump(primary_model, model_path, compress=3, protocol=5)
            model_paths.append(model_relative_path)

            assignments[experiment][k] = pd.DataFrame(
                {"pl_name": frame["pl_name"].astype(str), "cluster_id": primary_labels}
            )

            for seed in STABILITY_SEEDS:
                seed_metric = seed_metrics[seed]
                stability_rows.append(
                    {
                        "experiment": experiment,
                        "k": k,
                        "seed": seed,
                        "is_primary_seed": seed == PRIMARY_SEED,
                        "observations": len(frame),
                        "feature_columns_passed_to_kmeans": json.dumps(
                            list(feature_columns(experiment)), separators=(",", ":")
                        ),
                        "inertia": seed_metric["inertia"],
                        "silhouette_score": seed_metric["silhouette_score"],
                        "cluster_count": seed_metric["cluster_count"],
                        "cluster_size_min": seed_metric["cluster_size_min"],
                        "cluster_size_max": seed_metric["cluster_size_max"],
                        "cluster_size_mean": seed_metric["cluster_size_mean"],
                        "n_iter": seed_metric["n_iter"],
                        "reached_max_iter": seed_metric["reached_max_iter"],
                        "ari_vs_seed42": float(
                            adjusted_rand_score(primary_labels, seed_labels_by_k[k][seed])
                        ),
                    }
                )

    primary_metrics_frame = pd.DataFrame(primary_metrics)
    stability_frame = pd.DataFrame(stability_rows)
    stability_summary_frame = summarize_stability(stability_frame)

    assignment_files: dict[str, dict[int, str]] = {name: {} for name in EXPERIMENT_FEATURES}
    for experiment in EXPERIMENT_FEATURES:
        for k in K_VALUES:
            frame = matrices[experiment]
            assignment = pd.DataFrame(
                {"pl_name": frame["pl_name"].astype(str), "cluster_id": labels_by_experiment[experiment][k]}
            )
            if assignment["pl_name"].tolist() != matrices["with_temp"]["pl_name"].tolist():
                raise AssertionError("A K run changed the ordered observation identifiers.")
            filename = f"cluster_assignments_{experiment}_k{k}.csv"
            assignment.to_csv(output_dir / filename, index=False, encoding="utf-8")
            assignment_files[experiment][k] = filename
            assignments[experiment][k] = assignment

    profile_tables = _profile_all_k(master, assignments)
    for experiment, filename in (
        ("with_temp", "cluster_profiles_with_temp.csv"),
        ("without_temp", "cluster_profiles_without_temp.csv"),
    ):
        profile_tables[experiment].to_csv(
            output_dir / filename,
            index=False,
            encoding="utf-8",
            float_format="%.17g",
        )

    primary_metric_records = primary_metrics_frame.to_dict(orient="records")
    stability_records = stability_frame.to_dict(orient="records")
    stability_summary_records = stability_summary_frame.to_dict(orient="records")
    sensitivity_rows: list[dict[str, Any]] = []
    for k in K_VALUES:
        with_labels = labels_by_experiment["with_temp"][k]
        without_labels = labels_by_experiment["without_temp"][k]
        if matrices["with_temp"]["pl_name"].tolist() != matrices["without_temp"]["pl_name"].tolist():
            raise AssertionError("Temperature comparison requires identical ordered planet IDs.")
        sensitivity_rows.append(
            {
                "k": k,
                "observations": len(with_labels),
                "adjusted_rand_index": float(adjusted_rand_score(with_labels, without_labels)),
                "clusters_with_temp": int(len(np.unique(with_labels))),
                "clusters_without_temp": int(len(np.unique(without_labels))),
                "interpretation": "Partition sensitivity to feature configuration; not a causal effect.",
            }
        )
    sensitivity_frame = pd.DataFrame(sensitivity_rows)
    sensitivity_records = sensitivity_frame.to_dict(orient="records")

    diagnostics_by_experiment = {
        experiment: feature_diagnostics(
            matrices[experiment],
            experiment,
            labels_by_experiment[experiment],
        )
        for experiment in EXPERIMENT_FEATURES
    }
    diagnostics = {
        "method": {
            "feature_distribution_basis": "The standardized feature columns actually passed to K-means.",
            "correlation": "Pearson correlation of the exact standardized K-means input columns.",
            "small_cluster_review_flag": {
                "threshold_percent": SMALL_CLUSTER_PERCENT,
                "threshold_count": 5_273 * SMALL_CLUSTER_PERCENT / 100.0,
                "meaning": "Clusters under this share are listed for review only; no filtering or merging occurs.",
            },
            "extreme_observation_rule": "Five largest absolute standardized input values per feature are listed as review leads.",
        },
        "cluster_size_diagnostics_by_experiment_and_k": cluster_size_diagnostics(primary_metrics_frame),
        "experiments": diagnostics_by_experiment,
    }
    _json_write(output_dir / "feature_diagnostics.json", diagnostics)

    sensitivity_csv_path = output_dir / "temperature_sensitivity.csv"
    sensitivity_frame.to_csv(sensitivity_csv_path, index=False, encoding="utf-8", float_format="%.17g")
    metrics_csv_path = output_dir / "experiment_metrics.csv"
    metrics_csv = _csv_safe_records(
        primary_metrics_frame,
        json_columns=("feature_columns_passed_to_kmeans", "cluster_sizes", "small_clusters_below_one_percent", "empty_cluster_ids"),
    )
    metrics_csv.to_csv(metrics_csv_path, index=False, encoding="utf-8", float_format="%.17g")
    stability_frame.to_csv(
        output_dir / "stability_metrics.csv",
        index=False,
        encoding="utf-8",
        float_format="%.17g",
    )

    input_hashes_after = _hash_paths(
        root,
        [
            SOURCE_RELATIVE_PATH,
            MASTER_RELATIVE_PATH,
            WITH_TEMP_RELATIVE_PATH,
            WITHOUT_TEMP_RELATIVE_PATH,
            SCALER_WITH_TEMP_RELATIVE_PATH,
            SCALER_WITHOUT_TEMP_RELATIVE_PATH,
            PREPROCESSING_JSON_RELATIVE_PATH,
            PREPROCESSING_MARKDOWN_RELATIVE_PATH,
        ],
    )
    _assert_same_hashes(input_hashes_before, input_hashes_after)

    produced_paths = [EXPERIMENT_OUTPUT_DIR / name for name in REQUIRED_OUTPUT_FILES]
    produced_paths.extend(EXPERIMENT_OUTPUT_DIR / name for name in ASSIGNMENT_FILENAMES)
    produced_paths.extend(model_paths)
    output_hashes = _hash_paths(root, produced_paths)
    report: dict[str, Any] = {
        "dataset": {
            "source_name": SOURCE_RELATIVE_PATH.name,
            "source_path": SOURCE_RELATIVE_PATH.as_posix(),
            "source_snapshot_date": "2026-10-30",
            "source_sha256": PRE_MOVE_SHA256,
            "source_records": int(len(master)),
            "source_columns": 84,
            "cohort_records": 5_273,
            "ordered_planet_identifier_column": "pl_name",
            "ordered_identifiers_match_between_experiments": matrices["with_temp"]["pl_name"].tolist()
            == matrices["without_temp"]["pl_name"].tolist(),
        },
        "configuration": {
            "estimator": "sklearn.cluster.KMeans",
            "init": INIT,
            "n_init": N_INIT,
            "max_iter": MAX_ITER,
            "primary_random_state": PRIMARY_SEED,
            "stability_seeds": list(STABILITY_SEEDS),
            "k_values": list(K_VALUES),
            "algorithm": ALGORITHM,
            "tol": TOL,
            "copy_x": COPY_X,
            "verbose": VERBOSE,
            "silhouette_metric": SILHOUETTE_METRIC,
            "silhouette_evaluation": "Exact full-cohort silhouette score; no sampling.",
            "standardized_feature_columns_passed_to_kmeans": {
                experiment: list(feature_columns(experiment)) for experiment in EXPERIMENT_FEATURES
            },
            "temperature_excluded_from_experiment_b": "scaled_pl_eqt is not included in Experiment B feature columns.",
            "existing_scalers_loaded_and_verified": True,
            "scalers_refit": False,
            "features_retransformed": False,
        },
        "input_integrity": {
            "before_sha256": input_hashes_before,
            "after_sha256": input_hashes_after,
            "raw_and_preprocessing_inputs_unchanged": input_hashes_before == input_hashes_after,
        },
        "primary_metrics": primary_metric_records,
        "stability": {
            "individual_run_count": len(stability_records),
            "seed_count_per_experiment_and_k": len(STABILITY_SEEDS),
            "ari_summary_excludes_seed42_self_comparison": True,
            "standard_deviation_convention": "Sample standard deviation (ddof=1).",
            "summary": stability_summary_records,
            "metrics_csv": "data/cluster_experiments/stability_metrics.csv",
        },
        "temperature_sensitivity": sensitivity_records,
        "cluster_profiles": {
            experiment: {
                "path": str(EXPERIMENT_OUTPUT_DIR / filename).replace("\\", "/"),
                "rows": int(len(profile_tables[experiment])),
                "statistics": ["planet_count", "planet_percent", "median", "q1", "q3", "iqr", "mean", "std"],
                "physical_features_and_units": PHYSICAL_UNITS,
                "uses_original_physical_measurements": True,
                "cluster_ids_are_scientific_types": False,
            }
            for experiment, filename in (
                ("with_temp", "cluster_profiles_with_temp.csv"),
                ("without_temp", "cluster_profiles_without_temp.csv"),
            )
        },
        "diagnostics": {
            "path": "data/cluster_experiments/feature_diagnostics.json",
            "small_cluster_review_threshold_percent": SMALL_CLUSTER_PERCENT,
            "small_cluster_review_threshold_count": 5_273 * SMALL_CLUSTER_PERCENT / 100.0,
            "automatic_k_selection": False,
            "outlier_filtering": False,
            "causal_claims": False,
        },
        "interpretation_limits": [
            "Inertia is tied to each feature space and is not directly comparable across different dimensions.",
            "Silhouette is a Euclidean separation summary, not a standalone K-selection rule.",
            "ARI between feature configurations measures partition sensitivity and does not establish causation.",
            "Extreme standardized observations and small clusters are review findings; observations are not removed or merged.",
            "Cluster IDs describe partitions, not established scientific planet types.",
            "The experiment does not assess host-star dependence or validate scientific classes.",
        ],
        "outputs": {
            "directory": EXPERIMENT_OUTPUT_DIR.as_posix(),
            "primary_assignment_files": {
                experiment: {
                    str(k): (EXPERIMENT_OUTPUT_DIR / filename).as_posix()
                    for k, filename in per_k.items()
                }
                for experiment, per_k in assignment_files.items()
            },
            "model_artifacts": [path.as_posix() for path in model_paths],
            "sha256": output_hashes,
            "report_json": (EXPERIMENT_OUTPUT_DIR / "clustering_report.json").as_posix(),
            "report_markdown": (EXPERIMENT_OUTPUT_DIR / "clustering_report.md").as_posix(),
        },
        "runtime": {
            "python": __import__("platform").python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
        },
    }
    report_json_path = output_dir / "clustering_report.json"
    report_md_path = output_dir / "clustering_report.md"
    _json_write(report_json_path, report)
    report_md_path.write_text(_markdown_report(report, diagnostics_by_experiment), encoding="utf-8", newline="\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Project root with approved preprocessing outputs")
    args = parser.parse_args()
    report = run_clustering_pipeline(args.root)
    print(
        f"K-means experiments complete: {report['dataset']['cohort_records']:,} observations, "
        f"{len(report['primary_metrics'])} primary runs, "
        f"{report['stability']['individual_run_count']} stability runs."
    )
    print(f"Reports: {args.root / EXPERIMENT_OUTPUT_DIR / 'clustering_report.md'} and "
          f"{args.root / EXPERIMENT_OUTPUT_DIR / 'clustering_report.json'}")


if __name__ == "__main__":
    main()
