"""Read-only Flask API for the prepared ExoAtlas scientific data layer."""

from __future__ import annotations

import math
import json
import hashlib
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPLICATION_DATA = Path("data/processed/planets_application.csv")
CLUSTER_METADATA = Path("data/metadata/cluster_profiles.json")
MODEL_REGISTRY = Path("artifacts/clustering/model_registry.json")
CLUSTERING_REPORT = Path("data/cluster_experiments/clustering_report.json")
VALIDATION_REPORT = Path("data/cluster_validation/cluster_validation_report.json")
OUTLIER_DIAGNOSTICS = Path("data/processed/planet_outlier_diagnostics.csv")
OUTLIER_REPORT = Path("data/metadata/outlier_analysis_report.json")
DISCOVERY_LENS_REPORT = Path("data/metadata/discovery_lens_report.json")
DISCOVERY_LENS_TIMELINE = Path("data/processed/discovery_method_timeline.csv")
DISCOVERY_LENS_PROPERTIES = Path("data/processed/discovery_method_property_summary.csv")
DISCOVERY_LENS_FACILITIES = Path("data/processed/discovery_facility_counts.csv")
DISCOVERY_LENS_VALUES = Path("data/processed/discovery_property_values.csv")
PRIMARY_FEATURES = Path("data/processed/clustering_features_with_temp.csv")
PRIMARY_SCALER = Path("artifacts/preprocessing/scaler_with_temp.joblib")
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
DEFAULT_NEIGHBOR_LIMIT = 5
MAX_NEIGHBOR_LIMIT = 20
TRANSFORMED_FEATURE_COLUMNS = ["log10_pl_rade", "log10_pl_orbper", "pl_eqt", "pl_orbeccen"]
SCALED_FEATURE_COLUMNS = [
    "scaled_log10_pl_rade",
    "scaled_log10_pl_orbper",
    "scaled_pl_eqt",
    "scaled_pl_orbeccen",
]
SIMILARITY_FEATURES = ["pl_rade", "pl_orbper", "pl_eqt", "pl_orbeccen"]


def _read_json(root: Path, relative: Path) -> dict[str, Any]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_discovery_lens(root: Path, planets: pd.DataFrame) -> dict[str, Any]:
    """Load and validate the offline summaries once when the API starts."""
    paths = {
        "timeline": DISCOVERY_LENS_TIMELINE,
        "property_summary": DISCOVERY_LENS_PROPERTIES,
        "facility_counts": DISCOVERY_LENS_FACILITIES,
        "property_values": DISCOVERY_LENS_VALUES,
        "report": DISCOVERY_LENS_REPORT,
    }
    missing = [relative.as_posix() for relative in paths.values() if not (root / relative).is_file()]
    if missing:
        raise RuntimeError(f"Discovery Lens offline outputs are not ready; missing generated files: {missing}")
    report = _read_json(root, DISCOVERY_LENS_REPORT)
    application_hash = _sha256_file(root / APPLICATION_DATA)
    if report.get("source", {}).get("prepared_application_sha256") != application_hash:
        raise RuntimeError("Discovery Lens report does not match the current prepared application dataset.")
    for key, relative in paths.items():
        if key == "report":
            continue
        expected = report.get("outputs", {}).get(relative.as_posix())
        if expected is None or _sha256_file(root / relative) != expected:
            raise RuntimeError(f"Discovery Lens output checksum mismatch: {relative.as_posix()}")

    timeline = pd.read_csv(root / DISCOVERY_LENS_TIMELINE, low_memory=False)
    property_summary = pd.read_csv(root / DISCOVERY_LENS_PROPERTIES, low_memory=False)
    facility_counts = pd.read_csv(root / DISCOVERY_LENS_FACILITIES, low_memory=False)
    property_values = pd.read_csv(
        root / DISCOVERY_LENS_VALUES,
        low_memory=False,
        dtype={"pl_name": "string", "hostname": "string", "discovery_method": "string", "property": "string"},
    )
    if len(planets) != report.get("dataset", {}).get("planet_records"):
        raise RuntimeError("Discovery Lens report and application catalogue disagree on record totals.")
    if timeline["discovery_year"].nunique() != 35 or len(timeline) != 35 * len(report.get("methods", [])):
        raise RuntimeError("Discovery Lens timeline does not contain every year and method combination.")
    if property_summary.duplicated(["discovery_method", "property"]).any():
        raise RuntimeError("Discovery Lens property summary contains duplicate method/property rows.")
    if property_values["pl_name"].isna().any() or property_values["hostname"].isna().any():
        raise RuntimeError("Discovery Lens distribution records must have planet and host identifiers.")
    methods = [item["discovery_method"] for item in report.get("methods", [])]
    if set(methods) != set(planets["discoverymethod"].dropna().astype(str).unique()):
        raise RuntimeError("Discovery Lens method categories disagree with the application catalogue.")
    return {
        "report": report,
        "methods": methods,
        "timeline": timeline,
        "property_summary": property_summary,
        "facility_counts": facility_counts,
        "property_values": property_values,
    }


