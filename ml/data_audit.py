"""Read-only audit of the pinned NASA PSCompPars dataset snapshot."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RELATIVE_PATH = Path("data/raw/PSCompPars_2026.10.30_13.47.46.csv")
SOURCE_PATH = ROOT / SOURCE_RELATIVE_PATH
METADATA_DIR = ROOT / "data" / "metadata"
JSON_PATH = METADATA_DIR / "dataset_audit.json"
MARKDOWN_PATH = METADATA_DIR / "dataset_audit.md"

# Captured before the source CSV was moved into data/raw/.
PRE_MOVE_SHA256 = "16bb38b253d375b49cdb286b45e38435746c74bfde10d3ba580199fa822b6c30"

FEATURES = ("pl_rade", "pl_orbper", "pl_eqt", "pl_orbeccen")
FEATURES_WITHOUT_TEMPERATURE = ("pl_rade", "pl_orbper", "pl_orbeccen")
FEATURE_UNITS = {
    "pl_rade": "Earth radii",
    "pl_orbper": "days",
    "pl_eqt": "K",
    "pl_orbeccen": "dimensionless",
}
MISSING_LABEL = "[missing]"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def percentage(count: int, total: int) -> float:
    return round((count / total) * 100, 6) if total else 0.0


def category_label(value: Any) -> str:
    if pd.isna(value):
        return MISSING_LABEL
    if isinstance(value, (float, np.floating)) and float(value).is_integer():
        return str(int(value))
    return str(value)


def frequency_table(series: pd.Series) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for value in series:
        label = category_label(value)
        counts[label] = counts.get(label, 0) + 1
    total = len(series)
    return [
        {
            "value": label,
            "count": count,
            "percent_of_records": percentage(count, total),
        }
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def read_comment_metadata(path: Path) -> list[str]:
    comments: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        for line in source:
            stripped = line.lstrip()
            if stripped.startswith("#"):
                comments.append(stripped[1:].strip())
            elif stripped.strip():
                break
    return comments


def _extreme_examples(
    frame: pd.DataFrame,
    values: np.ndarray,
    mask: np.ndarray,
    *,
    largest: bool,
    limit: int = 5,
) -> list[dict[str, Any]]:
    positions = np.flatnonzero(mask)
    positions = sorted(positions, key=lambda position: values[position], reverse=largest)
    examples: list[dict[str, Any]] = []
    for position in positions[:limit]:
        identifier = frame.iloc[position].get("pl_name")
        examples.append(
            {
                "data_record_number": int(position + 1),
                "pl_name": None if pd.isna(identifier) else str(identifier),
                "value": float(values[position]),
            }
        )
    return examples


def feature_audit(frame: pd.DataFrame, column: str) -> tuple[dict[str, Any], pd.Series]:
    raw = frame[column]
    numeric = pd.to_numeric(raw, errors="coerce")
    values = numeric.to_numpy(dtype=np.float64, na_value=np.nan)
    finite_mask = np.isfinite(values)
    missing_mask = raw.isna().to_numpy()
    nonnumeric_mask = raw.notna().to_numpy() & numeric.isna().to_numpy()
    positive_infinity_mask = np.isposinf(values)
    negative_infinity_mask = np.isneginf(values)
    finite_values = values[finite_mask]

    if finite_values.size:
        q1, median, q3 = np.quantile(finite_values, [0.25, 0.5, 0.75])
        minimum = float(np.min(finite_values))
        mean = float(np.mean(finite_values))
        maximum = float(np.max(finite_values))
        standard_deviation = (
            float(np.std(finite_values, ddof=1)) if finite_values.size > 1 else None
        )
        iqr = float(q3 - q1)
        quantile_profile = {
            f"p{int(percentile * 100):02d}": float(
                np.quantile(finite_values, percentile)
            )
            for percentile in (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99)
        }
        lower_fence = float(q1 - 1.5 * iqr)
        upper_fence = float(q3 + 1.5 * iqr)
        lower_extreme_mask = finite_mask & (values < lower_fence)
        upper_extreme_mask = finite_mask & (values > upper_fence)
    else:
        q1 = median = q3 = minimum = mean = maximum = standard_deviation = None
        quantile_profile = {}
        iqr = lower_fence = upper_fence = None
        lower_extreme_mask = np.zeros(len(frame), dtype=bool)
        upper_extreme_mask = np.zeros(len(frame), dtype=bool)

    nonnumeric_values = raw.iloc[np.flatnonzero(nonnumeric_mask)].astype(str).value_counts()
    summary = {
        "inferred_dtype": str(raw.dtype),
        "records": int(len(frame)),
        "missing_count": int(missing_mask.sum()),
        "missing_percent": percentage(int(missing_mask.sum()), len(frame)),
        "non_numeric_count": int(nonnumeric_mask.sum()),
        "non_numeric_examples": [
            {"value": str(value), "count": int(count)}
            for value, count in sorted(
                nonnumeric_values.items(), key=lambda item: (-item[1], str(item[0]))
            )[:10]
        ],
        "positive_infinity_count": int(positive_infinity_mask.sum()),
        "negative_infinity_count": int(negative_infinity_mask.sum()),
        "finite_numeric_count": int(finite_mask.sum()),
        "zero_count": int(np.count_nonzero(finite_values == 0)),
        "negative_count": int(np.count_nonzero(finite_values < 0)),
        "positive_count": int(np.count_nonzero(finite_values > 0)),
        "statistics_finite_values_only": {
            "minimum": json_number(minimum),
            "mean": json_number(mean),
            "q1": json_number(q1),
            "median": json_number(median),
            "q3": json_number(q3),
            "maximum": json_number(maximum),
            "standard_deviation_sample": json_number(standard_deviation),
            "iqr": json_number(iqr),
            "quantile_profile": {
                name: json_number(value) for name, value in quantile_profile.items()
            },
        },
        "iqr_extreme_review_flags": {
            "rule": "below Q1 - 1.5*IQR or above Q3 + 1.5*IQR; review flag only, not removed",
            "lower_fence": json_number(lower_fence),
            "upper_fence": json_number(upper_fence),
            "below_lower_fence_count": int(lower_extreme_mask.sum()),
            "above_upper_fence_count": int(upper_extreme_mask.sum()),
            "lowest_examples": _extreme_examples(
                frame, values, lower_extreme_mask, largest=False
            ),
            "highest_examples": _extreme_examples(
                frame, values, upper_extreme_mask, largest=True
            ),
        },
    }
    return summary, pd.Series(finite_mask, index=frame.index, dtype=bool)


def duplicate_audit(frame: pd.DataFrame) -> dict[str, Any]:
    identifier_column = "pl_name" if "pl_name" in frame.columns else None
    if identifier_column is None:
        identifiers: dict[str, Any] = {
            "identifier_column": None,
            "status": "No pl_name planet identifier column was found.",
        }
    else:
        names = frame[identifier_column]
        counts = names.dropna().astype(str).value_counts()
        duplicate_groups = counts[counts > 1]
        examples: list[dict[str, Any]] = []
        for name, count in sorted(
            duplicate_groups.items(), key=lambda item: (-item[1], str(item[0]))
        )[:20]:
            row_numbers = [
                int(index + 1)
                for index in frame.index[names.astype("string").eq(str(name)).fillna(False)]
            ]
            examples.append(
                {"planet_identifier": str(name), "row_count": int(count), "data_record_numbers": row_numbers}
            )
        duplicate_row_mask = names.notna() & names.astype("string").duplicated(keep=False)
        identifiers = {
            "identifier_column": identifier_column,
            "non_missing_identifier_rows": int(names.notna().sum()),
            "unique_identifiers": int(counts.size),
            "duplicate_identifier_groups": int(duplicate_groups.size),
            "rows_in_duplicate_identifier_groups": int(duplicate_row_mask.sum()),
            "extra_rows_beyond_first_identifier_occurrence": int((duplicate_groups - 1).sum()),
            "examples": examples,
        }

    duplicate_mask = frame.duplicated(keep=False)
    exact_duplicate_groups = int(frame.loc[duplicate_mask].drop_duplicates().shape[0])
    exact_duplicate_rows_beyond_first = int(frame.duplicated(keep="first").sum())
    return {
        "planet_identifier": identifiers,
        "exact_duplicate_records": {
            "rows_in_duplicate_groups": int(duplicate_mask.sum()),
            "duplicate_groups": exact_duplicate_groups,
            "extra_rows_beyond_first_copy": exact_duplicate_rows_beyond_first,
        },
    }


def host_audit(frame: pd.DataFrame) -> dict[str, Any]:
    if "hostname" not in frame.columns:
        return {"hostname_column_present": False}

    hostnames = frame["hostname"].dropna().astype(str)
    counts = hostnames.value_counts()
    multiple = counts[counts > 1]
    multiplicities = counts.value_counts().sort_index()
    top_systems = [
        {"hostname": str(host), "planet_records": int(count)}
        for host, count in sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))
        if count > 1
    ][:20]
    total_with_hostname = int(len(hostnames))
    records_in_multi_planet_systems = int(multiple.sum())
    return {
        "hostname_column_present": True,
        "records_with_hostname": total_with_hostname,
        "records_missing_hostname": int(frame["hostname"].isna().sum()),
        "unique_host_stars": int(counts.size),
        "host_stars_with_multiple_planets": int(multiple.size),
        "planet_records_in_multi_planet_systems": records_in_multi_planet_systems,
        "percent_of_records_with_hostname_in_multi_planet_systems": percentage(
            records_in_multi_planet_systems, total_with_hostname
        ),
        "system_size_distribution": [
            {"planets_per_host": int(size), "host_count": int(host_count)}
            for size, host_count in multiplicities.items()
        ],
        "largest_multi_planet_hosts": top_systems,
    }


def eligibility_audit(
    frame: pd.DataFrame,
    numeric_values: dict[str, pd.Series],
    finite_masks: dict[str, pd.Series],
) -> dict[str, Any]:
    present_all = frame.loc[:, FEATURES].notna().all(axis=1)
    finite_all = pd.concat([finite_masks[name] for name in FEATURES], axis=1).all(axis=1)
    radius_positive = numeric_values["pl_rade"] > 0
    period_positive = numeric_values["pl_orbper"] > 0

    missing_any = ~present_all
    complete_nonnumeric = present_all & pd.concat(
        [frame[name].notna() & numeric_values[name].isna() for name in FEATURES], axis=1
    ).any(axis=1)
    complete_nonfinite = present_all & ~complete_nonnumeric & pd.concat(
        [
            numeric_values[name].notna() & ~finite_masks[name]
            for name in FEATURES
        ],
        axis=1,
    ).any(axis=1)
    finite_complete = finite_all
    invalid_radius = finite_complete & ~radius_positive
    after_radius = finite_complete & radius_positive
    invalid_period = after_radius & ~period_positive
    eligible_all_four = after_radius & period_positive

    partition = {
        "missing_one_or_more_features": int(missing_any.sum()),
        "nonnumeric_value_after_complete_case_check": int(complete_nonnumeric.sum()),
        "infinite_value_after_numeric_check": int(complete_nonfinite.sum()),
        "nonpositive_radius_after_finite_check": int(invalid_radius.sum()),
        "nonpositive_orbital_period_after_radius_check": int(invalid_period.sum()),
        "eligible_all_four_features": int(eligible_all_four.sum()),
    }
    if sum(partition.values()) != len(frame):
        raise AssertionError("Stepwise all-four-feature eligibility counts do not sum to total records.")

    independent_rule_counts = {
        "any_missing_required_feature": int(missing_any.sum()),
        "any_nonnumeric_required_feature": int(
            pd.concat(
                [frame[name].notna() & numeric_values[name].isna() for name in FEATURES], axis=1
            ).any(axis=1).sum()
        ),
        "any_infinite_required_feature": int(
            pd.concat(
                [numeric_values[name].notna() & ~finite_masks[name] for name in FEATURES], axis=1
            ).any(axis=1).sum()
        ),
        "nonpositive_radius": int((numeric_values["pl_rade"].notna() & ~radius_positive).sum()),
        "nonpositive_orbital_period": int(
            (numeric_values["pl_orbper"].notna() & ~period_positive).sum()
        ),
    }

    without_eqt = list(FEATURES_WITHOUT_TEMPERATURE)
    present_without_eqt = frame.loc[:, without_eqt].notna().all(axis=1)
    finite_without_eqt = pd.concat([finite_masks[name] for name in without_eqt], axis=1).all(axis=1)
    eligible_without_eqt = (
        finite_without_eqt & radius_positive & period_positive
    )

    eqt_numeric = numeric_values["pl_eqt"]
    ecc_numeric = numeric_values["pl_orbeccen"]
    return {
        "rules": [
            "Require all four planned feature fields to be present for the all-feature count.",
            "Require each of the four fields to parse as a finite number.",
            "Require pl_rade > 0 and pl_orbper > 0 for the proposed base-10 logarithms.",
            "Retain eccentricity zeros. Nonpositive equilibrium temperature and eccentricity outside [0, 1) are reported for review, not silently filtered from the numeric/log-eligible count.",
        ],
        "records_with_all_four_features_present": int(present_all.sum()),
        "records_with_all_four_features_finite_numeric": int(finite_all.sum()),
        "records_log_transform_eligible_with_all_four_features": int(eligible_all_four.sum()),
        "stepwise_all_four_feature_exclusions_and_eligibility": partition,
        "independent_rule_counts_overlap_possible": independent_rule_counts,
        "without_equilibrium_temperature_variant": {
            "required_features": without_eqt,
            "records_with_all_required_fields_present": int(present_without_eqt.sum()),
            "records_with_all_required_features_finite_numeric": int(finite_without_eqt.sum()),
            "records_log_transform_eligible": int(eligible_without_eqt.sum()),
        },
        "review_only_domain_flags_not_used_as_eligibility_filters": {
            "pl_rade_nonpositive": int((numeric_values["pl_rade"].notna() & ~radius_positive).sum()),
            "pl_orbper_nonpositive": int((numeric_values["pl_orbper"].notna() & ~period_positive).sum()),
            "pl_eqt_nonpositive": int((eqt_numeric.notna() & (eqt_numeric <= 0)).sum()),
            "pl_orbeccen_negative": int((ecc_numeric.notna() & (ecc_numeric < 0)).sum()),
            "pl_orbeccen_at_least_1": int((ecc_numeric.notna() & (ecc_numeric >= 1)).sum()),
        },
    }


def audit_dataset() -> dict[str, Any]:
    if not SOURCE_PATH.is_file():
        raise FileNotFoundError(f"Expected source dataset at {SOURCE_PATH}")

    actual_sha256 = sha256_file(SOURCE_PATH)
    if actual_sha256.lower() != PRE_MOVE_SHA256:
        raise RuntimeError(
            "The source SHA-256 differs from the checksum captured before the move. "
            "Review the source before updating PRE_MOVE_SHA256."
        )

    comments = read_comment_metadata(SOURCE_PATH)
    frame = pd.read_csv(
        SOURCE_PATH,
        comment="#",
        encoding="utf-8-sig",
        low_memory=False,
    )

    absent_features = [name for name in FEATURES if name not in frame.columns]
    if absent_features:
        raise ValueError(f"Required planned feature columns are missing: {absent_features}")

    columns = [
        {"name": str(name), "inferred_dtype": str(frame[name].dtype)}
        for name in frame.columns
    ]
    dtype_counts: dict[str, int] = {}
    for column in columns:
        dtype_counts[column["inferred_dtype"]] = dtype_counts.get(column["inferred_dtype"], 0) + 1

    row_count, column_count = frame.shape
    missing_by_column: dict[str, dict[str, Any]] = {}
    for name in frame.columns:
        count = int(frame[name].isna().sum())
        missing_by_column[str(name)] = {
            "missing_count": count,
            "missing_percent": percentage(count, row_count),
        }

    feature_results: dict[str, Any] = {}
    finite_masks: dict[str, pd.Series] = {}
    numeric_values: dict[str, pd.Series] = {}
    for name in FEATURES:
        feature_results[name], finite_masks[name] = feature_audit(frame, name)
        feature_results[name]["unit"] = FEATURE_UNITS[name]
        numeric_values[name] = pd.to_numeric(frame[name], errors="coerce")

    distributions: dict[str, Any] = {}
    for name in ("discoverymethod", "pl_bmassprov"):
        distributions[name] = {
            "column_present": name in frame.columns,
            "frequencies": frequency_table(frame[name]) if name in frame.columns else [],
        }

    if "disc_year" in frame.columns:
        year_numeric = pd.to_numeric(frame["disc_year"], errors="coerce")
        year_finite = np.isfinite(year_numeric.to_numpy(dtype=np.float64, na_value=np.nan))
        finite_years = year_numeric.to_numpy(dtype=np.float64, na_value=np.nan)[year_finite]
        year_stats = {
            "finite_numeric_count": int(finite_years.size),
            "missing_count": int(frame["disc_year"].isna().sum()),
            "non_numeric_count": int((frame["disc_year"].notna() & year_numeric.isna()).sum()),
            "minimum": json_number(np.min(finite_years)) if finite_years.size else None,
            "q1": json_number(np.quantile(finite_years, 0.25)) if finite_years.size else None,
            "median": json_number(np.quantile(finite_years, 0.5)) if finite_years.size else None,
            "q3": json_number(np.quantile(finite_years, 0.75)) if finite_years.size else None,
            "maximum": json_number(np.max(finite_years)) if finite_years.size else None,
            "standard_deviation_sample": (
                json_number(np.std(finite_years, ddof=1)) if finite_years.size > 1 else None
            ),
        }
        year_counts: dict[str, int] = {}
        for value in frame["disc_year"]:
            label = category_label(value)
            year_counts[label] = year_counts.get(label, 0) + 1
        year_distribution = [
            {"year": year, "count": year_counts[year]}
            for year in sorted(year_counts, key=lambda item: (item == MISSING_LABEL, item))
        ]
        distributions["disc_year"] = {
            "column_present": True,
            "statistics": year_stats,
            "frequency_by_year_including_missing": year_distribution,
        }
    else:
        distributions["disc_year"] = {"column_present": False}

    eligibility = eligibility_audit(frame, numeric_values, finite_masks)
    if eligibility["records_with_all_four_features_finite_numeric"] > eligibility[
        "records_with_all_four_features_present"
    ]:
        raise AssertionError("Finite all-feature records cannot exceed complete all-feature records.")
    if eligibility["records_log_transform_eligible_with_all_four_features"] > eligibility[
        "records_with_all_four_features_finite_numeric"
    ]:
        raise AssertionError("Log-eligible records cannot exceed finite all-feature records.")

    result = {
        "audit_schema_version": 1,
        "source": {
            "file_name": SOURCE_RELATIVE_PATH.name,
            "path": SOURCE_RELATIVE_PATH.as_posix(),
            "snapshot_date": "2026-10-30",
            "comment_metadata_lines": comments,
            "sha256_before_move": PRE_MOVE_SHA256,
            "sha256_after_move": actual_sha256,
            "sha256_matches_before_move": actual_sha256.lower() == PRE_MOVE_SHA256,
            "file_size_bytes": int(SOURCE_PATH.stat().st_size),
        },
        "audit_environment": {
            "python_version": sys.version.split()[0],
            "pandas_version": pd.__version__,
            "numpy_version": np.__version__,
        },
        "dataset_overview": {
            "records": int(row_count),
            "columns": int(column_count),
            "column_names_and_inferred_types": columns,
            "inferred_dtype_counts": dict(sorted(dtype_counts.items())),
        },
        "duplicate_checks": duplicate_audit(frame),
        "missing_values_by_column": missing_by_column,
        "planned_feature_quality": feature_results,
        "distributions": distributions,
        "host_star_relationships": host_audit(frame),
        "clustering_eligibility": eligibility,
    }
    return result


def fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, (float, np.floating)):
        return f"{float(value):,.6g}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown_report(result: dict[str, Any]) -> str:
    overview = result["dataset_overview"]
    source = result["source"]
    dtypes = overview["inferred_dtype_counts"]
    lines = [
        "# NASA PSCompPars Dataset Audit",
        "",
        f"Source: `{source['file_name']}` · snapshot date: {source['snapshot_date']}",
        "",
        "## Dataset overview and integrity",
        "",
        f"- Records: **{overview['records']:,}**",
        f"- Columns: **{overview['columns']:,}**",
        f"- Inferred pandas dtypes: {', '.join(f'{name}: {count}' for name, count in dtypes.items())}",
        f"- SHA-256 before move: `{source['sha256_before_move']}`",
        f"- SHA-256 after move: `{source['sha256_after_move']}`",
        f"- Hash match: **{source['sha256_matches_before_move']}**",
        f"- Source path: `{source['path']}`",
        "",
        "The file was read with pandas while skipping NASA `#` comment metadata. The source CSV was not edited.",
        "",
        "NASA comment metadata:",
        "",
    ]
    lines.extend([f"- {item}" for item in source["comment_metadata_lines"]] or ["- No comment metadata lines found."])

    lines.extend(
        [
            "",
            "## Schema and missing values",
            "",
            "Missingness is calculated from pandas' parsed source values. Percentages use all dataset records as the denominator.",
            "",
            "| Column | Inferred dtype | Missing | Missing % |",
            "|---|---:|---:|---:|",
        ]
    )
    for column in overview["column_names_and_inferred_types"]:
        missing = result["missing_values_by_column"][column["name"]]
        lines.append(
            f"| {column['name']} | {column['inferred_dtype']} | {missing['missing_count']:,} | {fmt(missing['missing_percent'])}% |"
        )

    duplicates = result["duplicate_checks"]
    identifiers = duplicates["planet_identifier"]
    lines.extend(
        [
            "",
            "## Duplicate checks",
            "",
            f"- Planet identifier column: `{identifiers.get('identifier_column')}`.",
            f"- Duplicate identifier groups: {identifiers.get('duplicate_identifier_groups', 'not available'):,}.",
            f"- Rows in duplicate identifier groups: {identifiers.get('rows_in_duplicate_identifier_groups', 'not available'):,}.",
            f"- Exact duplicate record groups: {duplicates['exact_duplicate_records']['duplicate_groups']:,}.",
            f"- Exact duplicate rows beyond the first copy: {duplicates['exact_duplicate_records']['extra_rows_beyond_first_copy']:,}.",
            "",
        ]
    )
    if identifiers.get("examples"):
        lines.extend(["Repeated planet identifiers for review:", ""])
        for example in identifiers["examples"]:
            lines.append(
                f"- `{example['planet_identifier']}` appears {example['row_count']} times (data records {', '.join(map(str, example['data_record_numbers']))})."
            )

    lines.extend(
        [
            "## Planned feature quality",
            "",
            "Descriptive statistics use finite numeric values only. IQR flags use the 1.5×IQR rule for review; they do not remove records.",
            "",
            "| Feature (unit) | dtype | Missing | Non-numeric | +∞ | −∞ | Zero | Negative | Min | Mean | Q1 | Median | Q3 | Max | Sample SD | IQR flags |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, feature in result["planned_feature_quality"].items():
        stats = feature["statistics_finite_values_only"]
        extremes = feature["iqr_extreme_review_flags"]
        flag_count = extremes["below_lower_fence_count"] + extremes["above_upper_fence_count"]
        lines.append(
            "| {name} ({unit}) | {dtype} | {missing} | {nonnumeric} | {posinf} | {neginf} | {zeros} | {negative} | {minimum} | {mean} | {q1} | {median} | {q3} | {maximum} | {std} | {flags} |".format(
                name=name,
                unit=feature["unit"],
                dtype=feature["inferred_dtype"],
                missing=feature["missing_count"],
                nonnumeric=feature["non_numeric_count"],
                posinf=feature["positive_infinity_count"],
                neginf=feature["negative_infinity_count"],
                zeros=feature["zero_count"],
                negative=feature["negative_count"],
                minimum=fmt(stats["minimum"]),
                mean=fmt(stats["mean"]),
                q1=fmt(stats["q1"]),
                median=fmt(stats["median"]),
                q3=fmt(stats["q3"]),
                maximum=fmt(stats["maximum"]),
                std=fmt(stats["standard_deviation_sample"]),
                flags=flag_count,
            )
        )

    lines.extend(
        [
            "",
            "### Distribution quantiles (raw units)",
            "",
            "| Feature (unit) | P05 | P10 | Q1 / P25 | Median / P50 | Q3 / P75 | P90 | P95 | P99 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, feature in result["planned_feature_quality"].items():
        quantiles = feature["statistics_finite_values_only"]["quantile_profile"]
        lines.append(
            "| {name} ({unit}) | {p05} | {p10} | {p25} | {p50} | {p75} | {p90} | {p95} | {p99} |".format(
                name=name,
                unit=feature["unit"],
                p05=fmt(quantiles.get("p05")),
                p10=fmt(quantiles.get("p10")),
                p25=fmt(quantiles.get("p25")),
                p50=fmt(quantiles.get("p50")),
                p75=fmt(quantiles.get("p75")),
                p90=fmt(quantiles.get("p90")),
                p95=fmt(quantiles.get("p95")),
                p99=fmt(quantiles.get("p99")),
            )
        )

    lines.extend(["", "### Extreme-value review flags", ""])
    for name, feature in result["planned_feature_quality"].items():
        flags = feature["iqr_extreme_review_flags"]
        lines.append(
            f"- `{name}`: {flags['below_lower_fence_count']:,} below the lower fence and {flags['above_upper_fence_count']:,} above the upper fence."
        )
        examples = flags["lowest_examples"] + flags["highest_examples"]
        if examples:
            rendered = "; ".join(
                f"{example['pl_name'] or 'unknown planet'}={fmt(example['value'])} (record {example['data_record_number']})"
                for example in examples
            )
            lines.append(f"  Examples: {rendered}.")
    lines.extend(
        [
            "",
            "## Discovery metadata distributions",
            "",
        ]
    )
    for column in ("discoverymethod", "pl_bmassprov"):
        distribution = result["distributions"][column]
        lines.extend([f"### `{column}`", ""])
        if not distribution["column_present"]:
            lines.append("Column not present in the source file.")
            lines.append("")
            continue
        lines.extend(["| Value | Records | Percent |", "|---|---:|---:|"])
        for item in distribution["frequencies"]:
            lines.append(
                f"| {item['value']} | {item['count']:,} | {fmt(item['percent_of_records'])}% |"
            )
        lines.append("")

    year = result["distributions"]["disc_year"]
    lines.extend(["### `disc_year`", ""])
    if not year["column_present"]:
        lines.append("Column not present in the source file.")
    else:
        stats = year["statistics"]
        lines.extend(
            [
                f"Finite numeric records: {stats['finite_numeric_count']:,}; missing: {stats['missing_count']:,}; non-numeric: {stats['non_numeric_count']:,}.",
                f"Range: {fmt(stats['minimum'])}–{fmt(stats['maximum'])}; median: {fmt(stats['median'])}; Q1: {fmt(stats['q1'])}; Q3: {fmt(stats['q3'])}; sample SD: {fmt(stats['standard_deviation_sample'])}.",
                "",
                "| Discovery year | Records |",
                "|---:|---:|",
            ]
        )
        for item in year["frequency_by_year_including_missing"]:
            lines.append(f"| {item['year']} | {item['count']:,} |")

    host = result["host_star_relationships"]
    lines.extend(["", "## Host-star relationships", ""])
    if not host["hostname_column_present"]:
        lines.append("The `hostname` column is not present.")
    else:
        lines.extend(
            [
                f"- Records with a hostname: {host['records_with_hostname']:,}; without one: {host['records_missing_hostname']:,}.",
                f"- Unique host stars: {host['unique_host_stars']:,}.",
                f"- Hosts with multiple planet records: {host['host_stars_with_multiple_planets']:,}.",
                f"- Planet records in those multi-planet systems: {host['planet_records_in_multi_planet_systems']:,} ({fmt(host['percent_of_records_with_hostname_in_multi_planet_systems'])}% of named-host records).",
                "",
                "| Planets per host | Number of hosts |",
                "|---:|---:|",
            ]
        )
        for item in host["system_size_distribution"]:
            lines.append(f"| {item['planets_per_host']} | {item['host_count']:,} |")
        lines.extend(["", "Largest multi-planet hosts:", ""])
        for item in host["largest_multi_planet_hosts"]:
            lines.append(f"- `{item['hostname']}`: {item['planet_records']:,} planet records.")

    eligibility = result["clustering_eligibility"]
    partition = eligibility["stepwise_all_four_feature_exclusions_and_eligibility"]
    lines.extend(
        [
            "",
            "## Clustering eligibility",
            "",
            "The all-four-feature log-eligible count requires all four fields to be present, finite numeric values, and requires positive radius and orbital period for `log10`. Eccentricity zero is retained. `pl_eqt <= 0` and eccentricity outside `[0, 1)` are review flags only, not silent filters.",
            "",
            f"- All four fields present: **{eligibility['records_with_all_four_features_present']:,}** / {overview['records']:,}.",
            f"- All four fields finite and numeric: **{eligibility['records_with_all_four_features_finite_numeric']:,}**.",
            f"- Eligible for the proposed all-four-feature transforms: **{eligibility['records_log_transform_eligible_with_all_four_features']:,}**.",
            "",
            "Stepwise partition (rows at each step are assigned once; counts sum to the source total):",
            "",
            "| Step | Records |",
            "|---|---:|",
        ]
    )
    partition_labels = {
        "missing_one_or_more_features": "Missing one or more required features",
        "nonnumeric_value_after_complete_case_check": "Nonnumeric value among complete rows",
        "infinite_value_after_numeric_check": "Infinite value among otherwise numeric complete rows",
        "nonpositive_radius_after_finite_check": "Nonpositive radius among finite complete rows",
        "nonpositive_orbital_period_after_radius_check": "Nonpositive period after positive-radius rule",
        "eligible_all_four_features": "Eligible with all four features",
    }
    for key, label in partition_labels.items():
        lines.append(f"| {label} | {partition[key]:,} |")
    lines.extend(["", "Independent rule counts can overlap:", ""])
    for key, count in eligibility["independent_rule_counts_overlap_possible"].items():
        lines.append(f"- `{key}`: {count:,} records.")

    without_eqt = eligibility["without_equilibrium_temperature_variant"]
    review = eligibility["review_only_domain_flags_not_used_as_eligibility_filters"]
    lines.extend(
        [
            "",
            "Without `pl_eqt`, the finite-and-log-eligible count for `pl_rade`, `pl_orbper`, and `pl_orbeccen` is **{:,}** (all required fields present: {:,}; finite numeric: {:,}).".format(
                without_eqt["records_log_transform_eligible"],
                without_eqt["records_with_all_required_fields_present"],
                without_eqt["records_with_all_required_features_finite_numeric"],
            ),
            "",
            "Review-only domain flags, not used to reduce the eligibility count:",
            "",
        ]
    )
    for key, count in review.items():
        lines.append(f"- `{key}`: {count:,} records.")

    lines.extend(
        [
            "",
            "## Preprocessing decisions requiring approval",
            "",
            "- Decide how missing values will be handled, and compare the all-four-feature cohort with the cohort that omits equilibrium temperature. No values were imputed.",
            "- Confirm that only positive `pl_rade` and `pl_orbper` values should enter the log-transformed feature space. These are excluded from the reported transform-eligible count, but remain in the source and audit.",
            "- Review nonpositive equilibrium temperatures and eccentricities outside `[0, 1)` against archive documentation before deciding whether any should be excluded. They remain in the audit and were not silently removed.",
            "- Review the IQR-flagged extremes and any duplicate identifiers/records. IQR flags are descriptive and no extremes or duplicates were deleted.",
            "- Decide whether discovery-method and host-star group structure should influence later comparisons. These distributions are descriptive and do not establish causal effects.",
            "",
            "No imputation, log transformation, standardization, model training, or source-data modification was performed.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    result = audit_dataset()
    markdown = markdown_report(result)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    MARKDOWN_PATH.write_text(markdown, encoding="utf-8")
    print(f"Audited {result['dataset_overview']['records']:,} records and {result['dataset_overview']['columns']:,} columns.")
    print(f"Source SHA-256 matches the pre-move checksum: {result['source']['sha256_matches_before_move']}.")
    print(f"Wrote {JSON_PATH.relative_to(ROOT)} and {MARKDOWN_PATH.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
