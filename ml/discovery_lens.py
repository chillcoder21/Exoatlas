"""Offline descriptive summaries for the frozen confirmed-planet catalogue."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPLICATION_DATA = Path("data/processed/planets_application.csv")
RAW_SOURCE = Path("data/raw/PSCompPars_2026.10.30_13.47.46.csv")
SNAPSHOT_DATE = "2026-10-30"
EXPECTED_RECORDS = 6_451
EXPECTED_HOSTS = 4_847
EXPECTED_FACILITIES = 73
EXPECTED_METHOD_COUNTS = {
    "Transit": 4_785,
    "Radial Velocity": 1_204,
    "Microlensing": 292,
    "Imaging": 98,
    "Transit Timing Variations": 29,
    "Eclipse Timing Variations": 17,
    "Orbital Brightness Modulation": 9,
    "Pulsar Timing": 8,
    "Astrometry": 6,
    "Pulsation Timing Variations": 2,
    "Disk Kinematics": 1,
}
METHODS = tuple(EXPECTED_METHOD_COUNTS)
PROPERTIES = {
    "pl_rade": {
        "label": "Planet radius",
        "unit": "Earth radii",
        "error_1": "pl_radeerr1",
        "error_2": "pl_radeerr2",
        "axis_scale": "log",
    },
    "pl_orbper": {
        "label": "Orbital period",
        "unit": "days",
        "error_1": "pl_orbpererr1",
        "error_2": "pl_orbpererr2",
        "axis_scale": "log",
    },
    "pl_eqt": {
        "label": "Equilibrium temperature",
        "unit": "K",
        "error_1": "pl_eqterr1",
        "error_2": "pl_eqterr2",
        "axis_scale": "linear",
    },
    "pl_orbeccen": {
        "label": "Orbital eccentricity",
        "unit": "dimensionless",
        "error_1": "pl_orbeccenerr1",
        "error_2": "pl_orbeccenerr2",
        "axis_scale": "linear",
    },
}
YEARS = tuple(range(1992, 2027))
OUTPUTS = {
    "timeline": Path("data/processed/discovery_method_timeline.csv"),
    "property_summary": Path("data/processed/discovery_method_property_summary.csv"),
    "facility_counts": Path("data/processed/discovery_facility_counts.csv"),
    "property_values": Path("data/processed/discovery_property_values.csv"),
    "report": Path("data/metadata/discovery_lens_report.json"),
}
APPLICATION_REPORT = Path("data/metadata/application_data_report.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def frozen_artifact_hashes(root: Path) -> dict[str, str]:
    """Hash pre-existing scientific inputs and outputs that this feature must preserve."""
    fixed = [
        APPLICATION_DATA,
        Path("data/processed/planets_master.csv"),
        Path("data/processed/clustering_features_with_temp.csv"),
        Path("data/processed/clustering_features_without_temp.csv"),
        Path("data/processed/planet_outlier_diagnostics.csv"),
        Path("data/metadata/application_data_report.json"),
        Path("data/metadata/cluster_profiles.json"),
        Path("data/metadata/preprocessing_report.json"),
        Path("data/metadata/preprocessing_report.md"),
        Path("data/metadata/outlier_analysis_report.json"),
        Path("data/metadata/outlier_analysis_report.md"),
        Path("data/metadata/dataset_audit.json"),
        Path("data/metadata/dataset_audit.md"),
    ]
    paths = [root / item for item in fixed if (root / item).is_file()]
    for relative_dir in (
        Path("data/raw"),
        Path("artifacts/preprocessing"),
        Path("artifacts/clustering"),
        Path("data/cluster_experiments"),
        Path("data/cluster_validation"),
    ):
        directory = root / relative_dir
        if directory.is_dir():
            paths.extend(path for path in directory.rglob("*") if path.is_file())
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(set(paths))
    }


def verify_raw_source(root: Path, application: pd.DataFrame) -> dict[str, Any]:
    """Check the pinned raw snapshot and confirm its 84 fields remain in the app table."""
    raw_path = root / RAW_SOURCE
    report_path = root / APPLICATION_REPORT
    if not raw_path.is_file():
        raise FileNotFoundError(f"Expected NASA source CSV at {RAW_SOURCE.as_posix()}")
    if not report_path.is_file():
        raise FileNotFoundError(f"Expected application-data provenance report at {APPLICATION_REPORT.as_posix()}")
    prior_report = json.loads(report_path.read_text(encoding="utf-8"))
    provenance = prior_report.get("dataset", {})
    raw_hash = sha256_file(raw_path)
    if provenance.get("source_sha256") != raw_hash:
        raise ValueError("Raw NASA source checksum differs from the approved application-data provenance report.")
    if provenance.get("source_snapshot_date") != SNAPSHOT_DATE:
        raise ValueError("Raw NASA source snapshot date differs from the Discovery Lens snapshot metadata.")
    with raw_path.open("r", encoding="utf-8-sig", newline="") as source_file:
        header = [next(source_file, "") for _ in range(4)]
    download_timestamp = next(
        (line.lstrip("# ").strip() for line in header if line.lstrip().startswith("#") and "2026" in line),
        None,
    )
    if download_timestamp != "Fri Oct 30 13:47:46 2026":
        raise ValueError("Raw NASA source download timestamp differs from the named snapshot.")

    raw = pd.read_csv(raw_path, comment="#", encoding="utf-8-sig", low_memory=False)
    validate_application_data(raw)
    if len(raw) != provenance.get("source_records") or len(raw.columns) != provenance.get("source_columns"):
        raise ValueError("Raw NASA source row or column count differs from its approved provenance report.")
    if len(application) != len(raw):
        raise ValueError("Prepared application dataset and raw NASA source have different row counts.")
    mismatched_columns = []
    for column in raw.columns:
        source_values = raw[column]
        prepared_values = application[column]
        if pd.api.types.is_numeric_dtype(source_values) and pd.api.types.is_numeric_dtype(prepared_values):
            matches = np.array_equal(
                pd.to_numeric(source_values, errors="coerce").to_numpy(dtype=float),
                pd.to_numeric(prepared_values, errors="coerce").to_numpy(dtype=float),
                equal_nan=True,
            )
        else:
            source_text = source_values.astype("string").fillna("<MISSING>")
            prepared_text = prepared_values.astype("string").fillna("<MISSING>")
            matches = source_text.equals(prepared_text)
        if not matches:
            mismatched_columns.append(column)
    if mismatched_columns:
        raise ValueError(f"Prepared application rows differ from raw source fields: {mismatched_columns}")
    return {
        "raw_source_sha256": raw_hash,
        "download_date": SNAPSHOT_DATE,
        "download_timestamp": download_timestamp,
        "raw_source_records": int(len(raw)),
        "raw_source_columns": int(len(raw.columns)),
        "raw_source_base_columns_match_application": True,
    }


def validate_application_data(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize the prepared data without changing the source file."""
    required = {
        "pl_name",
        "hostname",
        "discoverymethod",
        "disc_year",
        "disc_facility",
        *PROPERTIES,
        *(name for item in PROPERTIES.values() for name in (item["error_1"], item["error_2"])),
    }
    missing_columns = sorted(required.difference(frame.columns))
    if missing_columns:
        raise ValueError(f"Application dataset is missing required columns: {missing_columns}")
    data = frame.copy()

    for column in ("pl_name", "hostname", "discoverymethod"):
        values = data[column].astype("string")
        if values.isna().any() or values.str.strip().eq("").any():
            raise ValueError(f"Application dataset contains missing or blank {column} values.")
        data[column] = values

    if data["pl_name"].duplicated().any():
        raise ValueError("Application dataset contains duplicate pl_name planet identifiers.")
    if len(data) != EXPECTED_RECORDS:
        raise ValueError(f"Expected {EXPECTED_RECORDS} application records; found {len(data)}.")
    if data["hostname"].nunique(dropna=False) != EXPECTED_HOSTS:
        raise ValueError(f"Expected {EXPECTED_HOSTS} valid unique host identifiers.")
    if data["disc_facility"].dropna().astype("string").str.strip().eq("").any():
        raise ValueError("Application dataset contains blank nonmissing facility names.")
    if data["disc_facility"].nunique(dropna=True) != EXPECTED_FACILITIES:
        raise ValueError(f"Expected {EXPECTED_FACILITIES} distinct nonmissing facilities.")

    methods = data["discoverymethod"].value_counts().to_dict()
    if set(methods) != set(METHODS):
        unexpected = sorted(set(methods).symmetric_difference(METHODS))
        raise ValueError(f"Discovery method categories changed unexpectedly: {unexpected}")
    if methods != EXPECTED_METHOD_COUNTS:
        raise ValueError("Discovery method counts do not match the frozen 6,451-record snapshot.")

    years = pd.to_numeric(data["disc_year"], errors="coerce")
    if years.isna().any() or not np.isfinite(years.to_numpy(dtype=float)).all():
        raise ValueError("Discovery years must be populated finite numbers.")
    if not np.equal(years.to_numpy(dtype=float), np.floor(years.to_numpy(dtype=float))).all():
        raise ValueError("Discovery years must be integer calendar years.")
    data["disc_year"] = years.astype(int)
    expected_years = set(YEARS) - {1993}
    if set(data["disc_year"].unique()) != expected_years:
        raise ValueError("Discovery years differ from the expected 1992–2026 snapshot (with 1993 empty).")

    numeric_columns = [*PROPERTIES]
    numeric_columns.extend(
        name for item in PROPERTIES.values() for name in (item["error_1"], item["error_2"])
    )
    for column in numeric_columns:
        parsed = pd.to_numeric(data[column], errors="coerce")
        invalid = data[column].notna() & parsed.isna()
        if invalid.any() or np.isinf(parsed.dropna().to_numpy(dtype=float)).any():
            raise ValueError(f"Column {column} contains nonnumeric or nonfinite measurements.")
        data[column] = parsed
    if int(data["pl_orbeccen"].eq(0).sum()) != 3_156:
        raise ValueError("The frozen eccentricity field should retain its 3,156 measured zero values.")
    return data


