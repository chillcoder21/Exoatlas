"""K-means evaluation helpers for the two approved ExoAtlas feature sets."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score


K_VALUES = tuple(range(2, 9))
PRIMARY_SEED = 42
STABILITY_SEEDS = (42, 17, 23, 29, 31, 37, 43, 47, 53, 59)
N_INIT = 20
MAX_ITER = 300
INIT = "k-means++"
ALGORITHM = "lloyd"
TOL = 1e-4
COPY_X = True
VERBOSE = 0
SILHOUETTE_METRIC = "euclidean"
SMALL_CLUSTER_PERCENT = 1.0

EXPERIMENT_FEATURES = {
    "with_temp": (
        "scaled_log10_pl_rade",
        "scaled_log10_pl_orbper",
        "scaled_pl_eqt",
        "scaled_pl_orbeccen",
    ),
    "without_temp": (
        "scaled_log10_pl_rade",
        "scaled_log10_pl_orbper",
        "scaled_pl_orbeccen",
    ),
}
EXPERIMENT_LABELS = {
    "with_temp": "Experiment A - four features including temperature",
    "without_temp": "Experiment B - three features excluding temperature",
}
PHYSICAL_FEATURES = ("pl_rade", "pl_orbper", "pl_eqt", "pl_orbeccen")
PHYSICAL_UNITS = {
    "pl_rade": "Earth radii",
    "pl_orbper": "days",
    "pl_eqt": "K",
    "pl_orbeccen": "dimensionless",
}


def feature_columns(experiment: str) -> tuple[str, ...]:
    """Return the exact standardized CSV columns passed to K-means."""
    try:
        return EXPERIMENT_FEATURES[experiment]
    except KeyError as exc:
        raise ValueError(f"Unknown clustering experiment: {experiment}") from exc


def validate_feature_frame(frame: pd.DataFrame, experiment: str) -> np.ndarray:
    """Validate IDs and return only the configured finite K-means inputs."""
    columns = feature_columns(experiment)
    absent = [name for name in ("pl_name", *columns) if name not in frame.columns]
    if absent:
        raise ValueError(f"Clustering input is missing required columns: {absent}")
    if frame["pl_name"].isna().any() or frame["pl_name"].duplicated().any():
        raise ValueError("Clustering input must contain unique, nonmissing pl_name identifiers.")
    values = frame.loc[:, columns].to_numpy(dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError(f"Experiment {experiment} has missing or non-finite feature values.")
    return values


def fit_kmeans(values: np.ndarray, k: int, random_state: int = PRIMARY_SEED) -> KMeans:
    """Fit K-means using the milestone's fixed initialization settings."""
    if k not in K_VALUES:
        raise ValueError(f"K must be between 2 and 8 inclusive; received {k}.")
    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        raise ValueError("K-means requires a finite two-dimensional feature matrix.")
    if matrix.shape[0] <= k:
        raise ValueError("K must be smaller than the number of observations.")
    model = KMeans(
        n_clusters=k,
        init=INIT,
        n_init=N_INIT,
        max_iter=MAX_ITER,
        random_state=int(random_state),
        algorithm=ALGORITHM,
        tol=TOL,
        copy_x=COPY_X,
        verbose=VERBOSE,
    )
    model.fit(matrix)
    return model


