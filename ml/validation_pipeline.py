"""Run reproducible validation of the saved ExoAtlas candidate clusters."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy
import sklearn

from .cluster_validation import (
    EXPERIMENTS,
    PHYSICAL_FEATURES,
    cluster_distribution_validation,
    compare_temperature_assignments,
    discovery_method_validation,
    distribution_svg,
    k_selection_comparison,
    separation_diagnostics,
    silhouette_validation,
)
from .clustering import feature_columns, validate_feature_frame
from .clustering_pipeline import (
    EXPERIMENT_OUTPUT_DIR,
    MASTER_RELATIVE_PATH,
    ROOT,
    SCALER_WITH_TEMP_RELATIVE_PATH,
    SCALER_WITHOUT_TEMP_RELATIVE_PATH,
    SOURCE_RELATIVE_PATH,
    WITH_TEMP_RELATIVE_PATH,
    WITHOUT_TEMP_RELATIVE_PATH,
)
from .data_audit import PRE_MOVE_SHA256


OUTPUT_DIR = Path("data/cluster_validation")
COHORT_SIZE = 5_273
REQUIRED_REPORTS = (
    "cluster_distribution_validation.csv",
    "cluster_silhouette_validation.csv",
    "cluster_separation.csv",
    "discovery_method_counts.csv",
    "discovery_method_row_percentages.csv",
    "discovery_method_column_percentages.csv",
    "discovery_method_tests.json",
    "temperature_feature_comparison.csv",
    "k_selection_comparison.csv",
    "temperature_feature_membership_changes.csv",
    "cluster_validation_report.md",
    "cluster_validation_report.json",
)
PRESERVED_INPUTS = (
    SOURCE_RELATIVE_PATH,
    MASTER_RELATIVE_PATH,
    WITH_TEMP_RELATIVE_PATH,
    WITHOUT_TEMP_RELATIVE_PATH,
    SCALER_WITH_TEMP_RELATIVE_PATH,
    SCALER_WITHOUT_TEMP_RELATIVE_PATH,
    Path("data/metadata/preprocessing_report.json"),
    Path("data/metadata/preprocessing_report.md"),
    Path("data/cluster_experiments/cluster_assignments_with_temp_k4.csv"),
    Path("data/cluster_experiments/cluster_assignments_without_temp_k4.csv"),
    Path("data/cluster_experiments/cluster_assignments_with_temp_k2.csv"),
    Path("data/cluster_experiments/cluster_assignments_with_temp_k3.csv"),
    Path("data/cluster_experiments/cluster_assignments_with_temp_k5.csv"),
    Path("data/cluster_experiments/cluster_assignments_without_temp_k2.csv"),
    Path("data/cluster_experiments/cluster_assignments_without_temp_k3.csv"),
    Path("data/cluster_experiments/cluster_assignments_without_temp_k5.csv"),
    Path("data/cluster_experiments/experiment_metrics.csv"),
    Path("data/cluster_experiments/stability_metrics.csv"),
    Path("data/cluster_experiments/cluster_profiles_with_temp.csv"),
    Path("data/cluster_experiments/cluster_profiles_without_temp.csv"),
    Path("data/cluster_experiments/feature_diagnostics.json"),
)


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest for an input or generated artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _hash_paths(root: Path, paths: tuple[Path, ...] | list[Path]) -> dict[str, str]:
    return {path.as_posix(): sha256_file(root / path) for path in paths}


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _json_ready(value: Any) -> Any:
    """Convert pandas/NumPy scalars and missing values to strict JSON values."""
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_json_ready(v) for v in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8", float_format="%.17g", lineterminator="\n")


def _read_inputs(root: Path) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict[str, pd.DataFrame], dict[str, Any]]:
    source_path = root / SOURCE_RELATIVE_PATH
    source = pd.read_csv(source_path, comment="#", low_memory=False)
    if len(source) != 6_451 or source.shape[1] != 84:
        raise ValueError(f"Expected the audited 6,451 x 84 source table; found {source.shape}.")
    source_hash = sha256_file(source_path)
    if source_hash != PRE_MOVE_SHA256:
        raise ValueError("Raw NASA source checksum does not match the approved snapshot.")

    matrices: dict[str, pd.DataFrame] = {}
    assignments: dict[str, pd.DataFrame] = {}
    for experiment in EXPERIMENTS:
        matrix_path = root / (WITH_TEMP_RELATIVE_PATH if experiment == "with_temp" else WITHOUT_TEMP_RELATIVE_PATH)
        assignment_path = root / EXPERIMENT_OUTPUT_DIR / f"cluster_assignments_{experiment}_k4.csv"
        matrix = pd.read_csv(matrix_path, low_memory=False)
        assignment = pd.read_csv(assignment_path, dtype={"pl_name": "string"})
        validate_feature_frame(matrix, experiment)
        if list(assignment.columns) != ["pl_name", "cluster_id"]:
            raise ValueError(f"Unexpected assignment schema in {assignment_path}.")
        if assignment["pl_name"].duplicated().any() or assignment["pl_name"].isna().any():
            raise ValueError(f"Duplicate or missing planet ID in {assignment_path}.")
        if len(assignment) != COHORT_SIZE or set(assignment["cluster_id"].astype(int).unique()) != {0, 1, 2, 3}:
            raise ValueError(f"Expected one K=4 assignment per primary-cohort planet in {assignment_path}.")
        if assignment["pl_name"].astype(str).tolist() != matrix["pl_name"].astype(str).tolist():
            raise ValueError(f"Assignment and feature matrix identifiers/order differ for {experiment}.")
        matrices[experiment] = matrix
        assignments[experiment] = assignment
    if matrices["with_temp"]["pl_name"].astype(str).tolist() != matrices["without_temp"]["pl_name"].astype(str).tolist():
        raise ValueError("Candidate feature matrices do not contain the same ordered planet cohort.")
    identifiers = matrices["with_temp"]["pl_name"].astype(str).tolist()
    if len(identifiers) != COHORT_SIZE or len(set(identifiers)) != COHORT_SIZE:
        raise ValueError("The shared primary cohort must have 5,273 unique planet identifiers.")
    return source, matrices, assignments, {
        "records": len(source),
        "columns": source.shape[1],
        "source_sha256": source_hash,
        "primary_cohort_records": len(identifiers),
        "primary_cohort_unique_planet_ids": len(set(identifiers)),
        "ordered_ids_match_between_feature_configurations": True,
        "feature_columns": {experiment: list(feature_columns(experiment)) for experiment in EXPERIMENTS},
    }


def _format(value: Any, digits: int = 4) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):,.{digits}f}"


def _cluster_profile_markdown(distributions: pd.DataFrame, experiment: str) -> str:
    subset = distributions.loc[distributions.experiment == experiment]
    rows = []
    for cluster_id in sorted(subset.cluster_id.unique()):
        group = subset.loc[subset.cluster_id == cluster_id].set_index("feature")
        count = int(group.iloc[0].planet_count)
        percent = float(group.iloc[0].planet_percent)
        rows.append(
            f"| {cluster_id} | {count:,} ({percent:.2f}%) | "
            f"{group.loc['pl_rade','median']:,.3g} [{group.loc['pl_rade','minimum']:,.3g}, {group.loc['pl_rade','maximum']:,.3g}] | "
            f"{group.loc['pl_orbper','median']:,.3g} [{group.loc['pl_orbper','minimum']:,.3g}, {group.loc['pl_orbper','maximum']:,.3g}] | "
            f"{group.loc['pl_eqt','median']:,.3g} [{group.loc['pl_eqt','minimum']:,.3g}, {group.loc['pl_eqt','maximum']:,.3g}] | "
            f"{group.loc['pl_orbeccen','median']:,.3g} [{group.loc['pl_orbeccen','minimum']:,.3g}, {group.loc['pl_orbeccen','maximum']:,.3g}] |"
        )
    return "\n".join([
        "| Cluster ID | Planets | Radius median [min, max] (R⊕) | Period median [min, max] (days) | Temperature median [min, max] (K) | Eccentricity median [min, max] |",
        "|---:|---:|---:|---:|---:|---:|",
        *rows,
    ])


def _markdown_report(report: dict[str, Any], distributions: pd.DataFrame,
                     silhouettes: pd.DataFrame, separation: pd.DataFrame,
                     discovery_tests: dict[str, Any], k_comparison: pd.DataFrame,
                     ) -> str:
    dataset = report["dataset"]
    temp = report["temperature_comparison"]
    lines = [
        "# ExoAtlas — Cluster Validation Report",
        "",
        "## Scope and inputs",
        "",
        f"This validation examined the NASA Exoplanet Archive PSCompPars snapshot dated {dataset['source_snapshot_date']}. "
        f"The source contains {dataset['records']:,} records and {dataset['columns']} columns. "
        f"Both saved K=4 candidates use the same {dataset['primary_cohort_records']:,} unique planets, joined to the source by `pl_name`.",
        "",
        "Candidate A uses the existing four-feature standardized matrix (log10 radius, log10 orbital period, raw equilibrium temperature, raw eccentricity). "
        "Candidate B uses the existing three-feature matrix (log10 radius, log10 orbital period, raw eccentricity). "
        "This validation reads the saved seed-42 assignments and feature matrices; it does not refit K-means, alter preprocessing, or modify observations.",
        "",
        "## K=4 physical profiles",
        "",
        "All values below are original NASA physical measurements. Each range is the observed minimum to maximum; full mean, sample standard deviation, quartiles and IQR are in `cluster_distribution_validation.csv`. A median difference by itself does not establish a distinct planet population.",
        "",
        "### Candidate A — four features including temperature",
        "",
        _cluster_profile_markdown(distributions, "with_temp"),
        "",
        "### Candidate B — three features excluding temperature",
        "",
        _cluster_profile_markdown(distributions, "without_temp"),
        "",
        "For radius, orbital period, and temperature, the supplied distribution plots use logarithmic horizontal axes because their positive values span broad ranges. Histogram fractions are computed from original measurements; eccentricity is plotted on a linear axis and zeros are retained.",
        "",
        "## K=4 separation and overlap",
        "",
        f"The full-cohort Euclidean silhouette is {_format(report['overall_silhouette']['with_temp'], 4)} for Candidate A and {_format(report['overall_silhouette']['without_temp'], 4)} for Candidate B. "
        "Silhouette is a geometric diagnostic in the standardized input space, not scientific validation by itself.",
        "",
        "Per-cluster mean silhouettes and negative-silhouette counts:",
        "",
        "| Candidate | Cluster | Mean silhouette | Negative observations | Negative (%) |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in silhouettes.loc[silhouettes.cluster_id != "ALL"].to_dict(orient="records"):
        label = "A — with temperature" if row["experiment"] == "with_temp" else "B — without temperature"
        lines.append(f"| {label} | {row['cluster_id']} | {row['mean_silhouette']:.4f} | {row['negative_silhouette_count']:,} | {row['negative_silhouette_percent']:.2f}% |")
    for experiment in EXPERIMENTS:
        worst = silhouettes.loc[
            (silhouettes.experiment == experiment) & (silhouettes.cluster_id != "ALL")
        ].sort_values("mean_silhouette").iloc[0]
        label = "Candidate A" if experiment == "with_temp" else "Candidate B"
        lines.append(
            f"{label}: cluster {int(worst.cluster_id)} has the lowest cluster-average silhouette "
            f"({worst.mean_silhouette:.4f}) and {int(worst.negative_silhouette_count):,} negative-silhouette "
            f"members ({worst.negative_silhouette_percent:.2f}% of that cluster)."
        )
    lines.extend(["", "Pairwise centroid distances use the exact standardized K-means input space. Larger distances indicate more separated centroids, but do not imply non-overlapping observations. Binned univariate overlap coefficients range from 0 (no shared bin mass) to 1 (identical binned distributions); binning is shared across clusters within each feature. These one-dimensional coefficients complement, and do not replace, multivariate diagnostics.", ""])
    for experiment in EXPERIMENTS:
        name = "Candidate A" if experiment == "with_temp" else "Candidate B"
        subset = separation.loc[(separation.experiment == experiment) & (separation.k == 4) & (separation.diagnostic == "standardized_centroid_distance")].sort_values("distance_or_overlap")
        lines.append(f"**{name} centroid distances (ascending):** " + "; ".join(
            f"C{int(r.cluster_a)}–C{int(r.cluster_b)} {r.distance_or_overlap:.3f}" for r in subset.itertuples()
        ) + ".")
        overlaps = separation.loc[(separation.experiment == experiment) & (separation.k == 4) & (separation.diagnostic == "binned_univariate_overlap_coefficient")]
        strongest = overlaps.sort_values("distance_or_overlap", ascending=False).head(4)
        lines.append(f"Highest binned 1-D overlaps in {name}: " + "; ".join(
            f"C{int(r.cluster_a)}–C{int(r.cluster_b)} {r.feature}={r.distance_or_overlap:.2f}" for r in strongest.itertuples()
        ) + ".")
        lines.append("")
    lines.extend([
        "The lowest cluster-average silhouette identifies the group with the weakest average geometric assignment; its negative-silhouette share identifies observations closer, on average, to another cluster. Full per-planet values are in `cluster_silhouette_validation.csv`. No observations were removed based on these diagnostics.",
        "",
        "## Discovery-method composition",
        "",
        "Overall method counts in the full source and the 5,273-planet cohort are shown below. Candidate A and B use the same overall cohort methods, but cluster composition can differ.",
        "",
        "| Discovery method | Full source n (%) | Primary cohort n (%) |",
        "|---|---:|---:|",
    ])
    source_methods = discovery_tests["overall_discovery_method_distribution_full_source"]
    cohort_methods = discovery_tests["overall_discovery_method_distribution_primary_cohort"]["with_temp"]
    for method in sorted(set(source_methods) | set(cohort_methods), key=lambda key: (-source_methods.get(key, 0), key)):
        full_count = int(source_methods.get(method, 0))
        cohort_count = int(cohort_methods.get(method, 0))
        lines.append(
            f"| {method} | {full_count:,} ({full_count / dataset['records'] * 100:.2f}%) | "
            f"{cohort_count:,} ({cohort_count / dataset['primary_cohort_records'] * 100:.2f}%) |"
        )
    lines.extend([
        "",
        "Cluster-by-method counts and within-cluster / within-method percentages are in the three discovery-method CSVs. Dominant method composition by cluster:",
        "",
        "| Candidate | Cluster | Most common discovery method | Share within cluster |",
        "|---|---:|---|---:|",
    ])
    for experiment in EXPERIMENTS:
        table = discovery_tests[experiment]["observed_contingency_table"]
        label = "A — with temperature" if experiment == "with_temp" else "B — without temperature"
        for cluster, method_counts in table.items():
            method, count = max(method_counts.items(), key=lambda item: item[1])
            total = sum(method_counts.values())
            lines.append(f"| {label} | {cluster} | {method} | {int(count) / total * 100:.2f}% |")
    lines.extend([
        "",
        "| Candidate | n | χ² | df | p-value | Cramér’s V | Expected cells <5 | Expected cells <1 | Heuristic met? |",
        "|---|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ])
    for experiment in EXPERIMENTS:
        result = discovery_tests[experiment]
        name = "A — with temperature" if experiment == "with_temp" else "B — without temperature"
        lines.append(
            f"| {name} | {result['sample_size']:,} | {result['chi_square_statistic']:.2f} | {result['degrees_of_freedom']} | "
            f"{result['p_value_display']} | {result['cramers_v']:.3f} | {result['expected_cells_below_5']}/{result['expected_cell_count']} "
            f"({result['expected_cells_below_5_percent']:.1f}%) | {result['expected_cells_below_1']} | {'Yes' if result['common_expected_count_heuristic_met'] else 'No'} |"
        )
    lines.extend([
        "",
        "Discovery methods have different detection sensitivities and survey selection effects. The confirmed-planet catalogue is not an unbiased sample of planetary systems. These tests describe association only; they do not imply that discovery method causes a planet’s properties or cluster membership.",
        "",
        "The Pearson chi-square asymptotic p-value should not be overinterpreted when expected-count assumptions fail. Rare method categories were retained rather than pooled; use the reported Cramér’s V and counts descriptively and consider an approved category-handling or exact/resampling analysis if inferential claims are needed.",
        "",
        "## Temperature-inclusion comparison",
        "",
        f"The adjusted Rand index between the K=4 partitions is **{temp['adjusted_rand_index']:.4f}**. After one-to-one cluster alignment by maximum membership overlap, {temp['changed_planet_count']:,} planets ({temp['changed_planet_percent']:.2f}%) change matched cluster membership; the changed planet identifiers are in `temperature_feature_membership_changes.csv`.",
        "",
        "Cluster labels are aligned by the Hungarian assignment on shared membership, not by their numeric IDs. The comparison CSV contains the full 4×4 membership-overlap matrix as well as matched-pair Jaccard overlap and original-unit median differences.",
        "",
        "| With-temperature cluster | Without-temperature C0 | C1 | C2 | C3 |",
        "|---:|---:|---:|---:|---:|",
    ])
    overlap_matrix = temp["membership_overlap_matrix_with_temp_rows_without_temp_columns"]
    for cluster in range(4):
        row = overlap_matrix[str(cluster)]
        lines.append(f"| {cluster} | " + " | ".join(f"{int(row[str(other)]):,}" for other in range(4)) + " |")
    lines.extend([
        "",
        "The overlap pattern indicates more than a small boundary shift: Candidate A clusters 1 and 2 contribute 1,352 and 1,975 planets, respectively, to Candidate B cluster 0. Temperature inclusion separates those two groups in the four-feature partition, while the three-feature solution largely combines them. The matched A1↔B1 pair has only 5 shared planets, so that forced one-to-one match should not be read as a physical equivalence. This is a descriptive partition comparison, not evidence that temperature causes a planetary class.",
        f"Among the four one-to-one membership-matched cluster pairs, discovery-method composition has a mean total-variation distance of {temp['matched_cluster_discovery_method_composition_total_variation_mean']:.3f} (maximum {temp['matched_cluster_discovery_method_composition_total_variation_maximum']:.3f}); 0 means identical method proportions and 1 means disjoint compositions. This is descriptive and inherits the survey-selection limitations above.",
        "",
        "## Four-feature K choice: K=2–5",
        "",
        "| K | Silhouette | Inertia | Cluster sizes | Centroid distances (min–max) | Median 1-D overlap | Stability ARI mean ± SD | Iterations |",
        "|---:|---:|---:|---|---:|---:|---:|---:|",
    ])
    for row in k_comparison.to_dict(orient="records"):
        import json as _json
        sizes = _json.loads(row["cluster_sizes"])
        size_text = ", ".join(str(value) for value in sizes.values())
        lines.append(f"| {int(row['k'])} | {row['silhouette_score']:.4f} | {row['inertia']:.1f} | {size_text} | {row['centroid_distance_min']:.2f}–{row['centroid_distance_max']:.2f} | {row['feature_overlap_median']:.2f} | {row['stability_ari_mean_excluding_seed42_self']:.4f} ± {row['stability_ari_sample_sd']:.4f} | {int(row['n_iter'])} |")
    lines.extend([
        "",
        "For the four-feature experiment, K=2 has the highest silhouette among K=2–5. K=4 lowers silhouette substantially relative to K=2 and K=3, while K=5 improves slightly over K=4. Across K, all candidate partitions are stable across the tested initializations; stability does not distinguish K=4. The centroid-distance and binned-overlap summaries add geometric/profile evidence but are not directly equivalent to astronomical separation.",
        "",
        "Original-unit profiles suggest K=3 adds a hot, short-period, large-radius group to the broad K=2 split. K=4 further divides the smaller-radius population into a hotter, shorter-period group (median radius 1.54 R⊕, median period 4.29 days, median temperature 1,086 K) and a cooler/intermediate group (2.57 R⊕, 19.67 days, 579 K). At K=5, a 322-planet group has median eccentricity 0.512, compared with 0.129 for another large-radius, longer-period group; this is a plausible exploratory distinction, while the remaining profiles also shift. These are summaries of partitions, not claims of validated classes. Cluster membership transitions and physical medians by K are included in `k_selection_comparison.csv`.",
        "",
        "### Recommendation",
        "",
        "K=4 is defensible as an exploratory view, but the current evidence is not strong enough to freeze it as the primary scientific configuration. Its lower four-feature silhouette than K=2/K=3, the slight K=5 improvement, and the strong sensitivity to temperature leave the preferred granularity unresolved. Keep K=2 and K=3 as simpler references, retain K=5 as a refinement comparison, and request scientific review of the original-unit profiles and discovery-selection effects before promoting any K. This is a recommendation, not an automatic model-selection decision.",
        "",
        "## Integrity, plots, and limitations",
        "",
        f"The raw source and preprocessing inputs were byte-identical before and after validation: **{report['integrity']['preserved_inputs_unchanged']}**. Source SHA-256: `{dataset['source_sha256']}`. No values were deleted, imputed, or transformed in saved source/preprocessing data; no new clustering model or supervised model was trained.",
        "",
        "Full-source extreme-value context (extremes may not all belong to the primary cohort):",
        "",
        "| Feature | Units | Minimum planet (value) | Maximum planet (value) |",
        "|---|---|---|---|",
    ])
    for feature, result in report["source_feature_extremes"].items():
        lines.append(
            f"| {feature} | {result['units']} | `{result['minimum']['pl_name']}` ({result['minimum']['value']:,.6g}) | "
            f"`{result['maximum']['pl_name']}` ({result['maximum']['value']:,.6g}) |"
        )
    lines.extend([
        "",
        "Eight labelled SVG plots are saved under `data/cluster_validation/plots/`, with one original-unit feature distribution per feature and candidate. The JSON report records input and output hashes, statistical results, category-count diagnostics, and runtime versions.",
        "",
        "Limitations: K-means produces geometric partitions, not established astronomical classes; silhouette assesses geometry only; binned univariate overlap depends on the stated common bins; discovery-method association is subject to catalogue selection; and this milestone does not model dependence among planets around the same host star.",
        "",
    ])
    return "\n".join(lines)


def run_validation_pipeline(root: Path = ROOT) -> dict[str, Any]:
    """Generate validation tables, plots, integrity metadata and the final report."""
    root = Path(root).resolve()
    out = root / OUTPUT_DIR
    plot_dir = out / "plots"
    out.mkdir(parents=True, exist_ok=True)
    plot_dir.mkdir(parents=True, exist_ok=True)

    missing = [str(root / path) for path in PRESERVED_INPUTS if not (root / path).is_file()]
    if missing:
        raise FileNotFoundError("Required validation inputs are missing: " + ", ".join(missing))
    hashes_before = _hash_paths(root, PRESERVED_INPUTS)
    source, matrices, assignments, dataset = _read_inputs(root)
    identifiers = matrices["with_temp"]["pl_name"].astype(str).tolist()
    assignments_by_experiment_k: dict[str, dict[int, pd.DataFrame]] = {}
    for experiment in EXPERIMENTS:
        ks = (2, 3, 4, 5) if experiment == "with_temp" else (4,)
        assignments_by_experiment_k[experiment] = {}
        for k in ks:
            assignment_path = root / EXPERIMENT_OUTPUT_DIR / f"cluster_assignments_{experiment}_k{k}.csv"
            saved = assignments[experiment] if k == 4 else pd.read_csv(
                assignment_path, dtype={"pl_name": "string"}
            )
            if list(saved.columns) != ["pl_name", "cluster_id"]:
                raise ValueError(f"Unexpected assignment schema in {assignment_path}.")
            if saved["pl_name"].astype(str).tolist() != identifiers or saved["pl_name"].duplicated().any():
                raise ValueError(f"Saved {experiment} K={k} assignments do not match the ordered primary IDs.")
            if set(saved["cluster_id"].astype(int).unique()) != set(range(k)):
                raise ValueError(f"Saved {experiment} K={k} assignment labels are not 0..K-1.")
            assignments_by_experiment_k[experiment][k] = saved

    distributions = cluster_distribution_validation(source, assignments, identifiers)
    silhouette_rows, silhouette_summary = silhouette_validation(matrices, assignments)
    separation = separation_diagnostics(source, matrices, assignments_by_experiment_k, identifiers)
    discovery_counts, discovery_rows, discovery_columns, discovery_tests = discovery_method_validation(
        source, assignments, identifiers
    )
    temperature_profiles, changed_members, temperature_summary = compare_temperature_assignments(
        source, assignments, identifiers
    )
    existing_metrics = pd.read_csv(root / EXPERIMENT_OUTPUT_DIR / "experiment_metrics.csv")
    stability = pd.read_csv(root / EXPERIMENT_OUTPUT_DIR / "stability_metrics.csv")
    with_profiles = pd.read_csv(root / EXPERIMENT_OUTPUT_DIR / "cluster_profiles_with_temp.csv")
    k_compare = k_selection_comparison(
        existing_metrics, stability, separation, assignments_by_experiment_k["with_temp"], with_profiles
    )

    for frame, name in (
        (distributions, "cluster_distribution_validation.csv"),
        (silhouette_rows, "cluster_silhouette_validation.csv"),
        (separation, "cluster_separation.csv"),
        (discovery_counts, "discovery_method_counts.csv"),
        (discovery_rows, "discovery_method_row_percentages.csv"),
        (discovery_columns, "discovery_method_column_percentages.csv"),
        (temperature_profiles, "temperature_feature_comparison.csv"),
        (changed_members, "temperature_feature_membership_changes.csv"),
        (k_compare, "k_selection_comparison.csv"),
    ):
        _write_csv(frame, out / name)
    _json_write(out / "discovery_method_tests.json", discovery_tests)

    plot_paths: list[Path] = []
    for experiment in EXPERIMENTS:
        joined = assignments[experiment].merge(
            source[["pl_name", *PHYSICAL_FEATURES.keys()]],
            on="pl_name", how="left", validate="one_to_one",
        )
        for feature in PHYSICAL_FEATURES:
            by_cluster = {
                int(cluster): group[feature].to_numpy(dtype=float)
                for cluster, group in joined.groupby("cluster_id", sort=True)
            }
            plot_path = plot_dir / f"{experiment}_{feature}_by_cluster.svg"
            distribution_svg(
                by_cluster, feature, experiment,
                "NASA Exoplanet Archive PSCompPars, snapshot 2026-10-30",
                str(plot_path),
            )
            plot_paths.append(plot_path)

    hashes_after = _hash_paths(root, PRESERVED_INPUTS)
    if hashes_before != hashes_after:
        raise AssertionError("Source, preprocessing, clustering assignments, or prior results changed during validation.")
    if hashes_before[SOURCE_RELATIVE_PATH.as_posix()] != PRE_MOVE_SHA256:
        raise AssertionError("The raw source hash changed from the approved NASA snapshot.")

    overall_silhouette = {
        row["experiment"]: float(row["mean_silhouette"])
        for row in silhouette_summary.loc[silhouette_summary.cluster_id == "ALL"].to_dict(orient="records")
    }
    source_feature_extremes: dict[str, Any] = {}
    for feature in PHYSICAL_FEATURES:
        values = source.set_index("pl_name")[feature].dropna()
        low_name, high_name = str(values.idxmin()), str(values.idxmax())
        source_feature_extremes[feature] = {
            "units": PHYSICAL_FEATURES[feature],
            "minimum": {"pl_name": low_name, "value": float(values.min())},
            "maximum": {"pl_name": high_name, "value": float(values.max())},
            "scope": "full raw source; the extreme may be outside the shared four-feature cohort",
        }
    output_files = [out / name for name in REQUIRED_REPORTS if (out / name).exists()]
    output_files.extend(plot_paths)
    generated_hashes = _hash_paths(root, [path.relative_to(root) for path in output_files if path.name not in {
        "cluster_validation_report.json", "cluster_validation_report.md"
    }])
    report: dict[str, Any] = {
        "schema_version": 1,
        "dataset": {
            **dataset,
            "source_name": SOURCE_RELATIVE_PATH.name,
            "source_path": SOURCE_RELATIVE_PATH.as_posix(),
            "source_snapshot_date": "2026-10-30",
            "source_sha256": PRE_MOVE_SHA256,
        },
        "method": {
            "candidate_assignments": "Existing seed-42 K=4 labels; no model was fit in this milestone.",
            "silhouette_metric": "Euclidean silhouette_samples on each exact existing standardized K-means input matrix.",
            "cluster_matching": "Hungarian assignment maximizing planet membership overlap; numeric labels are not equated across models.",
            "overlap_diagnostic": "Pairwise binned one-dimensional overlap coefficient with common physical-value bins per feature.",
            "discovery_test": "Pearson chi-square without Yates correction, plus Cramer's V; all nonzero discovery-method categories retained.",
            "distribution_statistics": "Original NASA physical values; sample standard deviation (ddof=1), linear quantiles.",
        },
        "integrity": {
            "input_sha256_before": hashes_before,
            "input_sha256_after": hashes_after,
            "preserved_inputs_unchanged": hashes_before == hashes_after,
            "generated_output_sha256": generated_hashes,
        },
        "cluster_distribution": distributions.to_dict(orient="records"),
        "overall_silhouette": overall_silhouette,
        "silhouette_cluster_summary": silhouette_summary.to_dict(orient="records"),
        "silhouette_observation_count": int(len(silhouette_rows)),
        "cluster_separation": separation.to_dict(orient="records"),
        "discovery_method_tests": discovery_tests,
        "temperature_comparison": temperature_summary,
        "temperature_cluster_profile_comparison": temperature_profiles.to_dict(orient="records"),
        "changed_planet_identifier_count": int(len(changed_members)),
        "k_selection": k_compare.to_dict(orient="records"),
        "source_feature_extremes": source_feature_extremes,
        "recommendation": {
            "k4_justified_as_frozen_primary": False,
            "recommendation": "Retain K=4 as an exploratory candidate, but defer freezing it as the primary scientific configuration pending review of the K=2/3 simplicity advantage, K=5 refinement, feature overlap, temperature sensitivity, and catalogue selection effects.",
            "automatic_model_selection": False,
        },
        "limitations": [
            "K-means partitions are geometric groupings, not established astronomical classes.",
            "Silhouette is not a scientific validation metric by itself.",
            "One-dimensional overlap coefficients are approximate and depend on the shared binning scheme.",
            "Discovery methods have different sensitivities and survey selection effects; the confirmed catalogue is not an unbiased system sample.",
            "No causal inference is supported by discovery-method associations.",
            "Planet-level validation does not model dependence among planets around a shared host star.",
        ],
        "outputs": {
            "directory": OUTPUT_DIR.as_posix(),
            "plots": [path.relative_to(root).as_posix() for path in plot_paths],
            "csv_json_report_files": [path.relative_to(root).as_posix() for path in output_files if path.parent == out],
        },
        "runtime": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
        },
    }
    report = _json_ready(report)
    report_json_path = out / "cluster_validation_report.json"
    _json_write(report_json_path, report)
    markdown = _markdown_report(report, distributions, silhouette_summary, separation,
                                discovery_tests, k_compare)
    (out / "cluster_validation_report.md").write_text(markdown, encoding="utf-8", newline="\n")
    return report


def main() -> None:
    report = run_validation_pipeline()
    print(
        "Cluster validation complete: "
        f"{report['dataset']['primary_cohort_records']:,} planets, "
        f"{report['silhouette_observation_count']:,} per-observation silhouette results, "
        f"{len(report['outputs']['plots'])} plots."
    )
    print(f"Report: {ROOT / OUTPUT_DIR / 'cluster_validation_report.md'}")


if __name__ == "__main__":
    main()

