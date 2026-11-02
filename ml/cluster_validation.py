"""Scientific validation helpers for the approved ExoAtlas K-means runs.

This module reads saved assignments and feature matrices. It does not refit a
clustering model or alter any source or preprocessing data.
"""

from __future__ import annotations

import json
from html import escape
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.stats import chi2_contingency
from sklearn.metrics import adjusted_rand_score, silhouette_samples

from .clustering import feature_columns


PHYSICAL_FEATURES = {
    "pl_rade": "Earth radii",
    "pl_orbper": "days",
    "pl_eqt": "K",
    "pl_orbeccen": "dimensionless",
}
EXPERIMENTS = ("with_temp", "without_temp")


def _ordered_join(
    source: pd.DataFrame,
    assignments: pd.DataFrame,
    identifiers: list[str],
) -> pd.DataFrame:
    """Join source measurements to one assignment per requested planet ID."""
    if "pl_name" not in source or "pl_name" not in assignments:
        raise ValueError("Both source records and assignments must contain pl_name.")
    if source["pl_name"].isna().any() or source["pl_name"].duplicated().any():
        raise ValueError("Source planet identifiers must be present and unique.")
    if assignments["pl_name"].isna().any() or assignments["pl_name"].duplicated().any():
        raise ValueError("Assignment planet identifiers must be present and unique.")
    if assignments["pl_name"].astype(str).tolist() != identifiers:
        raise ValueError("Assignment identifiers do not match the ordered primary cohort.")
    joined = assignments.merge(source, on="pl_name", how="left", validate="one_to_one", indicator=True)
    if not joined["_merge"].eq("both").all() or len(joined) != len(identifiers):
        raise ValueError("Every assigned planet must join to exactly one source record.")
    return joined.drop(columns="_merge")


def cluster_distribution_validation(
    source: pd.DataFrame,
    assignments_by_experiment: dict[str, pd.DataFrame],
    identifiers: list[str],
) -> pd.DataFrame:
    """Summarize original physical measurements for every K=4 cluster."""
    rows: list[dict[str, Any]] = []
    for experiment, assignments in assignments_by_experiment.items():
        joined = _ordered_join(source, assignments, identifiers)
        if set(assignments["cluster_id"].astype(int).unique()) != {0, 1, 2, 3}:
            raise ValueError(f"{experiment} K=4 assignments must contain clusters 0 through 3.")
        for cluster_id, group in joined.groupby("cluster_id", sort=True):
            n = len(group)
            for feature, units in PHYSICAL_FEATURES.items():
                values = pd.to_numeric(group[feature], errors="coerce")
                if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
                    raise ValueError(f"{feature} has missing/non-finite primary-cohort values.")
                q1, median, q3 = (float(values.quantile(q)) for q in (0.25, 0.5, 0.75))
                rows.append({
                    "experiment": experiment,
                    "cluster_id": int(cluster_id),
                    "planet_count": int(n),
                    "planet_percent": float(n / len(identifiers) * 100),
                    "feature": feature,
                    "units": units,
                    "minimum": float(values.min()),
                    "q1": q1,
                    "median": median,
                    "q3": q3,
                    "iqr": q3 - q1,
                    "mean": float(values.mean()),
                    "standard_deviation": float(values.std(ddof=1)),
                    "maximum": float(values.max()),
                    "zero_value_count": int(values.eq(0).sum()),
                })
    return pd.DataFrame(rows)