def _load_data(root: Path) -> dict[str, Any]:
    """Load prepared tables and report metadata once when the app is created."""
    required = (
        APPLICATION_DATA,
        CLUSTER_METADATA,
        MODEL_REGISTRY,
        CLUSTERING_REPORT,
        VALIDATION_REPORT,
        OUTLIER_DIAGNOSTICS,
        OUTLIER_REPORT,
        PRIMARY_FEATURES,
        PRIMARY_SCALER,
        DISCOVERY_LENS_REPORT,
        DISCOVERY_LENS_TIMELINE,
        DISCOVERY_LENS_PROPERTIES,
        DISCOVERY_LENS_FACILITIES,
        DISCOVERY_LENS_VALUES,
    )
    missing = [path.as_posix() for path in required if not (root / path).is_file()]
    if missing:
        raise RuntimeError(f"ExoAtlas application data is not ready; missing generated files: {missing}")

    planets = pd.read_csv(
        root / APPLICATION_DATA,
        low_memory=False,
        dtype={"pl_name": "string", "cluster_id": "Int64", "assignment_status": "string"},
    )
    if "pl_name" not in planets or planets["pl_name"].isna().any() or planets["pl_name"].duplicated().any():
        raise RuntimeError("Application dataset must contain unique, nonmissing pl_name identifiers.")
    required_columns = {"hostname", "discoverymethod", "cluster_id", "assignment_status"}
    absent = sorted(required_columns.difference(planets.columns))
    if absent:
        raise RuntimeError(f"Application dataset is missing required columns: {absent}")
    assigned = planets["cluster_id"].notna()
    if not (planets.loc[assigned, "assignment_status"] == "assigned").all():
        raise RuntimeError("Application assignment status conflicts with cluster IDs.")
    if not (planets.loc[~assigned, "assignment_status"] == "unassigned").all():
        raise RuntimeError("Unclustered records must have status 'unassigned'.")

    clusters = _read_json(root, CLUSTER_METADATA)
    registry = _read_json(root, MODEL_REGISTRY)
    clustering = _read_json(root, CLUSTERING_REPORT)
    validation = _read_json(root, VALIDATION_REPORT)
    outlier_report = _read_json(root, OUTLIER_REPORT)
    cluster_ids = [int(item["cluster_id"]) for item in clusters["clusters"]]
    if cluster_ids != [0, 1, 2, 3]:
        raise RuntimeError("The primary application model must contain exactly clusters 0 through 3.")
    counts = planets["assignment_status"].value_counts().to_dict()
    if sum(counts.values()) != len(planets):
        raise RuntimeError("Application status counts do not sum to the dataset size.")
    outlier_diagnostics = pd.read_csv(
        root / OUTLIER_DIAGNOSTICS,
        low_memory=False,
        dtype={"pl_name": "string", "assignment_status": "string"},
    )
    if outlier_diagnostics["pl_name"].isna().any() or outlier_diagnostics["pl_name"].duplicated().any():
        raise RuntimeError("Outlier diagnostics must contain unique, nonmissing planet identifiers.")
    if not np.array_equal(
        outlier_diagnostics["pl_name"].astype(str).to_numpy(), planets["pl_name"].astype(str).to_numpy()
    ):
        raise RuntimeError("Outlier diagnostics identifiers must match the full application catalogue in order.")
    if not np.array_equal(
        outlier_diagnostics["assignment_status"].astype(str).to_numpy(),
        planets["assignment_status"].astype(str).to_numpy(),
    ):
        raise RuntimeError("Outlier diagnostics assignment status differs from the application catalogue.")
    required_outlier_columns = {
        "centroid_distance", "cluster_distance_percentile", "silhouette_score",
        "pl_rade_relation", "pl_orbper_relation", "pl_eqt_relation", "pl_orbeccen_relation",
        "pl_rade_iqr_from_median", "pl_orbper_iqr_from_median", "pl_eqt_iqr_from_median",
        "pl_orbeccen_iqr_from_median", "hostname", "pl_rade", "pl_orbper", "pl_eqt", "pl_orbeccen",
    }
    absent_outlier_columns = sorted(required_outlier_columns.difference(outlier_diagnostics.columns))
    if absent_outlier_columns:
        raise RuntimeError(f"Outlier diagnostics are missing required fields: {absent_outlier_columns}")
    for column in ["hostname", "pl_rade", "pl_orbper", "pl_eqt", "pl_orbeccen"]:
        left = planets[column]
        right = outlier_diagnostics[column]
        if column == "hostname":
            matches = left.fillna("").astype(str).to_numpy() == right.fillna("").astype(str).to_numpy()
        else:
            left_numeric = pd.to_numeric(left, errors="coerce").to_numpy(dtype=float)
            right_numeric = pd.to_numeric(right, errors="coerce").to_numpy(dtype=float)
            matches = np.array_equal(left_numeric, right_numeric, equal_nan=True)
        if not np.all(matches):
            raise RuntimeError(f"Outlier diagnostic output changed original application values in {column}.")
    assigned_outliers = outlier_diagnostics["assignment_status"] == "assigned"
    if int(assigned_outliers.sum()) != int(outlier_report["summary"]["assigned_records"]):
        raise RuntimeError("Outlier diagnostic assigned count conflicts with its report.")
    unavailable = ~assigned_outliers
    diagnostic_values = ["centroid_distance", "cluster_distance_percentile", "silhouette_score"]
    if outlier_diagnostics.loc[unavailable, diagnostic_values].notna().any().any():
        raise RuntimeError("Unassigned records must have null outlier diagnostics.")
    diagnostic_columns = [
        "pl_name", "centroid_distance", "cluster_distance_percentile", "silhouette_score",
        "pl_rade_relation", "pl_orbper_relation", "pl_eqt_relation", "pl_orbeccen_relation",
        "pl_rade_iqr_from_median", "pl_orbper_iqr_from_median", "pl_eqt_iqr_from_median",
        "pl_orbeccen_iqr_from_median",
    ]
    outlier_planets = planets.merge(
        outlier_diagnostics[diagnostic_columns],
        on="pl_name",
        how="left",
        validate="one_to_one",
        sort=False,
    )
    similarity = _load_similarity_index(root, planets)
    discovery_lens = _load_discovery_lens(root, planets)
    return {
        "root": root,
        "planets": planets,
        "clusters": clusters,
        "registry": registry,
        "clustering_report": clustering,
        "validation_report": validation,
        "outlier_report": outlier_report,
        "outlier_planets": outlier_planets,
        "assigned_count": int(counts.get("assigned", 0)),
        "unassigned_count": int(counts.get("unassigned", 0)),
        "cluster_ids": cluster_ids,
        "similarity": similarity,
        "discovery_lens": discovery_lens,
        "planets_by_name": planets.set_index("pl_name", drop=False),
        "discovery_methods": sorted(
            str(value) for value in planets["discoverymethod"].dropna().unique()
        ),
    }


