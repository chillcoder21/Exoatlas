"""Run the approved preprocessing pipeline and write reproducible artifacts."""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn

from .data_audit import PRE_MOVE_SHA256, SOURCE_PATH, sha256_file
from .preprocessing import (
    EXPECTED_PRIMARY_RECORDS,
    EXPECTED_WITHOUT_TEMPERATURE_RECORDS,
    FOUR_FEATURES,
    SCALED_FEATURES,
    SOURCE_COLUMNS,
    SOURCE_RECORDS,
    THREE_FEATURES,
    TRANSFORMED_FEATURES,
    PreprocessingResult,
    iqr_extreme_investigation,
    load_source_dataset,
    prepare_frames,
)


ROOT = Path(__file__).resolve().parents[1]
MASTER_RELATIVE_PATH = Path("data/processed/planets_master.csv")
WITH_TEMP_RELATIVE_PATH = Path("data/processed/clustering_features_with_temp.csv")
WITHOUT_TEMP_RELATIVE_PATH = Path("data/processed/clustering_features_without_temp.csv")
SCALER_WITH_TEMP_RELATIVE_PATH = Path("artifacts/preprocessing/scaler_with_temp.joblib")
SCALER_WITHOUT_TEMP_RELATIVE_PATH = Path("artifacts/preprocessing/scaler_without_temp.joblib")
REPORT_JSON_RELATIVE_PATH = Path("data/metadata/preprocessing_report.json")
REPORT_MARKDOWN_RELATIVE_PATH = Path("data/metadata/preprocessing_report.md")


def _file_hashes(root: Path, relative_paths: list[Path]) -> dict[str, str]:
    return {
        path.as_posix(): sha256_file(root / path)
        for path in relative_paths
    }


def _scaler_summary(scaler: Any, feature_names: tuple[str, ...]) -> dict[str, Any]:
    return {
        "class": "sklearn.preprocessing.StandardScaler",
        "feature_order": list(feature_names),
        "mean": [float(value) for value in scaler.mean_],
        "variance": [float(value) for value in scaler.var_],
        "scale": [float(value) for value in scaler.scale_],
        "fit_records": int(scaler.n_samples_seen_),
        "standard_deviation_convention": "population (ddof=0), as used by StandardScaler",
    }