def silhouette_validation(
    matrices: dict[str, pd.DataFrame],
    assignments_by_experiment: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate per-observation and per-cluster silhouette diagnostics."""
    observations: list[pd.DataFrame] = []
    summaries: list[dict[str, Any]] = []
    for experiment in EXPERIMENTS:
        matrix = matrices[experiment]
        assignment = assignments_by_experiment[experiment]
        if matrix["pl_name"].astype(str).tolist() != assignment["pl_name"].astype(str).tolist():
            raise ValueError(f"{experiment} feature rows and assignments are not identically ordered.")
        values = matrix.loc[:, feature_columns(experiment)].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"{experiment} K-means feature matrix contains non-finite values.")
        labels = assignment["cluster_id"].to_numpy(dtype=int)
        if len(np.unique(labels)) != 4:
            raise ValueError(f"{experiment} must contain exactly four assigned clusters.")
        scores = silhouette_samples(values, labels, metric="euclidean")
        table = pd.DataFrame({
            "experiment": experiment,
            "pl_name": assignment["pl_name"].astype(str),
            "cluster_id": labels,
            "silhouette_score": scores,
        })
        observations.append(table)
        for cluster_id, group in table.groupby("cluster_id", sort=True):
            cluster_scores = group["silhouette_score"]
            negative = int(cluster_scores.lt(0).sum())
            summaries.append({
                "experiment": experiment,
                "cluster_id": int(cluster_id),
                "planet_count": int(len(group)),
                "mean_silhouette": float(cluster_scores.mean()),
                "median_silhouette": float(cluster_scores.median()),
                "negative_silhouette_count": negative,
                "negative_silhouette_percent": float(negative / len(group) * 100),
                "silhouette_minimum": float(cluster_scores.min()),
                "silhouette_maximum": float(cluster_scores.max()),
            })
        negative = int(table["silhouette_score"].lt(0).sum())
        summaries.append({
            "experiment": experiment,
            "cluster_id": "ALL",
            "planet_count": int(len(table)),
            "mean_silhouette": float(table["silhouette_score"].mean()),
            "median_silhouette": float(table["silhouette_score"].median()),
            "negative_silhouette_count": negative,
            "negative_silhouette_percent": float(negative / len(table) * 100),
            "silhouette_minimum": float(table["silhouette_score"].min()),
            "silhouette_maximum": float(table["silhouette_score"].max()),
        })
    return pd.concat(observations, ignore_index=True), pd.DataFrame(summaries)


def _histogram_edges(values: np.ndarray, bins: int = 48) -> tuple[np.ndarray, bool]:
    """Choose common physical-value bins, logarithmic for broad positive ranges."""
    minimum, maximum = float(np.min(values)), float(np.max(values))
    if minimum > 0 and maximum / minimum >= 20:
        return np.geomspace(minimum, maximum, bins + 1), True
    if minimum == maximum:
        padding = max(abs(minimum) * 1e-6, 1e-9)
        return np.linspace(minimum - padding, maximum + padding, bins + 1), False
    return np.linspace(minimum, maximum, bins + 1), False


def separation_diagnostics(
    source: pd.DataFrame,
    matrices: dict[str, pd.DataFrame],
    assignments_by_experiment_k: dict[str, dict[int, pd.DataFrame]],
    identifiers: list[str],
) -> pd.DataFrame:
    """Report centroid distances and binned profile overlap for saved partitions."""
    rows: list[dict[str, Any]] = []
    for experiment, assignments_by_k in assignments_by_experiment_k.items():
        matrix = matrices[experiment]
        columns = feature_columns(experiment)
        values = matrix.loc[:, columns].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"{experiment} feature matrix contains non-finite values.")
        for k, assignment in sorted(assignments_by_k.items()):
            if assignment["pl_name"].astype(str).tolist() != identifiers:
                raise ValueError(f"{experiment} K={k} identifiers do not match the primary cohort.")
            labels = assignment["cluster_id"].to_numpy(dtype=int)
            clusters = sorted(np.unique(labels).tolist())
            if clusters != list(range(k)):
                raise ValueError(f"{experiment} K={k} assignment labels are not contiguous 0..K-1.")
            centroids = {cluster: values[labels == cluster].mean(axis=0) for cluster in clusters}
            for left, right in combinations(clusters, 2):
                rows.append({
                    "diagnostic": "standardized_centroid_distance",
                    "experiment": experiment,
                    "k": k,
                    "cluster_a": left,
                    "cluster_b": right,
                    "feature": "ALL_INPUT_FEATURES",
                    "distance_or_overlap": float(np.linalg.norm(centroids[left] - centroids[right])),
                    "method": "Euclidean distance between centroids in the exact standardized K-means input space",
                })

            joined = _ordered_join(source, assignment, identifiers)
            edges_by_feature: dict[str, tuple[np.ndarray, bool]] = {}
            for feature in PHYSICAL_FEATURES:
                all_values = pd.to_numeric(joined[feature], errors="coerce").to_numpy(dtype=float)
                edges_by_feature[feature] = _histogram_edges(all_values)
            for left, right in combinations(clusters, 2):
                for feature, units in PHYSICAL_FEATURES.items():
                    edges, logarithmic_bins = edges_by_feature[feature]
                    group_left = joined.loc[joined["cluster_id"].astype(int) == left, feature].to_numpy(dtype=float)
                    group_right = joined.loc[joined["cluster_id"].astype(int) == right, feature].to_numpy(dtype=float)
                    counts_left = np.histogram(group_left, bins=edges)[0].astype(float)
                    counts_right = np.histogram(group_right, bins=edges)[0].astype(float)
                    overlap = float(np.minimum(counts_left / counts_left.sum(), counts_right / counts_right.sum()).sum())
                    rows.append({
                        "diagnostic": "binned_univariate_overlap_coefficient",
                        "experiment": experiment,
                        "k": k,
                        "cluster_a": left,
                        "cluster_b": right,
                        "feature": feature,
                        "distance_or_overlap": overlap,
                        "units": units,
                        "method": (
                            "Sum of bin-wise minimum probability masses on shared physical-value bins; "
                            + ("geometric bins" if logarithmic_bins else "linear bins")
                        ),
                    })
    return pd.DataFrame(rows)


def discovery_method_validation(
    source: pd.DataFrame,
    assignments_by_experiment: dict[str, pd.DataFrame],
    identifiers: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Create discovery-method tables and Pearson chi-square/Cramer's V results."""
    full_method = source["discoverymethod"].fillna("Unreported").astype(str)
    source_counts = full_method.value_counts(sort=False).sort_index()
    counts_rows: list[dict[str, Any]] = []
    row_rows: list[dict[str, Any]] = []
    column_rows: list[dict[str, Any]] = []
    tests: dict[str, Any] = {"method": "Pearson chi-square test of independence; Cramer's V effect size."}
    counts_rows.extend({
        "experiment": "all_source",
        "scope": "full_source",
        "cluster_id": "ALL",
        "discoverymethod": str(method),
        "planet_count": int(count),
        "percent_of_scope": float(count / len(source) * 100),
    } for method, count in source_counts.items())
    tests["overall_discovery_method_distribution_full_source"] = {
        str(k): int(v) for k, v in source_counts.items()
    }

    primary_counts_by_experiment: dict[str, pd.Series] = {}
    for experiment, assignment in assignments_by_experiment.items():
        joined = _ordered_join(source, assignment, identifiers)
        joined["discoverymethod"] = joined["discoverymethod"].fillna("Unreported").astype(str)
        cohort_counts = joined["discoverymethod"].value_counts(sort=False).sort_index()
        primary_counts_by_experiment[experiment] = cohort_counts
        counts_rows.extend({
            "experiment": experiment,
            "scope": "primary_cohort",
            "cluster_id": "ALL",
            "discoverymethod": str(method),
            "planet_count": int(count),
            "percent_of_scope": float(count / len(joined) * 100),
        } for method, count in cohort_counts.items())

        table = pd.crosstab(joined["cluster_id"].astype(int), joined["discoverymethod"])
        table = table.reindex(index=sorted(joined["cluster_id"].astype(int).unique()), fill_value=0)
        for cluster_id in table.index:
            total = int(table.loc[cluster_id].sum())
            for method, count in table.loc[cluster_id].items():
                count = int(count)
                counts_rows.append({
                    "experiment": experiment,
                    "scope": "cluster",
                    "cluster_id": int(cluster_id),
                    "discoverymethod": str(method),
                    "planet_count": count,
                    "percent_of_scope": float(count / total * 100) if total else 0.0,
                })
                row_rows.append({
                    "experiment": experiment,
                    "cluster_id": int(cluster_id),
                    "discoverymethod": str(method),
                    "planet_count": count,
                    "percent_of_cluster": float(count / total * 100) if total else 0.0,
                })
        for method in table.columns:
            total = int(table[method].sum())
            for cluster_id, count in table[method].items():
                column_rows.append({
                    "experiment": experiment,
                    "cluster_id": int(cluster_id),
                    "discoverymethod": str(method),
                    "planet_count": int(count),
                    "percent_of_discovery_method": float(count / total * 100) if total else 0.0,
                })

        statistic, pvalue, dof, expected = chi2_contingency(table.to_numpy(dtype=int), correction=False)
        n = int(table.to_numpy().sum())
        dimensions = min(table.shape[0] - 1, table.shape[1] - 1)
        cramers_v = float(np.sqrt(statistic / (n * dimensions))) if dimensions > 0 and n > 0 else 0.0
        expected_lt5 = int((expected < 5).sum())
        expected_lt1 = int((expected < 1).sum())
        cell_count = int(expected.size)
        assumption_met = expected_lt1 == 0 and expected_lt5 / cell_count <= 0.20
        tests[experiment] = {
            "sample_size": n,
            "cluster_count": int(table.shape[0]),
            "discovery_method_categories": int(table.shape[1]),
            "observed_contingency_table": {str(k): {str(m): int(v) for m, v in row.items()} for k, row in table.iterrows()},
            "chi_square_statistic": float(statistic),
            "degrees_of_freedom": int(dof),
            "p_value": float(pvalue),
            "p_value_underflowed_float64": bool(pvalue == 0.0),
            "p_value_display": "<5e-324 (float64 underflow)" if pvalue == 0.0 else f"{pvalue:.6g}",
            "cramers_v": cramers_v,
            "expected_cell_count_minimum": float(expected.min()),
            "expected_cell_count": cell_count,
            "expected_cells_below_5": expected_lt5,
            "expected_cells_below_5_percent": float(expected_lt5 / cell_count * 100),
            "expected_cells_below_1": expected_lt1,
            "common_expected_count_heuristic_met": bool(assumption_met),
            "interpretation_note": (
                "Pearson chi-square asymptotic assumptions are not met under the common heuristic; "
                "do not overinterpret the p-value. Rare discovery categories were retained, not pooled."
                if not assumption_met else
                "The common expected-count heuristic is met; this remains an association test, not a causal test."
            ),
        }
    tests["overall_discovery_method_distribution_primary_cohort"] = {
        experiment: {str(k): int(v) for k, v in counts.items()}
        for experiment, counts in primary_counts_by_experiment.items()
    }
    tests["caveat"] = (
        "Discovery techniques have different detection sensitivities and survey selection effects. "
        "The confirmed-planet catalogue is not an unbiased sample of all planetary systems. "
        "An association does not show that discovery method causes physical properties or cluster membership."
    )
    return pd.DataFrame(counts_rows), pd.DataFrame(row_rows), pd.DataFrame(column_rows), tests


def compare_temperature_assignments(
    source: pd.DataFrame,
    assignments_by_experiment: dict[str, pd.DataFrame],
    identifiers: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Compare same-K assignments with labels aligned by maximum membership overlap."""
    with_temp = assignments_by_experiment["with_temp"].copy()
    without_temp = assignments_by_experiment["without_temp"].copy()
    if with_temp["pl_name"].astype(str).tolist() != without_temp["pl_name"].astype(str).tolist():
        raise ValueError("Temperature feature comparison requires matching ordered identifiers.")
    if with_temp["pl_name"].astype(str).tolist() != identifiers:
        raise ValueError("Temperature feature comparison is not using the primary cohort order.")
    left_labels = with_temp["cluster_id"].to_numpy(dtype=int)
    right_labels = without_temp["cluster_id"].to_numpy(dtype=int)
    table = pd.crosstab(left_labels, right_labels).reindex(index=range(4), columns=range(4), fill_value=0)
    left_ind, right_ind = linear_sum_assignment(-table.to_numpy(dtype=int))
    matched = {int(left): int(right) for left, right in zip(left_ind, right_ind, strict=True)}
    inverse = {right: left for left, right in matched.items()}
    aligned_right = np.array([inverse[int(label)] for label in right_labels], dtype=int)
    changed = left_labels != aligned_right
    membership = pd.DataFrame({
        "pl_name": identifiers,
        "cluster_with_temp": left_labels,
        "cluster_without_temp": right_labels,
        "matched_without_temp_cluster": aligned_right,
        "membership_changed_after_overlap_matching": changed,
    })
    left_profiles = cluster_distribution_validation(source, {"with_temp": with_temp}, identifiers)
    right_profiles = cluster_distribution_validation(source, {"without_temp": without_temp}, identifiers)
    left_source = _ordered_join(source, with_temp, identifiers)
    right_source = _ordered_join(source, without_temp, identifiers)
    left_source["discoverymethod"] = left_source["discoverymethod"].fillna("Unreported").astype(str)
    right_source["discoverymethod"] = right_source["discoverymethod"].fillna("Unreported").astype(str)
    all_methods = sorted(set(left_source["discoverymethod"]) | set(right_source["discoverymethod"]))
    profile_rows: list[dict[str, Any]] = []
    for left in range(4):
        for right in range(4):
            n_left = int((left_labels == left).sum())
            n_right = int((right_labels == right).sum())
            shared = int(table.loc[left, right])
            row: dict[str, Any] = {
                "cluster_with_temp": left,
                "cluster_without_temp": right,
                "is_one_to_one_profile_match": matched[left] == right,
                "with_temp_planet_count": n_left,
                "without_temp_planet_count": n_right,
                "shared_planet_count": shared,
                "jaccard_membership_overlap": float(shared / (n_left + n_right - shared)),
                "with_temp_members_recovered_percent": float(shared / n_left * 100),
                "without_temp_members_recovered_percent": float(shared / n_right * 100),
            }
            methods_a = left_source.loc[left_source["cluster_id"].astype(int) == left, "discoverymethod"].value_counts()
            methods_b = right_source.loc[right_source["cluster_id"].astype(int) == right, "discoverymethod"].value_counts()
            proportions_a = np.array([methods_a.get(method, 0) / n_left for method in all_methods], dtype=float)
            proportions_b = np.array([methods_b.get(method, 0) / n_right for method in all_methods], dtype=float)
            row["discovery_method_composition_total_variation_distance"] = float(
                np.abs(proportions_a - proportions_b).sum() / 2
            )
            row["dominant_discovery_method_with_temp"] = str(methods_a.idxmax())
            row["dominant_discovery_method_with_temp_percent"] = float(methods_a.max() / n_left * 100)
            row["dominant_discovery_method_without_temp"] = str(methods_b.idxmax())
            row["dominant_discovery_method_without_temp_percent"] = float(methods_b.max() / n_right * 100)
            for feature in PHYSICAL_FEATURES:
                a = left_profiles.loc[(left_profiles.cluster_id == left) & (left_profiles.feature == feature), "median"].iloc[0]
                b = right_profiles.loc[(right_profiles.cluster_id == right) & (right_profiles.feature == feature), "median"].iloc[0]
                row[f"{feature}_median_with_temp"] = float(a)
                row[f"{feature}_median_without_temp"] = float(b)
                row[f"{feature}_median_difference_without_minus_with"] = float(b - a)
            profile_rows.append(row)
    ari = float(adjusted_rand_score(left_labels, right_labels))
    matched_profile_rows = [row for row in profile_rows if row["is_one_to_one_profile_match"]]
    composition_distances = [row["discovery_method_composition_total_variation_distance"] for row in matched_profile_rows]
    summary = {
        "adjusted_rand_index": ari,
        "matched_clusters_by_maximum_membership_overlap": {str(k): int(v) for k, v in matched.items()},
        "membership_overlap_matrix_with_temp_rows_without_temp_columns": {
            str(int(left)): {str(int(right)): int(table.loc[left, right]) for right in range(4)}
            for left in range(4)
        },
        "matched_planet_count": int((~changed).sum()),
        "changed_planet_count": int(changed.sum()),
        "changed_planet_percent": float(changed.mean() * 100),
        "matched_cluster_discovery_method_composition_total_variation_mean": float(np.mean(composition_distances)),
        "matched_cluster_discovery_method_composition_total_variation_maximum": float(np.max(composition_distances)),
        "interpretation": "Partition sensitivity to temperature inclusion, not a causal effect.",
    }
    return pd.DataFrame(profile_rows), membership.loc[membership["membership_changed_after_overlap_matching"]].reset_index(drop=True), summary


def k_selection_comparison(
    metrics: pd.DataFrame,
    stability: pd.DataFrame,
    separation: pd.DataFrame,
    assignments_by_k: dict[int, pd.DataFrame],
    profiles: pd.DataFrame,
) -> pd.DataFrame:
    """Summarize the four-feature K=2,3,4,5 solutions without selecting K."""
    primary = metrics.loc[(metrics["experiment"] == "with_temp") & metrics["k"].isin([2, 3, 4, 5])].copy()
    stability_rows: list[dict[str, Any]] = []
    for k, group in stability.loc[stability.experiment == "with_temp"].groupby("k"):
        independent = group.loc[~group["is_primary_seed"].astype(bool), "ari_vs_seed42"]
        stability_rows.append({
            "k": int(k),
            "stability_ari_mean_excluding_seed42_self": float(independent.mean()),
            "stability_ari_sample_sd": float(independent.std(ddof=1)),
        })
    primary = primary.merge(pd.DataFrame(stability_rows), on="k", validate="one_to_one")
    separation_rows: list[dict[str, Any]] = []
    for k, group in separation.loc[separation.experiment == "with_temp"].groupby("k"):
        centroid = group.loc[group.diagnostic == "standardized_centroid_distance", "distance_or_overlap"]
        overlap = group.loc[group.diagnostic == "binned_univariate_overlap_coefficient", "distance_or_overlap"]
        separation_rows.append({
            "k": int(k),
            "centroid_distance_min": float(centroid.min()),
            "centroid_distance_median": float(centroid.median()),
            "centroid_distance_max": float(centroid.max()),
            "feature_overlap_median": float(overlap.median()),
            "feature_overlap_max": float(overlap.max()),
        })
    primary = primary.merge(pd.DataFrame(separation_rows), on="k", validate="one_to_one")

    profile_summaries: dict[int, str] = {}
    for k in (2, 3, 4, 5):
        subset = profiles.loc[(profiles.experiment == "with_temp") & (profiles.k == k)]
        summary = []
        for row in subset.sort_values("cluster_id").to_dict(orient="records"):
            summary.append({
                "cluster_id": int(row["cluster_id"]),
                "planet_count": int(row["planet_count"]),
                "planet_percent": round(float(row["planet_percent"]), 6),
                "median_pl_rade_earth_radii": float(row["pl_rade_median"]),
                "median_pl_orbper_days": float(row["pl_orbper_median"]),
                "median_pl_eqt_K": float(row["pl_eqt_median"]),
                "median_pl_orbeccen": float(row["pl_orbeccen_median"]),
            })
        profile_summaries[k] = json.dumps(summary, separators=(",", ":"))

    transition_summaries: dict[int, str] = {2: "No preceding K in this comparison."}
    for k in (3, 4, 5):
        previous = assignments_by_k[k - 1].set_index("pl_name")["cluster_id"].astype(int)
        current = assignments_by_k[k].set_index("pl_name")["cluster_id"].astype(int)
        if previous.index.tolist() != current.index.tolist():
            raise ValueError(f"K={k-1} and K={k} assignments must share ordered planet IDs.")
        transition = pd.crosstab(previous, current).reindex(
            index=sorted(previous.unique()), columns=sorted(current.unique()), fill_value=0
        )
        rows = []
        for cluster in transition.columns:
            dominant_parent = int(transition[cluster].idxmax())
            shared = int(transition.loc[dominant_parent, cluster])
            cluster_size = int(transition[cluster].sum())
            rows.append({
                "new_cluster_id": int(cluster),
                "dominant_previous_cluster": dominant_parent,
                "shared_planet_count": shared,
                "percent_of_new_cluster_from_parent": round(shared / cluster_size * 100, 6),
            })
        transition_summaries[k] = json.dumps(rows, separators=(",", ":"))
    primary["profile_medians_by_cluster_original_units"] = primary["k"].map(profile_summaries)
    primary["transition_from_previous_k"] = primary["k"].map(transition_summaries)
    primary["cluster_size_percentages"] = primary["cluster_sizes"].map(
        lambda raw: _size_percentages(raw, int(primary["observations"].iloc[0]))
    )
    primary["assessment_note"] = primary["k"].astype(int).map({
        2: "Two broad groups; highest four-feature silhouette among K=2–5.",
        3: "Adds one group; silhouette remains below K=2.",
        4: "Four-profile exploratory partition; silhouette is lower than K=2 and K=3.",
        5: "Slight silhouette increase over K=4; review whether the extra partition adds a useful distinction.",
    })
    keep = [
        "k", "observations", "silhouette_score", "inertia", "cluster_sizes", "cluster_size_percentages",
        "cluster_size_min", "cluster_size_max", "n_iter", "reached_max_iter",
        "centroid_distance_min", "centroid_distance_median", "centroid_distance_max",
        "feature_overlap_median", "feature_overlap_max",
        "stability_ari_mean_excluding_seed42_self", "stability_ari_sample_sd", "assessment_note",
        "profile_medians_by_cluster_original_units", "transition_from_previous_k",
    ]
    return primary.loc[:, keep].sort_values("k").reset_index(drop=True)


def _size_percentages(raw: Any, n: int) -> str:
    import json

    counts = json.loads(raw) if isinstance(raw, str) else raw
    return json.dumps({str(k): round(int(v) / n * 100, 6) for k, v in counts.items()}, separators=(",", ":"))


def distribution_svg(
    values_by_cluster: dict[int, np.ndarray],
    feature: str,
    experiment: str,
    source_caption: str,
    output_path: str,
) -> None:
    """Write a deterministic, dependency-free SVG relative-frequency histogram."""
    import math
    from pathlib import Path

    width, height = 1000, 700
    left, top, plot_width, plot_height = 105, 142, 820, 405
    palette = ["#2368a2", "#c45a18", "#39804a", "#8b5aa5"]
    all_values = np.concatenate([np.asarray(values, dtype=float) for values in values_by_cluster.values()])
    if not np.isfinite(all_values).all():
        raise ValueError(f"Cannot plot non-finite values in {feature}.")
    edges, logarithmic = _histogram_edges(all_values, bins=40)
    if logarithmic:
        transform = np.log10
        x_values = np.log10(edges)
    else:
        transform = lambda x: x
        x_values = edges
    span = float(x_values[-1] - x_values[0]) or 1.0
    fractions = {cluster: np.histogram(transform(vals), bins=x_values)[0] / len(vals)
                 for cluster, vals in values_by_cluster.items()}
    ymax = max(float(np.max(frac)) for frac in fractions.values())
    ymax = max(0.05, math.ceil(ymax / 0.05) * 0.05)
    title_names = {
        "pl_rade": ("Planet radius", "Earth radii"),
        "pl_orbper": ("Orbital period", "days"),
        "pl_eqt": ("Equilibrium temperature", "K"),
        "pl_orbeccen": ("Orbital eccentricity", "dimensionless"),
    }
    feature_title, units = title_names[feature]
    exp_title = "4 features including temperature" if experiment == "with_temp" else "3 features excluding temperature"
    title = f"{feature_title} by cluster — {exp_title}, K=4"
    xlabel = f"{feature_title} ({units})" + (" — logarithmic axis" if logarithmic else "")
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#202124}.tick{font-size:13px}.small{font-size:12px}.title{font-size:22px;font-weight:600}.axis{stroke:#333;stroke-width:1}.grid{stroke:#dedede;stroke-width:1}</style>',
        f'<text class="title" x="{left}" y="36">{escape(title)}</text>',
    ]
    # Legend, with cluster sizes, follows the source assignment labels exactly.
    for index, (cluster, vals) in enumerate(values_by_cluster.items()):
        x = left + (index % 2) * 255
        y = 72 + (index // 2) * 24
        pieces.append(f'<line x1="{x}" y1="{y-4}" x2="{x+28}" y2="{y-4}" stroke="{palette[index]}" stroke-width="3"/>')
        pieces.append(f'<text class="small" x="{x+36}" y="{y}">Cluster {cluster} (n={len(vals):,})</text>')
    for tick_i in range(6):
        fraction = tick_i / 5
        y = top + plot_height * (1 - fraction)
        pieces.append(f'<line class="grid" x1="{left}" y1="{y:.2f}" x2="{left+plot_width}" y2="{y:.2f}"/>')
        pieces.append(f'<text class="tick" text-anchor="end" x="{left-12}" y="{y+4:.2f}">{fraction*ymax:.2f}</text>')
    xmin, xmax = float(x_values[0]), float(x_values[-1])
    if logarithmic:
        physical_min, physical_max = float(all_values.min()), float(all_values.max())
        tick_values = [10.0 ** power for power in range(math.floor(math.log10(physical_min)), math.ceil(math.log10(physical_max)) + 1)]
        tick_values = [tick for tick in tick_values if physical_min <= tick <= physical_max]
        if len(tick_values) < 3:
            tick_values = np.geomspace(physical_min, physical_max, 4).tolist()
        for tick in tick_values:
            transformed_tick = math.log10(tick)
            x = left + plot_width * (transformed_tick - xmin) / span
            label = f"{tick:g}"
            pieces.append(f'<line class="axis" x1="{x:.2f}" y1="{top+plot_height}" x2="{x:.2f}" y2="{top+plot_height+5}"/>')
            pieces.append(f'<text class="tick" text-anchor="middle" x="{x:.2f}" y="{top+plot_height+23}">{label}</text>')
    else:
        tick_values = np.linspace(float(all_values.min()), float(all_values.max()), 6)
        for tick in tick_values:
            x = left + plot_width * (tick - xmin) / span
            pieces.append(f'<line class="axis" x1="{x:.2f}" y1="{top+plot_height}" x2="{x:.2f}" y2="{top+plot_height+5}"/>')
            pieces.append(f'<text class="tick" text-anchor="middle" x="{x:.2f}" y="{top+plot_height+23}">{tick:.3g}</text>')
    pieces.extend([
        f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_height}"/>',
        f'<line class="axis" x1="{left}" y1="{top+plot_height}" x2="{left+plot_width}" y2="{top+plot_height}"/>',
        f'<text class="tick" text-anchor="middle" x="{left+plot_width/2}" y="{top+plot_height+54}">{escape(xlabel)}</text>',
        f'<text class="tick" text-anchor="middle" transform="translate(30 {top+plot_height/2}) rotate(-90)">Fraction of cluster per histogram bin</text>',
    ])
    for index, (cluster, frac) in enumerate(fractions.items()):
        points: list[tuple[float, float]] = []
        centers = (x_values[:-1] + x_values[1:]) / 2
        for x_center, fraction in zip(centers, frac, strict=True):
            x = left + plot_width * (float(x_center) - xmin) / span
            y = top + plot_height * (1 - float(fraction) / ymax)
            points.append((x, y))
        if points:
            path = f"M {points[0][0]:.2f} {top+plot_height:.2f}"
            for (x0, y0), (x1, y1) in zip(points[:-1], points[1:], strict=True):
                path += f" L {x0:.2f} {y0:.2f} L {x1:.2f} {y0:.2f}"
            path += f" L {points[-1][0]:.2f} {points[-1][1]:.2f} L {points[-1][0]:.2f} {top+plot_height:.2f}"
            pieces.append(f'<path d="{path}" fill="none" stroke="{palette[index]}" stroke-width="2.4"/>')
    pieces.append(f'<text class="small" x="{left}" y="{height-38}">Source: {escape(source_caption)} · shared complete-case cohort (n=5,273)</text>')
    pieces.append('<text class="small" x="105" y="680">Histogram fractions use original physical measurements; no values were removed or transformed in saved data.</text>')
    pieces.append('</svg>')
    Path(output_path).write_text("\n".join(pieces) + "\n", encoding="utf-8", newline="\n")