def evaluate_partition(
    values: np.ndarray,
    labels: Sequence[int],
    *,
    k: int,
    inertia: float,
    n_iter: int,
    max_iter: int = MAX_ITER,
) -> dict[str, Any]:
    """Calculate requested full-data metrics and descriptive size diagnostics."""
    matrix = np.asarray(values, dtype=np.float64)
    assignments = np.asarray(labels, dtype=np.int64)
    if len(assignments) != len(matrix):
        raise ValueError("Each observation must have exactly one cluster assignment.")
    if pd.isna(assignments).any():
        raise ValueError("Cluster labels cannot be missing.")

    counts = np.bincount(assignments, minlength=k)
    sizes = [int(value) for value in counts]
    observed_labels = int(np.count_nonzero(counts))
    if observed_labels < 2:
        raise ValueError("Silhouette score requires at least two nonempty clusters.")
    score = float(
        silhouette_score(matrix, assignments, metric=SILHOUETTE_METRIC)
    )
    minimum = int(min(sizes))
    maximum = int(max(sizes))
    mean = float(np.mean(sizes))
    small_threshold_count = float(len(assignments)) * SMALL_CLUSTER_PERCENT / 100.0
    small_clusters = [
        {"cluster_id": cluster_id, "planet_count": size, "percent": size / len(assignments) * 100}
        for cluster_id, size in enumerate(sizes)
        if size / len(assignments) * 100 < SMALL_CLUSTER_PERCENT
    ]
    return {
        "inertia": float(inertia),
        "silhouette_score": score,
        "cluster_count": observed_labels,
        "cluster_sizes": {str(index): count for index, count in enumerate(sizes)},
        "cluster_sizes_ordered": sizes,
        "cluster_size_min": minimum,
        "cluster_size_max": maximum,
        "cluster_size_mean": mean,
        "cluster_size_std": float(np.std(sizes, ddof=0)),
        "cluster_size_max_min_ratio": float(maximum / minimum) if minimum else None,
        "empty_cluster_ids": [index for index, size in enumerate(sizes) if size == 0],
        "small_clusters_below_one_percent": small_clusters,
        "small_cluster_review_threshold_percent": SMALL_CLUSTER_PERCENT,
        "small_cluster_review_threshold_count": small_threshold_count,
        "n_iter": int(n_iter),
        "reached_max_iter": bool(n_iter >= max_iter),
    }


def summarize_stability(runs: pd.DataFrame) -> pd.DataFrame:
    """Summarize repeat-run metrics; omit seed 42's self-ARI from ARI summary."""
    rows: list[dict[str, Any]] = []
    for (experiment, k), group in runs.groupby(["experiment", "k"], sort=True):
        independent = group.loc[group["seed"] != PRIMARY_SEED]
        rows.append(
            {
                "experiment": str(experiment),
                "k": int(k),
                "seed_count": int(group["seed"].nunique()),
                "ari_comparison_seed_count": int(len(independent)),
                "inertia_mean": float(group["inertia"].mean()),
                "inertia_std": float(group["inertia"].std(ddof=1)),
                "silhouette_mean": float(group["silhouette_score"].mean()),
                "silhouette_std": float(group["silhouette_score"].std(ddof=1)),
                "ari_mean_excluding_primary_self_comparison": float(
                    independent["ari_vs_seed42"].mean()
                ),
                "ari_std_excluding_primary_self_comparison": float(
                    independent["ari_vs_seed42"].std(ddof=1)
                ),
            }
        )
    return pd.DataFrame(rows)