def _json_scalar(value: Any) -> Any:
    """Convert pandas/NumPy values to strict JSON values, preserving nulls."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if pd.isna(value):
        return None
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {str(key): _json_scalar(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _parse_positive_int(name: str, raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{name}' must be an integer.") from exc
    if value < 1:
        raise ValueError(f"'{name}' must be at least 1.")
    if name == "page_size" and value > MAX_PAGE_SIZE:
        raise ValueError(f"'page_size' must not exceed {MAX_PAGE_SIZE}.")
    return value


def _pagination(frame: pd.DataFrame, page: int, page_size: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    total = len(frame)
    start = (page - 1) * page_size
    page_frame = frame.iloc[start : start + page_size]
    return _records(page_frame), {
        "page": page,
        "page_size": page_size,
        "total_records": total,
        "total_pages": math.ceil(total / page_size) if total else 0,
    }


def _query_error(message: str):
    return jsonify({"error": {"code": "invalid_query_parameter", "message": message}}), 400


def _parse_pagination():
    try:
        return (
            _parse_positive_int("page", request.args.get("page"), 1),
            _parse_positive_int("page_size", request.args.get("page_size"), DEFAULT_PAGE_SIZE),
        ), None
    except ValueError as exc:
        return None, _query_error(str(exc))


def _similarity_blockers(record: pd.Series) -> list[dict[str, str]]:
    """Describe incomplete or transformation-ineligible measurements."""
    blockers = []
    for feature in SIMILARITY_FEATURES:
        value = pd.to_numeric(pd.Series([record.get(feature)]), errors="coerce").iloc[0]
        if pd.isna(value) or not math.isfinite(float(value)):
            blockers.append({"feature": feature, "reason": "missing_or_non_finite"})
        elif feature in {"pl_rade", "pl_orbper"} and float(value) <= 0:
            blockers.append({"feature": feature, "reason": "must_be_positive_for_log10"})
    return blockers


def _load_similarity_index(root: Path, planets: pd.DataFrame) -> dict[str, Any]:
    """Build an in-memory neighbor index using the existing matrix and fitted scaler."""
    features = pd.read_csv(root / PRIMARY_FEATURES, low_memory=False, dtype={"pl_name": "string"})
    required = {"pl_name", *TRANSFORMED_FEATURE_COLUMNS, *SCALED_FEATURE_COLUMNS}
    missing = sorted(required.difference(features.columns))
    if missing:
        raise RuntimeError(f"Primary feature matrix is missing columns required for similarity: {missing}")
    if features["pl_name"].isna().any() or features["pl_name"].duplicated().any():
        raise RuntimeError("Primary feature matrix must contain unique, nonmissing planet identifiers.")

    assigned_ids = planets.loc[planets["cluster_id"].notna(), "pl_name"].astype("string")
    feature_ids = features["pl_name"].astype("string")
    if len(features) != len(assigned_ids) or set(feature_ids) != set(assigned_ids):
        raise RuntimeError("Primary feature-matrix identifiers do not match saved assigned planets.")

    transformed = features[TRANSFORMED_FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    saved_scaled = features[SCALED_FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(transformed).all() or not np.isfinite(saved_scaled).all():
        raise RuntimeError("Primary feature matrix contains non-finite transformed values.")

    scaler = joblib.load(root / PRIMARY_SCALER)
    if getattr(scaler, "n_features_in_", None) != len(TRANSFORMED_FEATURE_COLUMNS):
        raise RuntimeError("Saved primary scaler does not match the four-feature similarity space.")
    standardized = scaler.transform(transformed)
    if not np.isfinite(standardized).all() or not np.allclose(
        standardized, saved_scaled, rtol=1e-12, atol=1e-12
    ):
        raise RuntimeError("Saved scaler output does not match the frozen primary feature matrix.")

    names = feature_ids.astype(str).to_numpy()
    return {
        "names": names,
        "vectors": standardized,
        "name_to_index": {name: index for index, name in enumerate(names)},
        "scaler": scaler,
    }


def create_app(project_root: Path | None = None) -> Flask:
    """Create the app and load all prepared data a single time."""
    frontend_dist = PROJECT_ROOT / "frontend" / "dist"
    app = Flask(__name__, static_folder=None)
    data = _load_data(Path(project_root) if project_root else PROJECT_ROOT)
    app.extensions["exoatlas_data"] = data

    @app.get("/api/health")
    def health():
        model = data["registry"]["primary_model"]
        return jsonify({
            "service": "exoatlas-api",
            "status": "ok",
            "data_ready": True,
            "dataset": {
                "total_planets": len(data["planets"]),
                "assigned_planets": data["assigned_count"],
                "unassigned_planets": data["unassigned_count"],
            },
            "model": {"id": model["model_id"], "version": model["version"]},
        })

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": {"code": "not_found", "message": "Endpoint or resource was not found."}}), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"error": {"code": "method_not_allowed", "message": "HTTP method is not supported for this endpoint."}}), 405

    @app.get("/api/overview")
    def overview():
        planets = data["planets"]
        method_counts = planets["discoverymethod"].value_counts(dropna=False).sort_index()
        model = data["registry"]["primary_model"]
        return jsonify({
            "dataset": {
                "total_confirmed_planets": len(planets),
                "with_primary_cluster_assignment": data["assigned_count"],
                "without_cluster_assignment": data["unassigned_count"],
                "number_of_clusters": len(data["cluster_ids"]),
                "discovery_method_counts": {str(key): int(value) for key, value in method_counts.items()},
                "version": f"PSCompPars-{model['dataset']['snapshot_date']}",
                "source_sha256": model["dataset"]["source_sha256"],
            },
            "model": {"id": model["model_id"], "version": model["version"], "status": model["status"]},
        })

    def filter_planets(frame: pd.DataFrame, *, include_search: bool = True) -> tuple[pd.DataFrame | None, Any | None]:
        result = frame
        search = request.args.get("search") if include_search else None
        if search is not None and search.strip():
            term = search.strip()
            matching_name = result["pl_name"].str.contains(term, case=False, regex=False, na=False)
            matching_host = result["hostname"].str.contains(term, case=False, regex=False, na=False)
            result = result.loc[matching_name | matching_host]

        cluster_raw = request.args.get("cluster_id")
        if cluster_raw is not None:
            try:
                cluster_id = int(cluster_raw)
            except ValueError:
                return None, _query_error("'cluster_id' must be an integer from 0 through 3.")
            if cluster_id not in data["cluster_ids"]:
                return None, _query_error("'cluster_id' must be one of 0, 1, 2, or 3.")
            result = result.loc[result["cluster_id"] == cluster_id]

        discovery_method = request.args.get("discovery_method")
        if discovery_method is not None:
            method_match = next(
                (method for method in data["discovery_methods"] if method.casefold() == discovery_method.casefold()),
                None,
            )
            if method_match is None:
                return None, _query_error("'discovery_method' must match a method present in the dataset.")
            result = result.loc[result["discoverymethod"] == method_match]

        assignment_status = request.args.get("assignment_status")
        if assignment_status is not None:
            assignment_status = assignment_status.casefold()
            if assignment_status not in {"assigned", "unassigned"}:
                return None, _query_error("'assignment_status' must be 'assigned' or 'unassigned'.")
            result = result.loc[result["assignment_status"] == assignment_status]
        return result, None

    @app.get("/api/planets")
    def list_planets():
        pagination, error = _parse_pagination()
        if error:
            return error
        filtered, error = filter_planets(data["planets"])
        if error:
            return error
        records, page_info = _pagination(filtered, *pagination)
        return jsonify({
            "pagination": page_info,
            "filters": {
                "search": request.args.get("search"),
                "cluster_id": request.args.get("cluster_id"),
                "discovery_method": request.args.get("discovery_method"),
                "assignment_status": request.args.get("assignment_status"),
            },
            "records": records,
        })

    @app.get("/api/planets/<path:planet_id>")
    def get_planet(planet_id: str):
        matches = data["planets"].loc[data["planets"]["pl_name"] == planet_id]
        if matches.empty:
            return jsonify({"error": {"code": "not_found", "message": "Planet identifier was not found."}}), 404
        return jsonify({"record": _records(matches.iloc[:1])[0]})

    @app.get("/api/planets/<path:planet_id>/similar")
    def similar_planets(planet_id: str):
        """Rank eligible planets in the saved standardized four-feature space."""
        try:
            limit = _parse_positive_int("limit", request.args.get("limit"), DEFAULT_NEIGHBOR_LIMIT)
        except ValueError as exc:
            return _query_error(str(exc))
        if limit > MAX_NEIGHBOR_LIMIT:
            return _query_error(f"'limit' must not exceed {MAX_NEIGHBOR_LIMIT}.")

        planets_by_name = data["planets_by_name"]
        if planet_id not in planets_by_name.index:
            return jsonify({"error": {"code": "not_found", "message": "Planet identifier was not found."}}), 404
        record = planets_by_name.loc[planet_id]
        method = {
            "name": "Euclidean distance in the saved standardized four-feature primary space",
            "features": ["log10(pl_rade)", "log10(pl_orbper)", "pl_eqt", "pl_orbeccen"],
            "scaling": "Existing fitted four-feature StandardScaler; not refit for this request.",
            "interpretation": (
                "Smaller distance means closer measured values under this selected representation; "
                "it is not a probability or a claim of physical identity."
            ),
        }
        similarity = data["similarity"]
        query_index = similarity["name_to_index"].get(planet_id)
        if query_index is None:
            blockers = _similarity_blockers(record)
            saved_reason = record.get("four_feature_eligibility_reason")
            detail = ", ".join(f"{item['feature']} ({item['reason']})" for item in blockers)
            if not detail and isinstance(saved_reason, str) and saved_reason:
                detail = saved_reason
            if not detail:
                detail = "The saved primary feature matrix does not include this record."
            return jsonify({
                "planet_id": planet_id,
                "eligibility": {
                    "eligible": False,
                    "message": (
                        "Four-feature similarity is unavailable because this record is outside "
                        "the saved complete-case primary cohort."
                    ),
                    "blockers": blockers,
                    "saved_eligibility_reason": saved_reason if isinstance(saved_reason, str) else None,
                    "detail": detail,
                },
                "method": method,
                "candidate_pool_size": 0,
                "neighbor_count": 0,
                "neighbors": [],
            })

        target = similarity["vectors"][query_index]
        differences = similarity["vectors"] - target
        distances = np.sqrt(np.einsum("ij,ij->i", differences, differences))
        distances[query_index] = np.inf
        order = np.lexsort((similarity["names"], distances))
        neighbors = []
        for index in order:
            if not math.isfinite(float(distances[index])):
                continue
            name = similarity["names"][index]
            neighbor = planets_by_name.loc[name]
            row = {str(key): _json_scalar(value) for key, value in neighbor.items()}
            row["similarity_distance"] = float(distances[index])
            neighbors.append(row)
            if len(neighbors) >= limit:
                break

        return jsonify({
            "planet_id": planet_id,
            "eligibility": {"eligible": True, "message": "Four-feature similarity is available."},
            "method": method,
            "candidate_pool_size": len(similarity["names"]) - 1,
            "neighbor_count": len(neighbors),
            "neighbors": neighbors,
        })

    @app.get("/api/outliers/overview")
    def outliers_overview():
        return jsonify({
            "summary": data["outlier_report"]["summary"],
            "distributions": data["outlier_report"]["distributions"],
            "method": data["outlier_report"]["method"],
            "limitations": data["outlier_report"]["limitations"],
            "cluster_profiles": data["clusters"]["clusters"],
        })

    @app.get("/api/outliers/observations")
    def outlier_observations():
        try:
            page, page_size = _parse_positive_int("page", request.args.get("page"), 1), _parse_positive_int(
                "page_size", request.args.get("page_size"), DEFAULT_PAGE_SIZE
            )
        except ValueError as exc:
            return _query_error(str(exc))
        percentile_raw = request.args.get("percentile_min", "90")
        try:
            percentile_min = float(percentile_raw)
        except (TypeError, ValueError):
            return _query_error("'percentile_min' must be a number from 0 through 100.")
        if not math.isfinite(percentile_min) or percentile_min < 0 or percentile_min > 100:
            return _query_error("'percentile_min' must be a number from 0 through 100.")
        sort_by = request.args.get("sort_by", "distance_percentile")
        if sort_by not in {"distance_percentile", "silhouette"}:
            return _query_error("'sort_by' must be 'distance_percentile' or 'silhouette'.")

        frame = data["outlier_planets"].loc[
            (data["outlier_planets"]["assignment_status"] == "assigned")
            & (data["outlier_planets"]["cluster_distance_percentile"] >= percentile_min)
        ]
        cluster_raw = request.args.get("cluster_id")
        if cluster_raw is not None:
            try:
                cluster_id = int(cluster_raw)
            except ValueError:
                return _query_error("'cluster_id' must be an integer from 0 through 3.")
            if cluster_id not in data["cluster_ids"]:
                return _query_error("'cluster_id' must be one of 0, 1, 2, or 3.")
            frame = frame.loc[frame["cluster_id"] == cluster_id]
        search = request.args.get("search")
        if search and search.strip():
            term = search.strip()
            match_planet = frame["pl_name"].astype("string").str.contains(term, case=False, regex=False, na=False)
            match_host = frame["hostname"].astype("string").str.contains(term, case=False, regex=False, na=False)
            frame = frame.loc[match_planet | match_host]
        if sort_by == "silhouette":
            frame = frame.sort_values(
                ["silhouette_score", "cluster_distance_percentile", "pl_name"],
                ascending=[True, False, True], kind="mergesort",
            )
        else:
            frame = frame.sort_values(
                ["cluster_distance_percentile", "centroid_distance", "pl_name"],
                ascending=[False, False, True], kind="mergesort",
            )
        records, page_info = _pagination(frame, page, page_size)
        return jsonify({
            "pagination": page_info,
            "filters": {
                "percentile_min": percentile_min,
                "cluster_id": cluster_raw,
                "search": search,
                "sort_by": sort_by,
            },
            "records": records,
            "ranking_note": (
                "Distance percentiles are ranked within each assigned cluster. The percentile filter selects a review range; it is not a universal anomaly threshold."
                if sort_by == "distance_percentile"
                else "Rows are ordered by saved silhouette from lowest to highest, then by centroid percentile. Silhouette describes cluster separation, not measurement unusualness."
            ),
        })

    @app.get("/api/outliers/planets/<path:planet_id>")
    def outlier_planet(planet_id: str):
        matches = data["outlier_planets"].loc[data["outlier_planets"]["pl_name"] == planet_id]
        if matches.empty:
            return jsonify({"error": {"code": "not_found", "message": "Planet identifier was not found."}}), 404
        record = matches.iloc[0]
        assigned_record = record["assignment_status"] == "assigned"
        cluster_id = int(record["cluster_id"]) if assigned_record else None
        profile = next(
            (item for item in data["clusters"]["clusters"] if item["cluster_id"] == cluster_id), None
        )
        comparisons = []
        for feature, label in (
            ("pl_rade", "Planetary radius"),
            ("pl_orbper", "Orbital period"),
            ("pl_eqt", "Equilibrium temperature"),
            ("pl_orbeccen", "Orbital eccentricity"),
        ):
            reference = profile["physical_features"][feature] if profile else None
            comparisons.append({
                "feature": feature,
                "label": label,
                "value": record.get(feature),
                "unit": reference["unit"] if reference else None,
                "relation": record.get(f"{feature}_relation") if assigned_record else None,
                "iqr_from_median": record.get(f"{feature}_iqr_from_median") if assigned_record else None,
                "reference": reference,
            })
        return jsonify({
            "record": {str(key): _json_scalar(value) for key, value in record.items()},
            "diagnostics_available": bool(assigned_record),
            "cluster_profile": profile,
            "feature_comparisons": comparisons,
            "unavailable_reason": None if assigned_record else (
                "This planet is outside the frozen four-feature complete-case cohort, so no centroid distance, "
                "within-cluster percentile, silhouette, or cluster-relative feature comparison is available."
            ),
        })

    @app.get("/api/clusters")
    def list_clusters():
        return jsonify({
            "model_id": data["clusters"]["model_id"],
            "cohort_size": data["clusters"]["cohort_size"],
            "clusters": data["clusters"]["clusters"],
        })

    @app.get("/api/clusters/<int:cluster_id>")
    def get_cluster(cluster_id: int):
        profile = next(
            (item for item in data["clusters"]["clusters"] if item["cluster_id"] == cluster_id),
            None,
        )
        if profile is None:
            return jsonify({"error": {"code": "not_found", "message": "Cluster identifier was not found."}}), 404
        pagination, error = _parse_pagination()
        if error:
            return error
        members = data["planets"].loc[data["planets"]["cluster_id"] == cluster_id]
        records, page_info = _pagination(members, *pagination)
        return jsonify({"profile": profile, "members": {"pagination": page_info, "records": records}})

    @app.get("/api/discovery/summary")
    def discovery_summary():
        planets = data["planets"]
        all_counts = planets["discoverymethod"].value_counts(dropna=False).sort_index()
        by_cluster: list[dict[str, Any]] = []
        assigned = planets.loc[planets["cluster_id"].notna()]
        for cluster_id in data["cluster_ids"]:
            members = assigned.loc[assigned["cluster_id"] == cluster_id]
            method_counts = members["discoverymethod"].value_counts(dropna=False).sort_index()
            methods = []
            for method, count in method_counts.items():
                methods.append({
                    "discovery_method": None if pd.isna(method) else str(method),
                    "planet_count": int(count),
                    "percent_within_cluster": float(count / len(members) * 100.0),
                })
            by_cluster.append({
                "cluster_id": cluster_id,
                "planet_count": len(members),
                "discovery_methods": methods,
            })
        return jsonify({
            "overall_counts": {str(key): int(value) for key, value in all_counts.items()},
            "primary_cluster_composition": by_cluster,
            "interpretation_caveat": (
                "Percentages describe this confirmed-planet catalogue and its saved exploratory assignments. "
                "Discovery methods have differing sensitivities and survey selection effects; associations are not causal."
            ),
        })

    def selected_discovery_methods() -> tuple[list[str] | None, Any | None]:
        """Read exact method filters from repeated `method` or comma-separated `methods` parameters."""
        repeated = request.args.getlist("method")
        comma_separated = request.args.get("methods")
        if repeated and comma_separated is not None:
            return None, _query_error("Use either repeated 'method' parameters or one 'methods' parameter, not both.")
        if comma_separated is not None:
            requested = comma_separated.split(",")
        else:
            requested = repeated
        if not requested:
            return list(data["discovery_lens"]["methods"]), None
        if any(method == "" for method in requested):
            return None, _query_error("Discovery-method filters must be exact nonempty category names.")
        known = set(data["discovery_lens"]["methods"])
        unknown = [method for method in requested if method not in known]
        if unknown:
            return None, _query_error(
                f"Unknown discovery method(s): {unknown}. Use an exact catalogue category name."
            )
        return list(dict.fromkeys(requested)), None

    @app.get("/api/discovery/overview")
    def discovery_lens_overview():
        lens = data["discovery_lens"]
        report = lens["report"]
        dataset = report["dataset"]
        return jsonify({
            "source": report["source"],
            "snapshot_date": report["source"]["snapshot_date"],
            "total_planet_records": dataset["planet_records"],
            "number_of_discovery_methods": dataset["discovery_methods"],
            "number_of_discovery_years": dataset["discovery_years_with_records"],
            "number_of_facilities": dataset["facilities"],
            "number_of_unique_host_systems": dataset["unique_host_systems"],
            "first_discovery_year": dataset["first_discovery_year"],
            "last_discovery_year": dataset["last_discovery_year"],
            "methods": report["methods"],
            "limitations": [
                "Catalogue counts describe confirmed-planet records, not occurrence rates in the universe.",
                "Discovery methods have different observational sensitivities and catalogue selection effects.",
                "Host counts may overlap between methods and are not summed to estimate unique systems.",
                "The same host can contribute multiple planets; observations within a host are not independent.",
                "Small method groups are retained and should be interpreted cautiously.",
            ],
        })

    @app.get("/api/discovery/timeline")
    def discovery_lens_timeline():
        methods, error = selected_discovery_methods()
        if error:
            return error
        timeline = data["discovery_lens"]["timeline"]
        years = []
        for year in range(1992, 2027):
            annual = timeline.loc[timeline["discovery_year"] == year]
            annual_total = int(annual["year_total"].iloc[0]) if not annual.empty else 0
            selected_rows = annual.loc[annual["discovery_method"].isin(methods)]
            method_counts = [
                {
                    "discovery_method": str(row["discovery_method"]),
                    "planet_count": int(row["planet_count"]),
                    "within_year_percentage": float(row["within_year_percentage"]),
                }
                for row in selected_rows.to_dict(orient="records")
            ]
            years.append({
                "year": year,
                "total_planet_records": annual_total,
                "selected_method_planet_records": sum(item["planet_count"] for item in method_counts),
                "methods": method_counts,
                "is_partial_year": year == 2026,
            })
        return jsonify({
            "snapshot_date": data["discovery_lens"]["report"]["source"]["snapshot_date"],
            "selected_methods": methods,
            "partial_year": {
                "year": 2026,
                "is_partial": True,
                "as_of_date": data["discovery_lens"]["report"]["source"]["snapshot_date"],
                "note": "2026 is a partial-year catalogue snapshot, not a complete calendar year.",
            },
            "interpretation_note": (
                "Counts follow the catalogue's recorded discovery years. Publication, confirmation, survey coverage, "
                "curation, and reporting practices also shape this timeline."
            ),
            "years": years,
        })

    @app.get("/api/discovery/distributions")
    def discovery_lens_distributions():
        property_name = request.args.get("property")
        property_definitions = {
            "pl_rade": {"label": "Planet radius", "unit": "Earth radii", "axis_scale": "log"},
            "pl_orbper": {"label": "Orbital period", "unit": "days", "axis_scale": "log"},
            "pl_eqt": {"label": "Equilibrium temperature", "unit": "K", "axis_scale": "linear"},
            "pl_orbeccen": {"label": "Orbital eccentricity", "unit": "dimensionless", "axis_scale": "linear"},
        }
        if property_name not in property_definitions:
            return _query_error("'property' must be one of pl_rade, pl_orbper, pl_eqt, or pl_orbeccen.")
        methods, error = selected_discovery_methods()
        if error:
            return error
        lens = data["discovery_lens"]
        summary = lens["property_summary"]
        values = lens["property_values"]
        distributions = []
        for method in methods:
            matches = summary.loc[
                (summary["discovery_method"] == method) & (summary["property"] == property_name)
            ]
            if matches.empty:
                continue
            row = matches.iloc[0]
            sample = values.loc[
                (values["discovery_method"] == method) & (values["property"] == property_name),
                ["pl_name", "hostname", "value", "error_1", "error_2", "uncertainty_available"],
            ]
            measured_count = int(row["measured_count"])
            warning = measured_count < 5
            distributions.append({
                "discovery_method": method,
                "total_planet_records": int(row["total_planet_records"]),
                "error_1_field": str(row["error_1_field"]),
                "error_2_field": str(row["error_2_field"]),
                "measured_count": measured_count,
                "missing_count": int(row["missing_count"]),
                "zero_measurement_count": int(row["zero_measurement_count"]),
                "measurement_availability_pct": float(row["measurement_availability_pct"]),
                "median": _json_scalar(row["median"]),
                "q1": _json_scalar(row["q1"]),
                "q3": _json_scalar(row["q3"]),
                "minimum": _json_scalar(row["minimum"]),
                "maximum": _json_scalar(row["maximum"]),
                "unique_hosts_measured": int(row["unique_hosts_measured"]),
                "uncertainty_count": int(row["uncertainty_count"]),
                "error_1_count": int(row["error_1_count"]),
                "error_2_count": int(row["error_2_count"]),
                "uncertainty_availability_pct": float(row["uncertainty_availability_pct"]),
                "sample_size_warning": {
                    "is_small": warning,
                    "message": (
                        "Fewer than five measured observations; raw values are shown and the summary is descriptive only."
                        if warning else None
                    ),
                },
                "observations": _records(sample),
            })
        return jsonify({
            "property": property_name,
            **property_definitions[property_name],
            "selected_methods": methods,
            "host_independence_note": (
                "Planets from one host can appear together; these catalogue observations are not independent "
                "statistical replicates."
            ),
            "uncertainty_note": lens["report"]["uncertainty_note"],
            "distributions": distributions,
        })

    @app.get("/api/discovery/facilities")
    def discovery_lens_facilities():
        methods, error = selected_discovery_methods()
        if error:
            return error
        lens = data["discovery_lens"]
        table = lens["facility_counts"]
        selected = table.loc[table["discovery_method"].isin(methods)]
        if request.args.getlist("method") or request.args.get("methods") is not None:
            denominator = int(
                lens["property_summary"].loc[
                    (lens["property_summary"]["property"] == "pl_rade")
                    & lens["property_summary"]["discovery_method"].isin(methods),
                    "total_planet_records",
                ].sum()
            )
            scoped_counts = selected.groupby("facility", sort=False)["planet_count"].sum()
            records = [
                {
                    "facility": str(facility),
                    "planet_count": int(count),
                    "percentage": float(count / denominator * 100) if denominator else 0.0,
                }
                for facility, count in scoped_counts.items()
            ]
            missing_facility_records = sum(
                int(item.get("records_without_facility", 0))
                for item in lens["report"]["methods"] if item["discovery_method"] in methods
            )
            scope = methods
        else:
            denominator = int(lens["report"]["dataset"]["planet_records"])
            scoped_counts = selected.groupby("facility", sort=False)["planet_count"].sum()
            records = [
                {
                    "facility": str(facility),
                    "planet_count": int(count),
                    "percentage": float(count / denominator * 100) if denominator else 0.0,
                }
                for facility, count in scoped_counts.items()
            ]
            missing_facility_records = int(lens["report"]["dataset"]["records_without_facility"])
            scope = "catalogue"
        records.sort(key=lambda item: (-item["planet_count"], item["facility"]))
        return jsonify({
            "scope": scope,
            "denominator_planet_records": denominator,
            "records_without_facility": missing_facility_records,
            "facility_count": len(records),
            "facilities": records,
            "interpretation_note": (
                "Counts represent catalogue planet records associated with a facility. They do not measure "
                "independent surveys, independent detections, or unique host systems."
            ),
        })

    @app.get("/api/model")
    def model_metadata():
        model = data["registry"]["primary_model"]
        comparisons = data["registry"]["comparison_configurations"]
        return jsonify({
            "model": {
                "model_id": model["model_id"],
                "version": model["version"],
                "status": model["status"],
                "experiment": model["experiment"],
                "k": model["k"],
                "ordered_features": model["ordered_features"],
                "standardized_input_columns": model["standardized_input_columns"],
                "feature_definitions": model["feature_definitions"],
                "cohort_size": model["cohort_size"],
                "random_seed": model["random_seed"],
                "kmeans_configuration": model["kmeans_configuration"],
                "dataset": model["dataset"],
                "evaluation": model["evaluation"],
                "selection_rationale": model["selection_rationale"],
                "interpretation": model["interpretation"],
                "limitations": model["limitations"],
            },
            "comparison_configurations": [
                {
                    "experiment": item["experiment"],
                    "k": item["k"],
                    "cohort_size": item["cohort_size"],
                    "silhouette": item["silhouette"],
                    "random_seed": item["random_seed"],
                    "feature_columns_passed_to_kmeans": item["feature_columns_passed_to_kmeans"],
                }
                for item in comparisons
            ],
        })

    @app.get("/api/validation/summary")
    def validation_summary():
        validation = data["validation_report"]
        clustering = data["clustering_report"]
        silhouette = next(
            row for row in validation["silhouette_cluster_summary"]
            if row["experiment"] == "with_temp" and row["cluster_id"] == "ALL"
        )
        stability = next(
            row for row in clustering["stability"]["summary"]
            if row["experiment"] == "with_temp" and int(row["k"]) == 4
        )
        association = validation["discovery_method_tests"]["with_temp"]
        sensitivity = validation["temperature_comparison"]
        primary_cluster_silhouettes = [
            {
                "cluster_id": int(row["cluster_id"]),
                "planet_count": int(row["planet_count"]),
                "mean_silhouette": float(row["mean_silhouette"]),
                "median_silhouette": float(row["median_silhouette"]),
                "negative_silhouette_count": int(row["negative_silhouette_count"]),
                "negative_silhouette_percent": float(row["negative_silhouette_percent"]),
            }
            for row in validation["silhouette_cluster_summary"]
            if row["experiment"] == "with_temp" and row["cluster_id"] != "ALL"
        ]
        primary_separation = [
            row for row in validation["cluster_separation"]
            if row["experiment"] == "with_temp" and int(row["k"]) == 4
        ]
        centroid_distances = [
            {
                "cluster_a": int(row["cluster_a"]),
                "cluster_b": int(row["cluster_b"]),
                "distance": float(row["distance_or_overlap"]),
            }
            for row in primary_separation
            if row["diagnostic"] == "standardized_centroid_distance"
        ]
        closest_centroids = min(centroid_distances, key=lambda row: row["distance"])
        eccentricity_overlap = next(
            row for row in primary_separation
            if row["diagnostic"] == "binned_univariate_overlap_coefficient"
            and row["feature"] == "pl_orbeccen"
            and {int(row["cluster_a"]), int(row["cluster_b"])} == {1, 2}
        )
        no_temperature_stability = next(
            row for row in clustering["stability"]["summary"]
            if row["experiment"] == "without_temp" and int(row["k"]) == 4
        )
        no_temperature_metrics = next(
            row for row in clustering["primary_metrics"]
            if row["experiment"] == "without_temp" and int(row["k"]) == 4
        )
        no_temperature_profiles = [
            {
                "cluster_id": int(row["cluster_id"]),
                "planet_count": int(row["planet_count"]),
                "planet_percent": float(row["planet_percent"]),
                "feature": row["feature"],
                "units": row["units"],
                "q1": float(row["q1"]),
                "median": float(row["median"]),
                "q3": float(row["q3"]),
                "iqr": float(row["iqr"]),
            }
            for row in validation["cluster_distribution"]
            if row["experiment"] == "without_temp"
        ]
        return jsonify({
            "model_id": data["registry"]["primary_model"]["model_id"],
            "cohort_size": int(silhouette["planet_count"]),
            "silhouette": {
                "metric": "Euclidean silhouette in the saved standardized input space",
                "mean": float(silhouette["mean_silhouette"]),
                "median": float(silhouette["median_silhouette"]),
            },
            "stability": {
                "metric": "ARI versus seed-42 assignments across alternate initialization seeds; primary self-comparison omitted",
                "seed_count": int(stability["seed_count"]),
                "comparison_seed_count": int(stability["ari_comparison_seed_count"]),
                "ari_mean": float(stability["ari_mean_excluding_primary_self_comparison"]),
                "ari_sample_sd": float(stability["ari_std_excluding_primary_self_comparison"]),
            },
            "negative_silhouette": {
                "count": int(silhouette["negative_silhouette_count"]),
                "percent": float(silhouette["negative_silhouette_percent"]),
            },
            "cluster_silhouette": primary_cluster_silhouettes,
            "cluster_separation": {
                "centroid_distance_metric": "Euclidean distance between centroids in the exact standardized four-feature K-means input space",
                "centroid_distances": centroid_distances,
                "closest_centroid_pair": closest_centroids,
                "eccentricity_overlap": {
                    "cluster_a": int(eccentricity_overlap["cluster_a"]),
                    "cluster_b": int(eccentricity_overlap["cluster_b"]),
                    "coefficient": float(eccentricity_overlap["distance_or_overlap"]),
                    "method": eccentricity_overlap["method"],
                    "units": eccentricity_overlap["units"],
                },
            },
            "feature_configuration_sensitivity": {
                "comparison": "with-temperature K=4 versus no-temperature K=4, same cohort",
                "adjusted_rand_index": float(sensitivity["adjusted_rand_index"]),
                "changed_planet_count": int(sensitivity["changed_planet_count"]),
                "changed_planet_percent": float(sensitivity["changed_planet_percent"]),
                "interpretation": sensitivity["interpretation"],
                "matched_clusters_by_maximum_membership_overlap": sensitivity[
                    "matched_clusters_by_maximum_membership_overlap"
                ],
                "without_temperature": {
                    "features": 3,
                    "k": 4,
                    "silhouette": float(no_temperature_metrics["silhouette_score"]),
                    "stability_ari_mean": float(
                        no_temperature_stability["ari_mean_excluding_primary_self_comparison"]
                    ),
                    "profiles": no_temperature_profiles,
                },
            },
            "discovery_method_association": {
                "method": validation["discovery_method_tests"]["method"],
                "sample_size": int(association["sample_size"]),
                "chi_square": float(association["chi_square_statistic"]),
                "degrees_of_freedom": int(association["degrees_of_freedom"]),
                "p_value_display": association["p_value_display"],
                "cramers_v": float(association["cramers_v"]),
                "expected_cells_below_5": int(association["expected_cells_below_5"]),
                "expected_cell_count": int(association["expected_cell_count"]),
                "common_expected_count_heuristic_met": bool(association["common_expected_count_heuristic_met"]),
                "caveat": validation["discovery_method_tests"]["caveat"],
            },
            "scientific_caveats": validation["limitations"],
        })

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def frontend(path: str):
        """Serve the built single-page app while preserving JSON API failures."""
        if path.startswith("api/"):
            return jsonify({"error": {"code": "not_found", "message": "Endpoint or resource was not found."}}), 404
        if not frontend_dist.is_dir():
            return jsonify({"error": {"code": "frontend_not_built", "message": "Build the frontend before serving it from Flask."}}), 503
        asset = frontend_dist / path
        if path and asset.is_file():
            return send_from_directory(frontend_dist, path)
        return send_from_directory(frontend_dist, "index.html")

    return app


app = create_app()