def _report_data(
    result: PreprocessingResult,
    *,
    source_path: Path,
    source_sha_before: str,
    source_sha_after: str,
    root: Path,
) -> dict[str, Any]:
    with_features = tuple(
        TRANSFORMED_FEATURES[name] for name in FOUR_FEATURES
    )
    without_features = tuple(
        TRANSFORMED_FEATURES[name] for name in THREE_FEATURES
    )
    report_files = [
        MASTER_RELATIVE_PATH,
        WITH_TEMP_RELATIVE_PATH,
        WITHOUT_TEMP_RELATIVE_PATH,
        SCALER_WITH_TEMP_RELATIVE_PATH,
        SCALER_WITHOUT_TEMP_RELATIVE_PATH,
    ]
    return {
        "dataset": {
            "name": source_path.name,
            "snapshot_date": "2026-10-30",
            "source_path": "data/raw/PSCompPars_2026.10.30_13.47.46.csv",
            "source_sha256_expected": PRE_MOVE_SHA256,
            "source_sha256_before": source_sha_before,
            "source_sha256_after": source_sha_after,
            "source_hash_matches_approved_snapshot": source_sha_before == PRE_MOVE_SHA256,
            "source_unchanged_during_run": source_sha_before == source_sha_after,
            "records": int(len(result.source)),
            "columns": int(result.source.shape[1]),
            "nasa_comment_metadata_skipped": True,
        },
        "eligibility": {
            **result.eligibility,
            "primary_cohort_policy": "Complete-case four-feature eligibility; no imputation.",
            "primary_excluded_records_remain_in_master": True,
            "master_eligibility_columns": [
                "eligible_four_feature_clustering",
                "four_feature_eligibility_reason",
                "eligible_without_temperature_sensitivity",
            ],
            "four_feature_partition_sums_to_source_records": sum(
                result.eligibility["four_feature_stepwise_partition"].values()
            )
            == len(result.source),
        },
        "experiments": {
            "with_temperature": {
                "role": "Primary experiment A",
                "records": len(result.with_temperature),
                "cohort": "The shared 5,273-record complete-case cohort.",
                "transformations": {
                    "pl_rade": "log10(pl_rade)",
                    "pl_orbper": "log10(pl_orbper)",
                    "pl_eqt": "raw value in kelvin",
                    "pl_orbeccen": "raw value; zeros preserved",
                },
                "transformed_feature_columns": list(with_features),
                "standardized_feature_columns": [SCALED_FEATURES[name] for name in with_features],
                "raw_physical_columns_preserved": list(FOUR_FEATURES),
                "scaler_path": SCALER_WITH_TEMP_RELATIVE_PATH.as_posix(),
                "scaler": _scaler_summary(result.scalers["with_temperature"], with_features),
                "output_path": WITH_TEMP_RELATIVE_PATH.as_posix(),
            },
            "without_temperature": {
                "role": "Primary experiment B; same cohort as experiment A.",
                "records": len(result.without_temperature),
                "cohort": "The shared 5,273-record complete-case cohort.",
                "transformations": {
                    "pl_rade": "log10(pl_rade)",
                    "pl_orbper": "log10(pl_orbper)",
                    "pl_orbeccen": "raw value; zeros preserved",
                },
                "transformed_feature_columns": list(without_features),
                "standardized_feature_columns": [SCALED_FEATURES[name] for name in without_features],
                "raw_physical_columns_preserved": list(FOUR_FEATURES),
                "pl_eqt_column_note": "Retained as a raw physical measurement; not a feature in experiment B.",
                "scaler_path": SCALER_WITHOUT_TEMP_RELATIVE_PATH.as_posix(),
                "scaler": _scaler_summary(result.scalers["without_temperature"], without_features),
                "output_path": WITHOUT_TEMP_RELATIVE_PATH.as_posix(),
            },
            "identical_planet_ids_and_order": result.with_temperature["pl_name"].tolist()
            == result.without_temperature["pl_name"].tolist(),
            "sensitivity_only_eligible_without_temperature_records": EXPECTED_WITHOUT_TEMPERATURE_RECORDS,
            "sensitivity_dataset_written": False,
        },
        "feature_quality": {
            "raw_feature_missing_counts": {
                name: int(result.source[name].isna().sum()) for name in FOUR_FEATURES
            },
            "raw_feature_missing_percent": {
                name: round(float(result.source[name].isna().mean() * 100), 6)
                for name in FOUR_FEATURES
            },
            "raw_zero_counts": {
                name: int((pd.to_numeric(result.source[name], errors="coerce") == 0).sum())
                for name in FOUR_FEATURES
            },
            "raw_non_finite_counts": {
                name: int(
                    (~np.isfinite(
                        pd.to_numeric(result.source[name], errors="coerce").to_numpy(
                            dtype=np.float64, na_value=np.nan
                        )
                    ) & pd.to_numeric(result.source[name], errors="coerce").notna().to_numpy()).sum()
                )
                for name in FOUR_FEATURES
            },
            "physical_measurements_overwritten": False,
            "extreme_values_removed": False,
            "eccentricity_zero_count_in_primary_cohort": result.eligibility[
                "review_only_domain_flags"
            ]["eccentricity_zero_primary_cohort"],
        },
        "extreme_value_investigation": {
            "interpretation": (
                "IQR thresholds identify statistical review flags only. They do not establish "
                "that a measurement is wrong. All listed records and original values are retained."
            ),
            "records_by_feature": iqr_extreme_investigation(result.source),
            "unresolved_concerns": [
                "The very large orbital periods, including COCONUTS-2 b, need source-level scientific review before downstream interpretation.",
                "High IQR flags for radius, equilibrium temperature, and eccentricity are retained; this report does not establish whether any measurement is physically correct.",
                "StandardScaler uses the full primary cohort and can be influenced by extreme values; the approved policy retains them pending review.",
            ],
        },
        "decisions": {
            "missing_data": "No imputation. The primary clustering cohort requires all four finite features and positive radius and period for log10.",
            "eccentricity_zeros": "Preserved as valid raw zero values.",
            "extreme_values": "No automatic deletion or winsorization.",
            "standardization": "StandardScaler fitted independently to each experiment's feature columns.",
            "model_training": "No clustering or supervised model was trained.",
        },
        "runtime": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
        "outputs": {
            "master_path": MASTER_RELATIVE_PATH.as_posix(),
            "master_records": len(result.master),
            "master_preserves_all_source_columns": all(
                name in result.master.columns for name in result.source.columns
            ),
            "feature_matrix_rows": {
                WITH_TEMP_RELATIVE_PATH.as_posix(): len(result.with_temperature),
                WITHOUT_TEMP_RELATIVE_PATH.as_posix(): len(result.without_temperature),
            },
            "sha256": _file_hashes(root, report_files),
        },
    }


