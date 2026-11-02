# ExoAtlas Preprocessing Report

## Dataset overview

- Source snapshot: `PSCompPars_2026.10.30_13.47.46.csv` (2026-10-30).
- Source records and columns: **6,451** and **84**.
- SHA-256: `16bb38b253d375b49cdb286b45e38435746c74bfde10d3ba580199fa822b6c30`; it matches the approved snapshot and remained unchanged during the run: **True**.
- NASA `#` comment metadata was skipped while reading. The raw CSV was not modified.
- Every source row and source column remains in `data/processed/planets_master.csv`; the master adds eligibility indicators and reasons, but no cluster labels.

## Cohort eligibility and missing data

- Four-feature complete cases: **5,273**.
- Four features finite and numeric: **5,273**.
- Eligible for both primary experiments: **5,273**.
- Eligible without temperature (sensitivity flag only): **5,335**.
- Both primary experiments use the same 5,273 records in the same source order. The extra no-temperature-eligible records are not included in either primary matrix.
- No values are imputed. Ineligible planets remain in the master file and have a false eligibility indicator plus a reason.

| Four-feature eligibility step | Records |
|---|---:|
| missing one or more features | 1,178 |
| nonnumeric value after complete case check | 0 |
| nonfinite value after numeric check | 0 |
| nonpositive radius after finite check | 0 |
| nonpositive orbital period after radius check | 0 |
| eligible all four features | 5,273 |

The stepwise exclusion categories are disjoint and sum to the 6,451 source records. Missing values account for the 1,178 primary exclusions; no complete records were excluded for nonnumeric, non-finite, nonpositive-radius, or nonpositive-period values. Radius and period must be greater than zero because they are log transformed. Temperature and eccentricity have no additional review-domain violations in this snapshot. Eccentricity zeros are retained.

### Planned feature missingness

| Feature | Missing records | Missing percent | Raw zero values |
|---|---:|---:|---:|
| `pl_rade` | 50 | 0.775074% | 0 |
| `pl_orbper` | 354 | 5.487521% | 0 |
| `pl_eqt` | 540 | 8.370795% | 0 |
| `pl_orbeccen` | 1,068 | 16.555573% | 3,156 |

## Feature transformations

Experiment A uses `log10(pl_rade)`, `log10(pl_orbper)`, raw equilibrium temperature, and raw eccentricity. Experiment B uses the first two transformed features and raw eccentricity. The original physical columns remain unchanged in both output tables; experiment B also retains raw `pl_eqt` as context, but it is not among that experiment's model features.

Base-10 logs reduce the wide positive scale of radius and especially orbital period while preserving order among positive values. StandardScaler then centers each experiment's transformed feature columns and scales them to unit population variance so units and numeric ranges do not dominate by scale alone. Each experiment has its own fitted scaler because its feature set differs.

- Experiment A features: `scaled_log10_pl_rade, scaled_log10_pl_orbper, scaled_pl_eqt, scaled_pl_orbeccen`.
- Experiment B features: `scaled_log10_pl_rade, scaled_log10_pl_orbper, scaled_pl_orbeccen`.
- Eccentricity zero measurements preserved in the primary cohort: **3,144**.

## Extreme-value investigation

The 1.5×IQR rule is used only to flag statistical extremes for review. Flags are not proof of invalidity, and no rows were removed or changed. Tables list the five largest values per feature, with source record, planet and host identifiers, and all four original physical measurements.