def profile_clusters(
    master: pd.DataFrame,
    assignments: pd.DataFrame,
    *,
    experiment: str,
    k: int,
) -> pd.DataFrame:
    """Profile seed-42 memberships using source measurements and physical units."""
    if not {"pl_name", "cluster_id"}.issubset(assignments.columns):
        raise ValueError("Assignments must have pl_name and cluster_id columns.")
    source = master.loc[:, ["pl_name", *PHYSICAL_FEATURES]].copy()
    joined = assignments.merge(source, on="pl_name", how="left", validate="one_to_one")
    if joined.loc[:, list(PHYSICAL_FEATURES)].isna().any().any():
        raise ValueError("A cluster profile is missing an original physical measurement.")

    total = len(joined)
    rows: list[dict[str, Any]] = []
    for cluster_id, group in joined.groupby("cluster_id", sort=True):
        row: dict[str, Any] = {
            "experiment": experiment,
            "k": int(k),
            "cluster_id": int(cluster_id),
            "planet_count": int(len(group)),
            "planet_percent": float(len(group) / total * 100),
        }
        for feature in PHYSICAL_FEATURES:
            values = pd.to_numeric(group[feature], errors="raise")
            q1 = float(values.quantile(0.25))
            median = float(values.quantile(0.50))
            q3 = float(values.quantile(0.75))
            row[f"{feature}_median"] = median
            row[f"{feature}_q1"] = q1
            row[f"{feature}_q3"] = q3
            row[f"{feature}_iqr"] = q3 - q1
            row[f"{feature}_mean"] = float(values.mean())
            row[f"{feature}_std"] = float(values.std(ddof=1)) if len(values) > 1 else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def feature_diagnostics(
    frame: pd.DataFrame,
    experiment: str,
    primary_labels_by_k: dict[int, np.ndarray],
) -> dict[str, Any]:
    """Describe actual standardized K-means inputs, correlations, and extremes."""
    columns = feature_columns(experiment)
    values = validate_feature_frame(frame, experiment)
    feature_statistics: dict[str, Any] = {}
    extreme_input_observations: dict[str, list[dict[str, Any]]] = {}
    raw_for_feature = {
        "scaled_log10_pl_rade": ("pl_rade", "log10_pl_rade"),
        "scaled_log10_pl_orbper": ("pl_orbper", "log10_pl_orbper"),
        "scaled_pl_eqt": ("pl_eqt", "pl_eqt"),
        "scaled_pl_orbeccen": ("pl_orbeccen", "pl_orbeccen"),
    }
    data = frame.loc[:, list(columns)].astype("float64")
    for position, name in enumerate(columns):
        series = data[name]
        q1, median, q3 = (float(series.quantile(q)) for q in (0.25, 0.5, 0.75))
        feature_statistics[name] = {
            "records": int(len(series)),
            "minimum": float(series.min()),
            "q1": q1,
            "median": median,
            "q3": q3,
            "maximum": float(series.max()),
            "mean": float(series.mean()),
            "standard_deviation_sample": float(series.std(ddof=1)),
            "zero_count": int(series.eq(0).sum()),
            "correlation_method": "Pearson correlation of the standardized K-means input columns",
        }

        absolute_order = np.argsort(np.abs(values[:, position]))[::-1][:5]
        physical_feature, transformed_feature = raw_for_feature[name]
        examples: list[dict[str, Any]] = []
        for row_position in absolute_order:
            example: dict[str, Any] = {
                "pl_name": str(frame.iloc[row_position]["pl_name"]),
                "hostname": str(frame.iloc[row_position]["hostname"]),
                "source_data_record_number": int(frame.iloc[row_position]["source_data_record_number"]),
                "standardized_feature_value": float(values[row_position, position]),
                "original_physical_feature": physical_feature,
                "original_physical_value": float(frame.iloc[row_position][physical_feature]),
                "transformed_feature_column": transformed_feature,
                "cluster_id_by_k": {
                    str(k): int(labels[row_position])
                    for k, labels in sorted(primary_labels_by_k.items())
                },
            }
            examples.append(example)
        extreme_input_observations[name] = examples

    correlation = data.corr(method="pearson")
    correlation_matrix = {
        str(row): {str(column): float(correlation.loc[row, column]) for column in columns}
        for row in columns
    }
    pairs: list[dict[str, Any]] = []
    for left_index, left in enumerate(columns):
        for right in columns[left_index + 1 :]:
            pairs.append(
                {
                    "feature_a": left,
                    "feature_b": right,
                    "pearson_r": float(correlation.loc[left, right]),
                    "absolute_pearson_r": abs(float(correlation.loc[left, right])),
                }
            )
    pairs.sort(key=lambda item: (-item["absolute_pearson_r"], item["feature_a"], item["feature_b"]))
    return {
        "label": EXPERIMENT_LABELS[experiment],
        "observations": len(frame),
        "feature_columns_passed_to_kmeans": list(columns),
        "feature_distributions_on_standardized_inputs": feature_statistics,
        "pearson_correlation_matrix": correlation_matrix,
        "strongest_absolute_feature_correlations": pairs[:5],
        "largest_absolute_standardized_observations_by_feature": extreme_input_observations,
        "extreme_value_interpretation": (
            "Largest absolute standardized observations are diagnostic review leads. "
            "Their assignment does not establish that the corresponding measurement is invalid "
            "or that it caused a cluster boundary."
        ),
    }


def cluster_size_diagnostics(metrics: pd.DataFrame) -> dict[str, Any]:
    """Expose imbalance and the declared under-one-percent review flag by K."""
    output: dict[str, Any] = {}
    for row in metrics.to_dict(orient="records"):
        key = f"{row['experiment']}_k{row['k']}"
        output[key] = {
            "cluster_sizes": row["cluster_sizes"],
            "minimum_size": int(row["cluster_size_min"]),
            "maximum_size": int(row["cluster_size_max"]),
            "mean_size": float(row["cluster_size_mean"]),
            "max_min_ratio": row["cluster_size_max_min_ratio"],
            "empty_cluster_ids": row["empty_cluster_ids"],
            "clusters_below_one_percent": row["small_clusters_below_one_percent"],
        }
    return output