def _fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    number = float(value)
    return f"{number:.8g}"


def _markdown_report(report: dict[str, Any]) -> str:
    dataset = report["dataset"]
    eligibility = report["eligibility"]
    experiments = report["experiments"]
    quality = report["feature_quality"]
    lines = [
        "# ExoAtlas Preprocessing Report",
        "",
        "## Dataset overview",
        "",
        f"- Source snapshot: `{dataset['name']}` ({dataset['snapshot_date']}).",
        f"- Source records and columns: **{dataset['records']:,}** and **{dataset['columns']}**.",
        f"- SHA-256: `{dataset['source_sha256_before']}`; it matches the approved snapshot and remained unchanged during the run: **{dataset['source_unchanged_during_run']}**.",
        "- NASA `#` comment metadata was skipped while reading. The raw CSV was not modified.",
        "- Every source row and source column remains in `data/processed/planets_master.csv`; the master adds eligibility indicators and reasons, but no cluster labels.",
        "",
        "## Cohort eligibility and missing data",
        "",
        f"- Four-feature complete cases: **{eligibility['all_four_fields_present']:,}**.",
        f"- Four features finite and numeric: **{eligibility['all_four_fields_finite_numeric']:,}**.",
        f"- Eligible for both primary experiments: **{eligibility['eligible_four_feature_records']:,}**.",
        f"- Eligible without temperature (sensitivity flag only): **{eligibility['eligible_without_temperature_sensitivity_records']:,}**.",
        "- Both primary experiments use the same 5,273 records in the same source order. The extra no-temperature-eligible records are not included in either primary matrix.",
        "- No values are imputed. Ineligible planets remain in the master file and have a false eligibility indicator plus a reason.",
        "",
        "| Four-feature eligibility step | Records |",
        "|---|---:|",
    ]
    for step, count in eligibility["four_feature_stepwise_partition"].items():
        lines.append(f"| {step.replace('_', ' ')} | {count:,} |")
    lines.extend([
        "",
        "The stepwise exclusion categories are disjoint and sum to the 6,451 source records. Missing values account for the 1,178 primary exclusions; no complete records were excluded for nonnumeric, non-finite, nonpositive-radius, or nonpositive-period values. Radius and period must be greater than zero because they are log transformed. Temperature and eccentricity have no additional review-domain violations in this snapshot. Eccentricity zeros are retained.",
        "",
        "### Planned feature missingness",
        "",
        "| Feature | Missing records | Missing percent | Raw zero values |",
        "|---|---:|---:|---:|",
    ])
    for feature in FOUR_FEATURES:
        lines.append(
            f"| `{feature}` | {quality['raw_feature_missing_counts'][feature]:,} | "
            f"{quality['raw_feature_missing_percent'][feature]:.6f}% | "
            f"{quality['raw_zero_counts'][feature]:,} |"
        )
    lines.extend([
        "",
        "## Feature transformations",
        "",
        "Experiment A uses `log10(pl_rade)`, `log10(pl_orbper)`, raw equilibrium temperature, and raw eccentricity. Experiment B uses the first two transformed features and raw eccentricity. The original physical columns remain unchanged in both output tables; experiment B also retains raw `pl_eqt` as context, but it is not among that experiment's model features.",
        "",
        "Base-10 logs reduce the wide positive scale of radius and especially orbital period while preserving order among positive values. StandardScaler then centers each experiment's transformed feature columns and scales them to unit population variance so units and numeric ranges do not dominate by scale alone. Each experiment has its own fitted scaler because its feature set differs.",
        "",
        f"- Experiment A features: `{', '.join(experiments['with_temperature']['standardized_feature_columns'])}`.",
        f"- Experiment B features: `{', '.join(experiments['without_temperature']['standardized_feature_columns'])}`.",
        f"- Eccentricity zero measurements preserved in the primary cohort: **{quality['eccentricity_zero_count_in_primary_cohort']:,}**.",
        "",
        "## Extreme-value investigation",
        "",
        "The 1.5×IQR rule is used only to flag statistical extremes for review. Flags are not proof of invalidity, and no rows were removed or changed. Tables list the five largest values per feature, with source record, planet and host identifiers, and all four original physical measurements.",
        "",
        "| Feature | Source record | Planet | Host | Primary cohort | Flagged value | Radius | Period (days) | Equilibrium temp (K) | Eccentricity |",
        "|---|---:|---|---|---|---:|---:|---:|---:|---:|",
    ])
    for feature, findings in report["extreme_value_investigation"]["records_by_feature"].items():
        for item in findings["highest_records"]:
            physical = item["original_physical_measurements"]
            flagged = " (IQR)" if item["iqr_flagged"] else ""
            lines.append(
                f"| `{feature}` | {item['source_data_record_number']} | {item['pl_name']} | {item['hostname']} | "
                f"{item['eligible_four_feature_clustering']} | "
                f"{_fmt(item['value'])}{flagged} | {_fmt(physical['pl_rade'])} | "
                f"{_fmt(physical['pl_orbper'])} | {_fmt(physical['pl_eqt'])} | {_fmt(physical['pl_orbeccen'])} |"
            )
    lines.extend([
        "",
        "The largest orbital period is COCONUTS-2 b at 402,000,000 days (source record 101); it is an IQR review flag, but this row is outside the primary cohort because eccentricity is missing. Other largest values include V2376 Ori b at 87.20586985 Earth radii, KOI-55 b at 7,777.78 K, and eccentricities of 0.95 for HD 20782 b and HD 28254 b. The table marks which records enter the primary cohort. These values are unusual relative to the distribution; this audit cannot establish measurement validity.",
        "",
        "No records violated the numeric or log-transform eligibility rules in this source. `pl_eqt <= 0`, negative eccentricity, and eccentricity >= 1 review counts are all zero. The many upper IQR flags, including long-period planets and high eccentricities, remain preserved and warrant source-level review before interpreting downstream clusters. StandardScaler is sensitive to extreme values.",
        "",
        "## Outputs and reproducibility",
        "",
        "- `data/processed/planets_master.csv`: 6,451 source rows and all 84 source columns, plus row provenance and eligibility columns.",
        "- `data/processed/clustering_features_with_temp.csv`: 5,273 rows, retained identifiers and raw physical measurements, transformed columns, and standardized Experiment A features.",
        "- `data/processed/clustering_features_without_temp.csv`: the same 5,273 identifiers in the same order, with raw `pl_eqt` retained only as a physical measurement.",
        "- `artifacts/preprocessing/scaler_with_temp.joblib` and `scaler_without_temp.joblib`: separately fitted scaler objects with their feature order, means, variances, and scales recorded in this report.",
        "- No clustering or supervised model was run.",
        "",
        "## Decisions and unresolved scientific questions",
        "",
        "Approved policy used here: complete cases for primary experiments; no imputation; preserve all observations in the master; positive radius and period for base-10 logs; preserve eccentricity zeros; keep raw physical columns; retain extreme values; and standardize each feature set separately.",
        "",
        "Before clustering results are interpreted, review the very long orbital-period observations and other IQR flags against their source references. Decide how to discuss the influence of such observations on StandardScaler. This pipeline does not determine whether an extreme measurement is physically correct. Multi-planet hosts are also present in the source; whether later analysis should account for host-level dependence remains a modeling question.",
        "",
        f"The two primary feature matrices have identical planet identifiers in the same order: **{experiments['identical_planet_ids_and_order']}**.",
        "",
    ])
    return "\n".join(lines)


