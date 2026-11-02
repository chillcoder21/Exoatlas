"""Approved, reproducible preprocessing for the NASA PSCompPars snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from .data_audit import PRE_MOVE_SHA256, SOURCE_PATH, sha256_file


SOURCE_RECORDS = 6_451
SOURCE_COLUMNS = 84
FOUR_FEATURES = ("pl_rade", "pl_orbper", "pl_eqt", "pl_orbeccen")
THREE_FEATURES = ("pl_rade", "pl_orbper", "pl_orbeccen")
IDENTIFIERS = ("pl_name", "hostname")
PHYSICAL_FEATURES = FOUR_FEATURES
EXPECTED_PRIMARY_RECORDS = 5_273
EXPECTED_WITHOUT_TEMPERATURE_RECORDS = 5_335

TRANSFORMED_FEATURES = {
    "pl_rade": "log10_pl_rade",
    "pl_orbper": "log10_pl_orbper",
    "pl_eqt": "pl_eqt",
    "pl_orbeccen": "pl_orbeccen",
}
SCALED_FEATURES = {
    "log10_pl_rade": "scaled_log10_pl_rade",
    "log10_pl_orbper": "scaled_log10_pl_orbper",
    "pl_eqt": "scaled_pl_eqt",
    "pl_orbeccen": "scaled_pl_orbeccen",
}


@dataclass(frozen=True)
class PreprocessingResult:
    """Prepared full master table, primary feature views, and fitted scalers."""

    source: pd.DataFrame
    master: pd.DataFrame
    with_temperature: pd.DataFrame
    without_temperature: pd.DataFrame
    scalers: dict[str, StandardScaler]
    eligibility: dict[str, Any]
    masks: dict[str, pd.Series]


def load_source_dataset(
    source_path: Path = SOURCE_PATH,
    expected_sha256: str | None = PRE_MOVE_SHA256,
) -> pd.DataFrame:
    """Read NASA CSV comments correctly and optionally verify the pinned hash."""
    source_path = Path(source_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Expected NASA source CSV at {source_path}")
    if expected_sha256 is not None:
        actual_sha256 = sha256_file(source_path)
        if actual_sha256.lower() != expected_sha256.lower():
            raise RuntimeError(
                "Source SHA-256 differs from the approved dataset snapshot; "
                "review the source before changing the expected checksum."
            )

    frame = pd.read_csv(
        source_path,
        comment="#",
        encoding="utf-8-sig",
        low_memory=False,
    )
    validate_source_dataset(frame)
    return frame


def validate_source_dataset(frame: pd.DataFrame) -> None:
    """Check required source fields and unique, populated planet identifiers."""
    required = (*IDENTIFIERS, *FOUR_FEATURES)
    absent = [name for name in required if name not in frame.columns]
    if absent:
        raise ValueError(f"Required source columns are missing: {absent}")
    if frame["pl_name"].isna().any():
        raise ValueError("The source contains missing pl_name planet identifiers.")
    if frame["pl_name"].astype("string").duplicated().any():
        raise ValueError("The source contains duplicate pl_name planet identifiers.")


def _numeric_columns(frame: pd.DataFrame, features: tuple[str, ...]) -> dict[str, pd.Series]:
    """Parse feature fields numerically without treating invalid values as valid."""
    return {name: pd.to_numeric(frame[name], errors="coerce") for name in features}


def assess_eligibility(frame: pd.DataFrame) -> tuple[dict[str, pd.Series], dict[str, Any]]:
    """Build row masks and a disjoint count partition for both feature sets."""
    validate_source_dataset(frame)
    numeric = _numeric_columns(frame, FOUR_FEATURES)
    present = frame.loc[:, FOUR_FEATURES].notna()
    nonnumeric = pd.DataFrame(
        {
            name: frame[name].notna() & numeric[name].isna()
            for name in FOUR_FEATURES
        },
        index=frame.index,
    )
    finite = pd.DataFrame(
        {
            name: pd.Series(
                np.isfinite(numeric[name].to_numpy(dtype=np.float64, na_value=np.nan)),
                index=frame.index,
            )
            for name in FOUR_FEATURES
        },
        index=frame.index,
    )

    complete_four = present.all(axis=1)
    complete_three = frame.loc[:, THREE_FEATURES].notna().all(axis=1)
    finite_four = finite.all(axis=1)
    finite_three = finite.loc[:, THREE_FEATURES].all(axis=1)
    positive_radius = numeric["pl_rade"] > 0
    positive_period = numeric["pl_orbper"] > 0
    eligible_four = finite_four & positive_radius & positive_period
    eligible_three = finite_three & positive_radius & positive_period

    any_nonnumeric = nonnumeric.any(axis=1)
    any_nonfinite = (~finite).any(axis=1) & ~any_nonnumeric
    missing_any = ~complete_four
    finite_complete = complete_four & ~any_nonnumeric & ~any_nonfinite
    nonpositive_radius = finite_complete & ~positive_radius
    after_radius = finite_complete & positive_radius
    nonpositive_period = after_radius & ~positive_period
    step_counts = {
        "missing_one_or_more_features": int(missing_any.sum()),
        "nonnumeric_value_after_complete_case_check": int(
            (complete_four & any_nonnumeric).sum()
        ),
        "nonfinite_value_after_numeric_check": int(
            (complete_four & any_nonfinite).sum()
        ),
        "nonpositive_radius_after_finite_check": int(nonpositive_radius.sum()),
        "nonpositive_orbital_period_after_radius_check": int(nonpositive_period.sum()),
        "eligible_all_four_features": int(eligible_four.sum()),
    }
    if sum(step_counts.values()) != len(frame):
        raise AssertionError("Four-feature stepwise eligibility counts do not sum to source rows.")

    masks = {
        "complete_four": complete_four,
        "finite_four": finite_four,
        "eligible_four": eligible_four,
        "complete_three": complete_three,
        "finite_three": finite_three,
        "eligible_three": eligible_three,
    }
    counts: dict[str, Any] = {
        "source_records": int(len(frame)),
        "source_columns": int(frame.shape[1]),
        "all_four_fields_present": int(complete_four.sum()),
        "all_four_fields_finite_numeric": int(finite_four.sum()),
        "eligible_four_feature_records": int(eligible_four.sum()),
        "without_temperature_fields_present": int(complete_three.sum()),
        "without_temperature_fields_finite_numeric": int(finite_three.sum()),
        "eligible_without_temperature_sensitivity_records": int(eligible_three.sum()),
        "four_feature_stepwise_partition": step_counts,
        "review_only_domain_flags": {
            "nonpositive_equilibrium_temperature": int(
                (numeric["pl_eqt"].notna() & (numeric["pl_eqt"] <= 0)).sum()
            ),
            "negative_eccentricity": int(
                (numeric["pl_orbeccen"].notna() & (numeric["pl_orbeccen"] < 0)).sum()
            ),
            "eccentricity_at_least_one": int(
                (numeric["pl_orbeccen"].notna() & (numeric["pl_orbeccen"] >= 1)).sum()
            ),
            "eccentricity_zero_all_source_records": int(
                (numeric["pl_orbeccen"] == 0).sum()
            ),
            "eccentricity_zero_primary_cohort": int(
                ((numeric["pl_orbeccen"] == 0) & eligible_four).sum()
            ),
        },
    }
    return masks, counts


def _eligibility_reasons(frame: pd.DataFrame, eligible: pd.Series) -> pd.Series:
    """Explain why any source row is outside the four-feature cohort."""
    reasons: list[str] = []
    numeric = _numeric_columns(frame, FOUR_FEATURES)
    for position, (_, row) in enumerate(frame.iterrows()):
        if bool(eligible.iloc[position]):
            reasons.append("eligible")
            continue
        row_reasons: list[str] = []
        for name in FOUR_FEATURES:
            if pd.isna(row[name]):
                row_reasons.append(f"missing:{name}")
            elif pd.isna(numeric[name].iloc[position]):
                row_reasons.append(f"non_numeric:{name}")
            elif not np.isfinite(float(numeric[name].iloc[position])):
                row_reasons.append(f"non_finite:{name}")
        if pd.notna(numeric["pl_rade"].iloc[position]) and numeric["pl_rade"].iloc[position] <= 0:
            row_reasons.append("nonpositive:pl_rade")
        if pd.notna(numeric["pl_orbper"].iloc[position]) and numeric["pl_orbper"].iloc[position] <= 0:
            row_reasons.append("nonpositive:pl_orbper")
        reasons.append(";".join(row_reasons))
    return pd.Series(reasons, index=frame.index, dtype="string")


def _build_feature_view(
    frame: pd.DataFrame,
    eligible: pd.Series,
    *,
    include_temperature: bool,
) -> tuple[pd.DataFrame, StandardScaler]:
    """Transform eligible rows, fit one scaler, and retain raw physical fields."""
    positions = np.flatnonzero(eligible.to_numpy(dtype=bool))
    cohort = frame.iloc[positions].copy().reset_index(drop=True)

    transformed = pd.DataFrame(
        {
            "log10_pl_rade": np.log10(
                pd.to_numeric(cohort["pl_rade"], errors="raise").to_numpy(dtype=np.float64)
            ),
            "log10_pl_orbper": np.log10(
                pd.to_numeric(cohort["pl_orbper"], errors="raise").to_numpy(dtype=np.float64)
            ),
        }
    )
    if include_temperature:
        transformed["pl_eqt"] = pd.to_numeric(cohort["pl_eqt"], errors="raise").to_numpy(
            dtype=np.float64
        )
    transformed["pl_orbeccen"] = pd.to_numeric(
        cohort["pl_orbeccen"], errors="raise"
    ).to_numpy(dtype=np.float64)

    scaler = StandardScaler()
    standardized = scaler.fit_transform(transformed.to_numpy(dtype=np.float64))
    output = cohort.loc[:, [*IDENTIFIERS, *PHYSICAL_FEATURES]].copy()
    output.insert(0, "source_data_record_number", positions + 1)
    for feature_name in transformed.columns:
        output[feature_name] = transformed[feature_name].to_numpy()
    for index, feature_name in enumerate(transformed.columns):
        scaled_name = SCALED_FEATURES[feature_name]
        output[scaled_name] = standardized[:, index]

    if not np.isfinite(output.loc[:, list(transformed.columns)].to_numpy(dtype=np.float64)).all():
        raise AssertionError("Non-finite values remain after approved transformations.")
    return output, scaler


def prepare_frames(frame: pd.DataFrame) -> PreprocessingResult:
    """Prepare the master table and both experiments on the shared cohort."""
    validate_source_dataset(frame)
    masks, counts = assess_eligibility(frame)
    if counts["eligible_four_feature_records"] != EXPECTED_PRIMARY_RECORDS:
        raise ValueError(
            "The four-feature eligibility count differs from the approved cohort size "
            f"({counts['eligible_four_feature_records']} != {EXPECTED_PRIMARY_RECORDS})."
        )
    if counts["eligible_without_temperature_sensitivity_records"] != EXPECTED_WITHOUT_TEMPERATURE_RECORDS:
        raise ValueError(
            "The no-temperature sensitivity count differs from the audited size "
            f"({counts['eligible_without_temperature_sensitivity_records']} != "
            f"{EXPECTED_WITHOUT_TEMPERATURE_RECORDS})."
        )

    master = frame.copy()
    master.insert(0, "source_data_record_number", np.arange(1, len(frame) + 1))
    master["eligible_four_feature_clustering"] = masks["eligible_four"].to_numpy(dtype=bool)
    master["four_feature_eligibility_reason"] = _eligibility_reasons(
        frame, masks["eligible_four"]
    ).to_numpy()
    master["eligible_without_temperature_sensitivity"] = masks["eligible_three"].to_numpy(
        dtype=bool
    )

    primary_with, scaler_with = _build_feature_view(
        frame, masks["eligible_four"], include_temperature=True
    )
    primary_without, scaler_without = _build_feature_view(
        frame, masks["eligible_four"], include_temperature=False
    )
    if primary_with["pl_name"].tolist() != primary_without["pl_name"].tolist():
        raise AssertionError("Primary experiments do not contain identical planet IDs in order.")

    return PreprocessingResult(
        source=frame.copy(),
        master=master,
        with_temperature=primary_with,
        without_temperature=primary_without,
        scalers={"with_temperature": scaler_with, "without_temperature": scaler_without},
        eligibility=counts,
        masks=masks,
    )


def iqr_extreme_investigation(frame: pd.DataFrame, limit: int = 5) -> dict[str, Any]:
    """List IQR-flagged values and contextual raw measurements without filtering."""
    eligibility_masks, _ = assess_eligibility(frame)
    primary_eligible = eligibility_masks["eligible_four"].to_numpy(dtype=bool)
    investigations: dict[str, Any] = {}
    for feature in FOUR_FEATURES:
        values = pd.to_numeric(frame[feature], errors="coerce").to_numpy(
            dtype=np.float64, na_value=np.nan
        )
        finite_positions = np.flatnonzero(np.isfinite(values))
        finite_values = values[finite_positions]
        q1, q3 = np.quantile(finite_values, [0.25, 0.75])
        iqr = float(q3 - q1)
        lower_fence = float(q1 - 1.5 * iqr)
        upper_fence = float(q3 + 1.5 * iqr)

        def example(position: int) -> dict[str, Any]:
            row = frame.iloc[position]
            physical = {
                name: (None if pd.isna(row[name]) else float(row[name]))
                for name in PHYSICAL_FEATURES
            }
            return {
                "source_data_record_number": int(position + 1),
                "pl_name": str(row["pl_name"]),
                "hostname": str(row["hostname"]),
                "flagged_feature": feature,
                "value": float(values[position]),
                "iqr_flagged": bool(values[position] < lower_fence or values[position] > upper_fence),
                "eligible_four_feature_clustering": bool(primary_eligible[position]),
                "original_physical_measurements": physical,
            }

        low_positions = sorted(finite_positions, key=lambda position: values[position])[:limit]
        high_positions = sorted(
            finite_positions, key=lambda position: values[position], reverse=True
        )[:limit]
        investigations[feature] = {
            "unit": {
                "pl_rade": "Earth radii",
                "pl_orbper": "days",
                "pl_eqt": "K",
                "pl_orbeccen": "dimensionless",
            }[feature],
            "rule": "Review flag if below Q1 - 1.5*IQR or above Q3 + 1.5*IQR; no rows removed.",
            "q1": float(q1),
            "q3": float(q3),
            "iqr": iqr,
            "lower_fence": lower_fence,
            "upper_fence": upper_fence,
            "below_lower_fence_count": int((finite_values < lower_fence).sum()),
            "above_upper_fence_count": int((finite_values > upper_fence).sum()),
            "lowest_records": [example(int(position)) for position in low_positions],
            "highest_records": [example(int(position)) for position in high_positions],
        }
    return investigations