def analyze_discovery_lens(frame: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Build deterministic descriptive tables from the complete application catalogue."""
    data = validate_application_data(frame)
    total = len(data)

    method_rows: list[dict[str, Any]] = []
    for method in METHODS:
        members = data.loc[data["discoverymethod"] == method]
        method_rows.append({
            "discovery_method": method,
            "planet_count": int(len(members)),
            "catalogue_percentage": float(len(members) / total * 100),
            "unique_host_count": int(members["hostname"].nunique()),
            "facility_count": int(members["disc_facility"].nunique(dropna=True)),
            "records_without_facility": int(members["disc_facility"].isna().sum()),
            "first_discovery_year": int(members["disc_year"].min()),
            "last_discovery_year": int(members["disc_year"].max()),
        })
    method_summary = pd.DataFrame(method_rows)

    count_lookup = data.groupby(["disc_year", "discoverymethod"], sort=False).size()
    year_totals = data.groupby("disc_year", sort=False).size()
    timeline_rows = []
    for year in YEARS:
        year_total = int(year_totals.get(year, 0))
        for method in METHODS:
            count = int(count_lookup.get((year, method), 0))
            timeline_rows.append({
                "discovery_year": year,
                "discovery_method": method,
                "planet_count": count,
                "year_total": year_total,
                "within_year_percentage": float(count / year_total * 100) if year_total else 0.0,
                "is_partial_year": year == 2026,
            })
    timeline = pd.DataFrame(timeline_rows)
    if int(timeline.drop_duplicates("discovery_year")["year_total"].sum()) != total:
        raise ValueError("Timeline annual totals do not reconcile with the application record count.")
    if int(timeline["planet_count"].sum()) != total:
        raise ValueError("Timeline method totals do not reconcile with the application record count.")
    if int(timeline.loc[timeline["discovery_year"] == 1993, "planet_count"].sum()) != 0:
        raise ValueError("The expected zero-record year 1993 is not empty.")

    property_rows: list[dict[str, Any]] = []
    value_rows: list[dict[str, Any]] = []
    for method in METHODS:
        members = data.loc[data["discoverymethod"] == method]
        for key, definition in PROPERTIES.items():
            measured = members.loc[members[key].notna()]
            values = measured[key].astype(float)
            error_1 = measured[definition["error_1"]]
            error_2 = measured[definition["error_2"]]
            paired_uncertainties = error_1.notna() & error_2.notna()
            n = int(len(measured))
            property_rows.append({
                "discovery_method": method,
                "property": key,
                "property_label": definition["label"],
                "unit": definition["unit"],
                "error_1_field": definition["error_1"],
                "error_2_field": definition["error_2"],
                "total_planet_records": int(len(members)),
                "measured_count": n,
                "missing_count": int(len(members) - n),
                "zero_measurement_count": int(values.eq(0).sum()),
                "measurement_availability_pct": float(n / len(members) * 100) if len(members) else 0.0,
                "median": float(values.median()) if n else None,
                "q1": float(values.quantile(0.25)) if n else None,
                "q3": float(values.quantile(0.75)) if n else None,
                "minimum": float(values.min()) if n else None,
                "maximum": float(values.max()) if n else None,
                "unique_hosts_measured": int(measured["hostname"].nunique()),
                "uncertainty_count": int(paired_uncertainties.sum()),
                "error_1_count": int(error_1.notna().sum()),
                "error_2_count": int(error_2.notna().sum()),
                "uncertainty_availability_pct": float(paired_uncertainties.sum() / n * 100) if n else 0.0,
                "sample_size_is_small": n < 5,
            })
            for row_index, record in measured.iterrows():
                value_rows.append({
                    "pl_name": str(record["pl_name"]),
                    "hostname": str(record["hostname"]),
                    "discovery_method": method,
                    "property": key,
                    "value": float(record[key]),
                    "error_1": float(record[definition["error_1"]])
                    if pd.notna(record[definition["error_1"]]) else None,
                    "error_2": float(record[definition["error_2"]])
                    if pd.notna(record[definition["error_2"]]) else None,
                    "uncertainty_available": bool(
                        pd.notna(record[definition["error_1"]])
                        and pd.notna(record[definition["error_2"]])
                    ),
                })
    property_summary = pd.DataFrame(property_rows)
    property_values = pd.DataFrame(value_rows)

    facility_counts = (
        data.dropna(subset=["disc_facility"])
        .groupby(["disc_facility", "discoverymethod"], sort=True)
        .size()
        .rename("planet_count")
        .reset_index()
        .rename(columns={"disc_facility": "facility", "discoverymethod": "discovery_method"})
    )
    method_denominators = method_summary.set_index("discovery_method")["planet_count"]
    facility_counts["method_denominator"] = facility_counts["discovery_method"].map(method_denominators).astype(int)
    facility_counts["catalogue_denominator"] = total
    facility_counts["method_percentage"] = (
        facility_counts["planet_count"] / facility_counts["method_denominator"] * 100
    )
    facility_counts["catalogue_percentage"] = facility_counts["planet_count"] / total * 100

    method_summary_records = method_summary.to_dict(orient="records")
    report = {
        "feature": "ExoAtlas Discovery Lens",
        "source": {
            "catalogue": "NASA Exoplanet Archive, Confirmed Planets (PSCompPars)",
            "source_file": RAW_SOURCE.as_posix(),
            "prepared_application_dataset": APPLICATION_DATA.as_posix(),
            "snapshot_date": SNAPSHOT_DATE,
            "raw_source_present": True,
            "raw_source_sha256": None,
            "raw_source_records": None,
            "raw_source_columns": None,
            "raw_source_base_columns_match_application": False,
            "note": "The named raw CSV was checksum-verified against the existing application-data provenance report; all original source columns match the prepared application table in row order.",
        },
        "uncertainty_note": (
            "Asymmetric catalogue values remain in their original err1 and err2 fields and signs. "
            "They are not relabelled as lower/upper or converted to symmetric uncertainties."
        ),
        "dataset": {
            "planet_records": total,
            "unique_planet_identifiers": int(data["pl_name"].nunique()),
            "unique_host_systems": int(data["hostname"].nunique()),
            "multi_planet_hosts": int((data.groupby("hostname").size() > 1).sum()),
            "records_in_multi_planet_hosts": int(data.groupby("hostname").size().loc[lambda counts: counts > 1].sum()),
            "maximum_planets_per_host": int(data.groupby("hostname").size().max()),
            "discovery_methods": len(METHODS),
            "discovery_years_with_records": int(data["disc_year"].nunique()),
            "first_discovery_year": int(data["disc_year"].min()),
            "last_discovery_year": int(data["disc_year"].max()),
            "facilities": int(data["disc_facility"].nunique(dropna=True)),
            "records_without_facility": int(data["disc_facility"].isna().sum()),
        },
        "methods": method_summary_records,
        "property_missingness": {
            key: {
                "missing_count": int(data[key].isna().sum()),
                "measured_count": int(data[key].notna().sum()),
                "unit": definition["unit"],
                "zero_measurement_count": int(data[key].eq(0).sum()),
            }
            for key, definition in PROPERTIES.items()
        },
        "validation_checks": {
            "unique_planet_identifiers": True,
            "valid_host_identifiers": True,
            "expected_method_categories_and_counts": True,
            "expected_discovery_year_range_and_empty_1993": True,
            "method_counts_reconcile_to_source": int(method_summary["planet_count"].sum()) == total,
            "timeline_totals_reconcile_to_source": int(timeline["planet_count"].sum()) == total,
            "all_catalogue_records_retained": total == EXPECTED_RECORDS,
        },
        "method_counts": {str(row["discovery_method"]): int(row["planet_count"]) for row in method_summary_records},
        "outputs": {},
        "output_manifest_note": "SHA-256 covers generated CSV outputs; this report is excluded to avoid a self-referential hash.",
    }
    return {
        "timeline": timeline,
        "property_summary": property_summary,
        "facility_counts": facility_counts,
        "property_values": property_values,
    }, report


def run_discovery_lens(root: Path = PROJECT_ROOT, output_root: Path | None = None) -> dict[str, Any]:
    """Generate the offline tables and a deterministic provenance report."""
    root = Path(root)
    target_root = Path(output_root) if output_root is not None else root
    frozen_before = frozen_artifact_hashes(root)
    source_path = root / APPLICATION_DATA
    frame = pd.read_csv(source_path, low_memory=False)
    source_verification = verify_raw_source(root, frame)
    tables, report = analyze_discovery_lens(frame)
    report["source"]["prepared_application_sha256"] = sha256_file(source_path)
    report["source"].update(source_verification)

    for key, relative_path in OUTPUTS.items():
        if key == "report":
            continue
        path = target_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tables[key].to_csv(path, index=False, lineterminator="\n", float_format="%.15g")
        report["outputs"][relative_path.as_posix()] = sha256_file(path)

    frozen_after = frozen_artifact_hashes(root)
    if frozen_before != frozen_after:
        changed = sorted(name for name in set(frozen_before) | set(frozen_after) if frozen_before.get(name) != frozen_after.get(name))
        raise RuntimeError(f"Frozen scientific inputs or outputs changed during Discovery Lens generation: {changed}")
    report["frozen_artifacts_sha256"] = frozen_before
    report_path = target_root / OUTPUTS["report"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="Project root containing the prepared application CSV.")
    parser.add_argument("--output-root", type=Path, default=None, help="Optional destination root for derived outputs.")
    args = parser.parse_args()
    report = run_discovery_lens(args.root, args.output_root)
    print(json.dumps({"planet_records": report["dataset"]["planet_records"], "outputs": report["outputs"]}, indent=2))


if __name__ == "__main__":
    main()