def run_pipeline(
    source_path: Path = SOURCE_PATH,
    output_root: Path = ROOT,
) -> dict[str, Any]:
    """Run validation, preprocessing, scaler serialization, and report generation."""
    source_path = Path(source_path)
    output_root = Path(output_root)
    source_sha_before = sha256_file(source_path)
    frame = load_source_dataset(source_path, expected_sha256=PRE_MOVE_SHA256)
    if len(frame) != SOURCE_RECORDS or frame.shape[1] != SOURCE_COLUMNS:
        raise ValueError(
            f"Expected {SOURCE_RECORDS} records and {SOURCE_COLUMNS} columns; "
            f"found {len(frame)} and {frame.shape[1]} instead."
        )
    result = prepare_frames(frame)

    output_paths = {
        MASTER_RELATIVE_PATH: result.master,
        WITH_TEMP_RELATIVE_PATH: result.with_temperature,
        WITHOUT_TEMP_RELATIVE_PATH: result.without_temperature,
    }
    for relative_path, output_frame in output_paths.items():
        target = output_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        output_frame.to_csv(target, index=False, encoding="utf-8", float_format="%.17g")

    scaler_targets = {
        SCALER_WITH_TEMP_RELATIVE_PATH: result.scalers["with_temperature"],
        SCALER_WITHOUT_TEMP_RELATIVE_PATH: result.scalers["without_temperature"],
    }
    for relative_path, scaler in scaler_targets.items():
        target = output_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(scaler, target, compress=3, protocol=5)

    source_sha_after = sha256_file(source_path)
    if source_sha_before != source_sha_after:
        raise RuntimeError("The source CSV changed during preprocessing.")

    report = _report_data(
        result,
        source_path=source_path,
        source_sha_before=source_sha_before,
        source_sha_after=source_sha_after,
        root=output_root,
    )
    json_path = output_root / REPORT_JSON_RELATIVE_PATH
    markdown_path = output_root / REPORT_MARKDOWN_RELATIVE_PATH
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.write_text(_markdown_report(report), encoding="utf-8", newline="\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_PATH, help="Pinned NASA CSV path")
    parser.add_argument("--output-root", type=Path, default=ROOT, help="Root for generated outputs")
    args = parser.parse_args()
    report = run_pipeline(source_path=args.source, output_root=args.output_root)
    print(
        "Preprocessing complete: "
        f"{report['dataset']['records']:,} master rows; "
        f"{report['eligibility']['eligible_four_feature_records']:,} primary cohort rows."
    )
    print(f"Reports: {args.output_root / REPORT_JSON_RELATIVE_PATH} and "
          f"{args.output_root / REPORT_MARKDOWN_RELATIVE_PATH}")


if __name__ == "__main__":
    main()