| Feature | Source record | Planet | Host | Primary cohort | Flagged value | Radius | Period (days) | Equilibrium temp (K) | Eccentricity |
|---|---:|---|---|---|---:|---:|---:|---:|---:|
| `pl_rade` | 6183 | V2376 Ori b | V2376 Ori | False | 87.20587 (IQR) | 87.20587 | N/A | 2100 | N/A |
| `pl_rade` | 528 | HD 100546 b | HD 100546 | False | 77.3421 (IQR) | 77.3421 | N/A | 94.67 | N/A |
| `pl_rade` | 363 | GQ Lup b | GQ Lup | False | 33.6 (IQR) | 33.6 | N/A | 2650 | N/A |
| `pl_rade` | 143 | DH Tau b | DH Tau | False | 30.2643 (IQR) | 30.2643 | N/A | 2200 | N/A |
| `pl_rade` | 3497 | Kepler-1979 b | Kepler-1979 | True | 29.33 (IQR) | 29.33 | 18.508453 | 683 | 0 |
| `pl_orbper` | 101 | COCONUTS-2 b | COCONUTS-2 A | False | 4.02e+08 (IQR) | 12.576476 | 4.02e+08 | 493 | N/A |
| `pl_orbper` | 98 | CFHTWIR-Oph 98 b | CFHTWIR-Oph 98 A | False | 8040000 (IQR) | 20.848704 | 8040000 | 1800 | N/A |
| `pl_orbper` | 5172 | Oph 11 b | Oph 11 | False | 7300000 (IQR) | 12.3 | 7300000 | 2175 | N/A |
| `pl_orbper` | 6185 | VHS J125601.92-125723.9 b | VHS J125601.92-125723.9 | True | 5800000 (IQR) | 13.674956 | 5800000 | 1194 | 0.68 |
| `pl_orbper` | 6409 | b Cen AB b | b Cen A | False | 1790000 (IQR) | 12.4 | 1790000 | N/A | 0.4 |
| `pl_eqt` | 2158 | KOI-55 b | KOI-55 | False | 7777.78 (IQR) | 0.759 | 0.240104 | 7777.78 | N/A |
| `pl_eqt` | 2159 | KOI-55 c | KOI-55 | False | 6910.74 (IQR) | 0.867 | 0.342887 | 6910.74 | N/A |
| `pl_eqt` | 1971 | KELT-9 b | KELT-9 | True | 3921 (IQR) | 21.700587 | 1.4811235 | 3921 | 0 |
| `pl_eqt` | 5556 | TOI-2109 b | TOI-2109 | False | 3646 (IQR) | 15.098497 | 0.67247414 | 3646 | N/A |
| `pl_eqt` | 6276 | WASP-189 b | WASP-189 | True | 3353 (IQR) | 18.14734 | 2.724033 | 3353 | 0 |
| `pl_orbeccen` | 940 | HD 20782 b | HD 20782 | True | 0.95 (IQR) | 13.6 | 597.0643 | 253.34 | 0.95 |
| `pl_orbeccen` | 1070 | HD 28254 b | HD 28254 | True | 0.95 (IQR) | 13 | 1333 | 212.28 | 0.95 |
| `pl_orbeccen` | 1414 | HIP 66074 b | HIP 66074 | True | 0.948 (IQR) | 12.9 | 310.9 | 192.69 | 0.948 |
| `pl_orbeccen` | 5236 | TIC 241249530 b | TIC 241249530 | True | 0.9412 (IQR) | 13.293851 | 165.7719 | 438.94 | 0.9412 |
| `pl_orbeccen` | 1276 | HD 80606 b | HD 80606 | True | 0.93183 (IQR) | 11.567668 | 111.43676 | 405 | 0.93183 |

The largest orbital period is COCONUTS-2 b at 402,000,000 days (source record 101); it is an IQR review flag, but this row is outside the primary cohort because eccentricity is missing. Other largest values include V2376 Ori b at 87.20586985 Earth radii, KOI-55 b at 7,777.78 K, and eccentricities of 0.95 for HD 20782 b and HD 28254 b. The table marks which records enter the primary cohort. These values are unusual relative to the distribution; this audit cannot establish measurement validity.

No records violated the numeric or log-transform eligibility rules in this source. `pl_eqt <= 0`, negative eccentricity, and eccentricity >= 1 review counts are all zero. The many upper IQR flags, including long-period planets and high eccentricities, remain preserved and warrant source-level review before interpreting downstream clusters. StandardScaler is sensitive to extreme values.

## Outputs and reproducibility

- `data/processed/planets_master.csv`: 6,451 source rows and all 84 source columns, plus row provenance and eligibility columns.
- `data/processed/clustering_features_with_temp.csv`: 5,273 rows, retained identifiers and raw physical measurements, transformed columns, and standardized Experiment A features.
- `data/processed/clustering_features_without_temp.csv`: the same 5,273 identifiers in the same order, with raw `pl_eqt` retained only as a physical measurement.
- `artifacts/preprocessing/scaler_with_temp.joblib` and `scaler_without_temp.joblib`: separately fitted scaler objects with their feature order, means, variances, and scales recorded in this report.
- No clustering or supervised model was run.

## Decisions and unresolved scientific questions

Approved policy used here: complete cases for primary experiments; no imputation; preserve all observations in the master; positive radius and period for base-10 logs; preserve eccentricity zeros; keep raw physical columns; retain extreme values; and standardize each feature set separately.

Before clustering results are interpreted, review the very long orbital-period observations and other IQR flags against their source references. Decide how to discuss the influence of such observations on StandardScaler. This pipeline does not determine whether an extreme measurement is physically correct. Multi-planet hosts are also present in the source; whether later analysis should account for host-level dependence remains a modeling question.

The two primary feature matrices have identical planet identifiers in the same order: **True**.
