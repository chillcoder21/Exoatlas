"""Precompute interpretable diagnostics from ExoAtlas's frozen primary model."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPLICATION_DATA = Path("data/processed/planets_application.csv")
RAW_SOURCE = Path("data/raw/PSCompPars_2026.10.30_13.47.46.csv")
FEATURE_DATA = Path("data/processed/clustering_features_with_temp.csv")
ASSIGNMENTS = Path("data/cluster_experiments/cluster_assignments_with_temp_k4.csv")
SILHOUETTES = Path("data/cluster_validation/cluster_silhouette_validation.csv")
SCALER = Path("artifacts/preprocessing/scaler_with_temp.joblib")
MODEL = Path("artifacts/clustering/kmeans_with_temp_k4.joblib")
REGISTRY = Path("artifacts/clustering/model_registry.json")
PROFILES = Path("data/metadata/cluster_profiles.json")
PREPROCESSING_REPORT = Path("data/metadata/preprocessing_report.json")
APPLICATION_REPORT = Path("data/metadata/application_data_report.json")
VALIDATION_REPORT = Path("data/cluster_validation/cluster_validation_report.json")
OUTPUT_CSV = Path("data/processed/planet_outlier_diagnostics.csv")
OUTPUT_JSON = Path("data/metadata/outlier_analysis_report.json")
OUTPUT_MARKDOWN = Path("data/metadata/outlier_analysis_report.md")

TRANSFORMED_COLUMNS = ["log10_pl_rade", "log10_pl_orbper", "pl_eqt", "pl_orbeccen"]
SCALED_COLUMNS = [
    "scaled_log10_pl_rade",
    "scaled_log10_pl_orbper",
    "scaled_pl_eqt",
    "scaled_pl_orbeccen",
]
FEATURES: dict[str, dict[str, str]] = {
    "pl_rade": {"label": "Planetary radius", "unit": "Earth radii"},
    "pl_orbper": {"label": "Orbital period", "unit": "days"},
    "pl_eqt": {"label": "Equilibrium temperature", "unit": "K"},
    "pl_orbeccen": {"label": "Orbital eccentricity", "unit": "dimensionless"},
}


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 checksum for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    return json.loads((root / path).read_text(encoding="utf-8"))


def _expected_input_hashes(root: Path) -> dict[str, str]:
    """Collect pinned input checksums from the existing frozen manifests."""
    registry = _read_json(root, REGISTRY)
    primary = registry["primary_model"]
    preprocessing = _read_json(root, PREPROCESSING_REPORT)
    application = _read_json(root, APPLICATION_REPORT)
    validation = _read_json(root, VALIDATION_REPORT)
    validation_outputs = validation["integrity"]["generated_output_sha256"]
    values = {
        RAW_SOURCE.as_posix(): primary["dataset"]["source_sha256"],
        APPLICATION_DATA.as_posix(): application["outputs"][APPLICATION_DATA.as_posix()],
        FEATURE_DATA.as_posix(): preprocessing["outputs"]["sha256"][FEATURE_DATA.as_posix()],
        ASSIGNMENTS.as_posix(): primary["assignments"]["sha256"],
        SILHOUETTES.as_posix(): validation_outputs[SILHOUETTES.as_posix()],
        SCALER.as_posix(): primary["scaler"]["sha256"],
        MODEL.as_posix(): primary["fitted_model"]["sha256"],
        PROFILES.as_posix(): application["outputs"][PROFILES.as_posix()],
    }
    return values


def verify_input_hashes(root: Path, expected: dict[str, str] | None = None) -> dict[str, str]:
    """Verify frozen inputs before/after analysis and return their checksums."""
    expected = expected or _expected_input_hashes(root)
    observed: dict[str, str] = {}
    for relative, pinned in expected.items():
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Required outlier-analysis input is missing: {relative}")
        actual = sha256_file(path)
        if actual != pinned:
            raise ValueError(f"Frozen input checksum mismatch for {relative}: {actual}")
        observed[relative] = actual
    return observed


def within_cluster_percentiles(distances: pd.Series, cluster_ids: pd.Series) -> pd.Series:
    """Compute average-rank empirical percentiles independently by cluster."""
    if len(distances) != len(cluster_ids):
        raise ValueError("Distances and cluster IDs must have matching lengths.")
    if distances.isna().any() or cluster_ids.isna().any():
        raise ValueError("Percentile inputs must contain only assigned finite observations.")
    if not np.isfinite(distances.to_numpy(dtype=float)).all():
        raise ValueError("Centroid distances must be finite.")
    return distances.groupby(cluster_ids, sort=False).rank(method="average", pct=True) * 100.0


def feature_relation(value: float, reference: dict[str, Any]) -> tuple[str, float | None]:
    """Compare an original-unit measurement with frozen cluster quartiles."""
    q1, q3 = float(reference["q1"]), float(reference["q3"])
    median, iqr = float(reference["median"]), float(reference["iqr"])
    relation = "below_q1" if value < q1 else "above_q3" if value > q3 else "within_q1_q3"
    displacement = (value - median) / iqr if iqr > 0 else None
    return relation, displacement


def centroid_distances(points: np.ndarray, labels: np.ndarray, centers: np.ndarray) -> np.ndarray:
    """Return Euclidean distances to the already-assigned frozen centroids."""
    points = np.asarray(points, dtype=float)
    labels = np.asarray(labels, dtype=int)
    centers = np.asarray(centers, dtype=float)
    if points.ndim != 2 or centers.ndim != 2 or points.shape[1] != centers.shape[1]:
        raise ValueError("Points and centroid arrays must have matching feature dimensions.")
    if len(points) != len(labels) or not len(points):
        raise ValueError("Each point must have one assigned cluster label.")
    if not np.isfinite(points).all() or not np.isfinite(centers).all():
        raise ValueError("Points and centroids must be finite.")
    if (labels < 0).any() or (labels >= len(centers)).any():
        raise ValueError("Cluster labels must identify an available centroid.")
    return np.linalg.norm(points - centers[labels], axis=1)


def build_diagnostics(
    application: pd.DataFrame,
    features: pd.DataFrame,
    assignments: pd.DataFrame,
    silhouette_rows: pd.DataFrame,
    scaler: Any,
    model: Any,
    profiles: dict[str, Any],
) -> pd.DataFrame:
    """Build all-catalogue diagnostics using frozen model geometry and labels."""
    if application["pl_name"].isna().any() or application["pl_name"].duplicated().any():
        raise ValueError("Application data must have unique nonmissing pl_name identifiers.")
    if features["pl_name"].isna().any() or features["pl_name"].duplicated().any():
        raise ValueError("Feature matrix must have unique nonmissing pl_name identifiers.")
    if assignments["pl_name"].isna().any() or assignments["pl_name"].duplicated().any():
        raise ValueError("Assignments must have unique nonmissing pl_name identifiers.")
    if len(features) != len(assignments) or not np.array_equal(
        features["pl_name"].astype(str).to_numpy(), assignments["pl_name"].astype(str).to_numpy()
    ):
        raise ValueError("Feature matrix and frozen assignments must have identical ordered identifiers.")
    assigned_application = application.loc[application["assignment_status"] == "assigned", "pl_name"].astype(str)
    if not np.array_equal(assigned_application.to_numpy(), features["pl_name"].astype(str).to_numpy()):
        raise ValueError("Assigned application identifiers do not match the frozen primary cohort in order.")
    physical_columns = list(FEATURES)
    source_physical = application.loc[application["assignment_status"] == "assigned", physical_columns].apply(
        pd.to_numeric, errors="coerce"
    ).to_numpy(dtype=float)
    feature_physical = features[physical_columns].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    if not np.array_equal(source_physical, feature_physical):
        raise ValueError("Application physical measurements differ from the saved primary feature cohort.")
    if getattr(model, "n_clusters", None) != 4:
        raise ValueError("Expected the saved four-cluster K-means model.")

    transformed = features[TRANSFORMED_COLUMNS].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    saved_scaled = features[SCALED_COLUMNS].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(transformed).all() or not np.isfinite(saved_scaled).all():
        raise ValueError("Saved primary features must be finite numeric values.")
    if getattr(scaler, "n_features_in_", None) != 4:
        raise ValueError("Saved scaler is not the frozen four-feature scaler.")
    scaled = scaler.transform(transformed)
    if not np.allclose(scaled, saved_scaled, rtol=1e-12, atol=1e-12):
        raise ValueError("Existing scaler output differs from the saved primary feature matrix.")

    assignment_ids = assignments["pl_name"].astype(str).to_numpy()
    cluster_ids = pd.to_numeric(assignments["cluster_id"], errors="coerce").to_numpy(dtype=int)
    predictions = model.predict(saved_scaled)
    if not np.array_equal(predictions, cluster_ids):
        raise ValueError("Saved model predictions differ from the frozen primary assignments.")
    centers = np.asarray(model.cluster_centers_, dtype=float)
    if centers.shape != (4, 4) or not np.isfinite(centers).all():
        raise ValueError("Saved model must contain four finite centroids in the frozen feature space.")
    distances = centroid_distances(saved_scaled, cluster_ids, centers)
    distance_series = pd.Series(distances, index=pd.RangeIndex(len(distances)))
    cluster_series = pd.Series(cluster_ids, index=pd.RangeIndex(len(cluster_ids)))
    percentiles = within_cluster_percentiles(distance_series, cluster_series)

    saved_silhouettes = silhouette_rows.loc[silhouette_rows["experiment"] == "with_temp"].copy()
    saved_silhouettes = saved_silhouettes[["pl_name", "cluster_id", "silhouette_score"]]
    if saved_silhouettes["pl_name"].duplicated().any() or len(saved_silhouettes) != len(features):
        raise ValueError("Saved primary silhouette table must contain exactly one row per assigned planet.")
    if not np.array_equal(saved_silhouettes["pl_name"].astype(str).to_numpy(), assignment_ids):
        # Validation output order may differ; use an explicit identifier check and then reindex.
        if set(saved_silhouettes["pl_name"].astype(str)) != set(assignment_ids):
            raise ValueError("Saved primary silhouette identifiers do not match the frozen cohort.")
    silhouette_cluster_ids = saved_silhouettes.set_index("pl_name").loc[assignment_ids, "cluster_id"].to_numpy(dtype=int)
    if not np.array_equal(silhouette_cluster_ids, cluster_ids):
        raise ValueError("Saved primary silhouette cluster labels differ from frozen assignments.")
    silhouette_values = pd.to_numeric(
        saved_silhouettes.set_index("pl_name").loc[assignment_ids, "silhouette_score"], errors="coerce"
    ).to_numpy(dtype=float)
    if not np.isfinite(silhouette_values).all() or (silhouette_values < -1).any() or (silhouette_values > 1).any():
        raise ValueError("Saved silhouette values must be finite and within [-1, 1].")

    assigned = pd.DataFrame({
        "pl_name": assignment_ids,
        "cluster_id": cluster_ids,
        "assignment_status": "assigned",
        "centroid_distance": distances,
        "cluster_distance_percentile": percentiles.to_numpy(dtype=float),
        "silhouette_score": silhouette_values,
    })
    profile_by_cluster = {
        int(cluster["cluster_id"]): cluster["physical_features"] for cluster in profiles["clusters"]
    }
    for feature in FEATURES:
        original_values = pd.to_numeric(features[feature], errors="coerce").to_numpy(dtype=float)
        relations: list[str] = []
        displacements: list[float | None] = []
        for value, cluster_id in zip(original_values, cluster_ids, strict=True):
            relation, displacement = feature_relation(value, profile_by_cluster[int(cluster_id)][feature])
            relations.append(relation)
            displacements.append(displacement)
        assigned[f"{feature}_relation"] = relations
        assigned[f"{feature}_iqr_from_median"] = displacements

    result = application[["pl_name", "hostname", *physical_columns, "cluster_id", "assignment_status"]].copy()
    result["pl_name"] = result["pl_name"].astype(str)
    result = result.merge(
        assigned.drop(columns=["cluster_id", "assignment_status"]),
        on="pl_name",
        how="left",
        validate="one_to_one",
        sort=False,
    )
    is_assigned = result["assignment_status"] == "assigned"
    if is_assigned.sum() != len(features):
        raise ValueError("Merged outlier diagnostics lost assigned application records.")
    if result.loc[~is_assigned, ["centroid_distance", "cluster_distance_percentile", "silhouette_score"]].notna().any().any():
        raise ValueError("Unassigned planets must not receive fabricated model diagnostics.")
    for feature in FEATURES:
        if result.loc[~is_assigned, f"{feature}_relation"].notna().any():
            raise ValueError("Unassigned planets must not receive cluster-relative feature comparisons.")
    return result


def _distribution_report(diagnostics: pd.DataFrame) -> dict[str, Any]:
    assigned = diagnostics.loc[diagnostics["assignment_status"] == "assigned"]
    percentile_edges = list(range(0, 101, 10))
    percentile_labels = [f"{edge}-{edge + 10}" for edge in percentile_edges[:-1]]
    percentile_counts = pd.cut(
        assigned["cluster_distance_percentile"], bins=percentile_edges,
        labels=percentile_labels, include_lowest=True, right=True,
    ).value_counts(sort=False)
    silhouette_edges = [-1.0, -0.5, 0.0, 0.25, 0.5, 0.75, 1.0]
    silhouette_labels = ["-1 to -0.5", "-0.5 to 0", "0 to 0.25", "0.25 to 0.5", "0.5 to 0.75", "0.75 to 1"]
    silhouette_counts = pd.cut(
        assigned["silhouette_score"], bins=silhouette_edges, labels=silhouette_labels,
        include_lowest=True, right=True,
    ).value_counts(sort=False)
    feature_relations: dict[str, dict[str, int]] = {}
    for feature in FEATURES:
        feature_relations[feature] = {
            key: int((assigned[f"{feature}_relation"] == key).sum())
            for key in ("below_q1", "within_q1_q3", "above_q3")
        }
    stats = assigned["cluster_distance_percentile"].describe(percentiles=[0.25, 0.5, 0.75])
    return {
        "centroid_distance_percentile": {
            "minimum": float(stats["min"]),
            "q1": float(stats["25%"]),
            "median": float(stats["50%"]),
            "q3": float(stats["75%"]),
            "maximum": float(stats["max"]),
            "histogram": {str(key): int(value) for key, value in percentile_counts.items()},
        },
        "silhouette": {
            "minimum": float(assigned["silhouette_score"].min()),
            "median": float(assigned["silhouette_score"].median()),
            "maximum": float(assigned["silhouette_score"].max()),
            "negative_count": int((assigned["silhouette_score"] < 0).sum()),
            "histogram": {str(key): int(value) for key, value in silhouette_counts.items()},
        },
        "feature_relations": feature_relations,
    }


def _markdown_report(report: dict[str, Any], diagnostics: pd.DataFrame) -> str:
    summary = report["summary"]
    dist = report["distributions"]
    top = diagnostics.loc[diagnostics["assignment_status"] == "assigned"].nlargest(
        12, "cluster_distance_percentile"
    )
    lines = [
        "# The Outliers — Analysis Report",
        "",
        "## Dataset and method",
        "",
        f"The catalogue contains **{summary['catalogue_records']:,}** confirmed-planet records. "
        f"The frozen four-feature K=4 model covers **{summary['assigned_records']:,}**; "
        f"**{summary['unassigned_records']:,}** remain searchable but have no model diagnostics.",
        "",
        "For each assigned planet, the pipeline measures Euclidean distance to its existing assigned K-means "
        "centroid in the saved standardized space: log10 radius, log10 orbital period, raw equilibrium "
        "temperature, and raw eccentricity after the already-fitted StandardScaler. It ranks distance within "
        "the assigned cluster using average empirical ranks (ties share their average rank). No model or scaler is fitted.",
        "",
        "The saved `with_temp` silhouette result is joined by `pl_name`; it is not recomputed. A negative "
        "silhouette is a weak-separation diagnostic under this representation, not a physical classification.",
        "",
        "## Population summaries",
        "",
        f"The within-cluster distance percentile has median **{dist['centroid_distance_percentile']['median']:.2f}%** "
        f"(Q1 {dist['centroid_distance_percentile']['q1']:.2f}%, Q3 {dist['centroid_distance_percentile']['q3']:.2f}%). "
        f"There are **{dist['silhouette']['negative_count']:,}** negative saved silhouettes among assigned planets.",
        "",
        "### Feature relations to assigned-cluster quartiles",
        "",
        "| Measurement | Below Q1 | Within Q1–Q3 | Above Q3 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for feature, definition in FEATURES.items():
        counts = dist["feature_relations"][feature]
        lines.append(
            f"| {definition['label']} ({definition['unit']}) | {counts['below_q1']:,} | "
            f"{counts['within_q1_q3']:,} | {counts['above_q3']:,} |"
        )
    lines.extend([
        "",
        "A value outside Q1–Q3 is a descriptive comparison, not evidence of error or physical exceptionalism. "
        "The optional IQR displacement is `(measurement − cluster median) / cluster IQR`; it is omitted when "
        "IQR is zero. It is not a probability or a combined outlier score.",
        "",
        "## Highest within-cluster distance percentiles",
        "",
        "These are the largest empirical distance percentiles under this specific model representation. They are "
        "review candidates, not asserted anomalies.",
        "",
        "| Planet | Cluster | Distance (standardized space) | Within-cluster percentile | Saved silhouette |",
        "| --- | ---: | ---: | ---: | ---: |",
    ])
    for row in top.itertuples(index=False):
        lines.append(
            f"| {row.pl_name} | {int(row.cluster_id)} | {row.centroid_distance:.4f} | "
            f"{row.cluster_distance_percentile:.2f}% | {row.silhouette_score:.4f} |"
        )
    lines.extend([
        "",
        "## Interpretation limits",
        "",
        "- High centroid distance, unusual individual measurements, and low silhouette describe different properties; they are not combined into one score.",
        "- A high distance does not prove an observation is incorrectly assigned. A low silhouette indicates weak separation in the selected feature space.",
        "- Quartiles are reference summaries of the assigned groups. An outside-IQR value is not automatically anomalous or erroneous.",
        "- Cluster IDs are arbitrary partition labels. The result depends on selected features, transformations, and scaling.",
        "- This confirmed-planet catalogue reflects observational and discovery biases; four measurements do not support claims about habitability, atmospheres, composition, or physical mechanisms.",
        "- Unassigned planets have null centroid, percentile, silhouette, and cluster-relative feature diagnostics. No missing values are imputed.",
        "",
        "## Reproducibility and integrity",
        "",
        f"The frozen source, application data, feature matrix, assignments, silhouette file, scaler, model, and cluster profiles were checksum-verified before and after computation. "
        f"The prepared diagnostics CSV SHA-256 is `{report['outputs']['diagnostics_csv_sha256']}`.",
        "",
    ])
    return "\n".join(lines)


def run_analysis(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Build diagnostics and reproducibility reports without altering frozen inputs."""
    root = Path(root)
    pinned_hashes = _expected_input_hashes(root)
    before = verify_input_hashes(root, pinned_hashes)
    application = pd.read_csv(root / APPLICATION_DATA, low_memory=False, dtype={"pl_name": "string"})
    features = pd.read_csv(root / FEATURE_DATA, low_memory=False, dtype={"pl_name": "string"})
    assignments = pd.read_csv(root / ASSIGNMENTS, dtype={"pl_name": "string"})
    silhouettes = pd.read_csv(root / SILHOUETTES, dtype={"pl_name": "string"})
    scaler = joblib.load(root / SCALER)
    model = joblib.load(root / MODEL)
    profiles = _read_json(root, PROFILES)
    diagnostics = build_diagnostics(application, features, assignments, silhouettes, scaler, model, profiles)

    root.joinpath(OUTPUT_CSV).parent.mkdir(parents=True, exist_ok=True)
    diagnostics.to_csv(root / OUTPUT_CSV, index=False, lineterminator="\n", float_format="%.17g")
    csv_hash = sha256_file(root / OUTPUT_CSV)
    assigned = diagnostics.loc[diagnostics["assignment_status"] == "assigned"]
    report: dict[str, Any] = {
        "schema_version": 1,
        "dataset": {
            "source_name": _read_json(root, REGISTRY)["primary_model"]["dataset"]["source_name"],
            "source_sha256": _read_json(root, REGISTRY)["primary_model"]["dataset"]["source_sha256"],
            "application_data": APPLICATION_DATA.as_posix(),
            "primary_model_id": _read_json(root, REGISTRY)["primary_model"]["model_id"],
            "primary_model_k": 4,
        },
        "summary": {
            "catalogue_records": int(len(diagnostics)),
            "assigned_records": int(len(assigned)),
            "unassigned_records": int(len(diagnostics) - len(assigned)),
            "negative_silhouette_records": int((assigned["silhouette_score"] < 0).sum()),
        },
        "method": {
            "centroid_distance": "Euclidean distance to each planet's frozen assigned K-means centroid in the exact saved four-feature standardized space.",
            "within_cluster_percentile": "Empirical percentile rank computed separately within assigned cluster using average ranks for ties, multiplied by 100.",
            "silhouette": "Reused from cluster_validation/cluster_silhouette_validation.csv for experiment=with_temp, joined by pl_name and checked against frozen cluster IDs.",
            "feature_relations": "Original physical measurements compared with frozen assigned-cluster Q1, median, Q3, and IQR profile values.",
            "physical_measurements": "Original catalogue hostname and four clustering measurements copied unchanged from the prepared application dataset.",
            "iqr_displacement": "(measurement - cluster median) / cluster IQR; null when the cluster IQR is zero.",
            "threshold_policy": "No universal distance threshold or combined outlier score is defined. UI percentile filters select a review range only.",
            "missing_data": "Unassigned catalogue records are preserved with null cluster diagnostics; no imputation or deletion.",
            "model_fitting": False,
            "scaler_refitting": False,
        },
        "distributions": _distribution_report(diagnostics),
        "input_sha256_before": before,
        "outputs": {
            "diagnostics_csv": OUTPUT_CSV.as_posix(),
            "diagnostics_csv_sha256": csv_hash,
            "json_report": OUTPUT_JSON.as_posix(),
            "markdown_report": OUTPUT_MARKDOWN.as_posix(),
        },
        "preserved_inputs_unchanged": True,
        "limitations": [
            "Centroid distance, feature-level quartile position, and silhouette measure different properties and must not be collapsed into one outlier score.",
            "An observation outside the IQR is not automatically anomalous or incorrect.",
            "Cluster-relative values depend on the frozen exploratory K=4 feature representation and the selected confirmed-planet catalogue.",
            "Planet records are treated independently even when multiple planets share a host star.",
        ],
    }
    markdown = _markdown_report(report, diagnostics)
    after = verify_input_hashes(root, pinned_hashes)
    report["input_sha256_after"] = after
    report["preserved_inputs_unchanged"] = before == after
    if not report["preserved_inputs_unchanged"]:
        raise RuntimeError("A frozen input changed during outlier analysis.")
    root.joinpath(OUTPUT_JSON).parent.mkdir(parents=True, exist_ok=True)
    (root / OUTPUT_JSON).write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    (root / OUTPUT_MARKDOWN).write_text(markdown, encoding="utf-8")
    return report


def main() -> None:
    report = run_analysis()
    summary = report["summary"]
    print(
        "Outlier diagnostics complete: "
        f"{summary['assigned_records']:,} assigned / {summary['catalogue_records']:,} catalogue records; "
        f"{summary['negative_silhouette_records']:,} negative saved silhouettes."
    )
    print(f"Reports: {OUTPUT_JSON.as_posix()} and {OUTPUT_MARKDOWN.as_posix()}")
    print(f"Prepared data: {OUTPUT_CSV.as_posix()}")


if __name__ == "__main__":
    main()
