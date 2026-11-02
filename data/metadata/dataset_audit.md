# NASA PSCompPars Dataset Audit

Source: `PSCompPars_2026.10.30_13.47.46.csv` · snapshot date: 2026-10-30

## Dataset overview and integrity

- Records: **6,451**
- Columns: **84**
- Inferred pandas dtypes: float64: 70, int64: 5, str: 9
- SHA-256 before move: `16bb38b253d375b49cdb286b45e38435746c74bfde10d3ba580199fa822b6c30`
- SHA-256 after move: `16bb38b253d375b49cdb286b45e38435746c74bfde10d3ba580199fa822b6c30`
- Hash match: **True**
- Source path: `data/raw/PSCompPars_2026.10.30_13.47.46.csv`

The file was read with pandas while skipping NASA `#` comment metadata. The source CSV was not edited.

NASA comment metadata:

- This file was produced by the NASA Exoplanet Archive  http://exoplanetarchive.ipac.caltech.edu
- Fri Oct 30 13:47:46 2026
- 
- COLUMN pl_name:        Planet Name
- COLUMN hostname:       Host Name
- COLUMN sy_snum:        Number of Stars
- COLUMN sy_pnum:        Number of Planets
- COLUMN discoverymethod: Discovery Method
- COLUMN disc_year:      Discovery Year
- COLUMN disc_facility:  Discovery Facility
- COLUMN pl_controv_flag: Controversial Flag
- COLUMN pl_orbper:      Orbital Period [days]
- COLUMN pl_orbpererr1:  Orbital Period Upper Unc. [days]
- COLUMN pl_orbpererr2:  Orbital Period Lower Unc. [days]
- COLUMN pl_orbperlim:   Orbital Period Limit Flag
- COLUMN pl_orbsmax:     Orbit Semi-Major Axis [au]
- COLUMN pl_orbsmaxerr1: Orbit Semi-Major Axis Upper Unc. [au]
- COLUMN pl_orbsmaxerr2: Orbit Semi-Major Axis Lower Unc. [au]
- COLUMN pl_orbsmaxlim:  Orbit Semi-Major Axis Limit Flag
- COLUMN pl_rade:        Planet Radius [Earth Radius]
- COLUMN pl_radeerr1:    Planet Radius Upper Unc. [Earth Radius]
- COLUMN pl_radeerr2:    Planet Radius Lower Unc. [Earth Radius]
- COLUMN pl_radelim:     Planet Radius Limit Flag
- COLUMN pl_radj:        Planet Radius [Jupiter Radius]
- COLUMN pl_radjerr1:    Planet Radius Upper Unc. [Jupiter Radius]
- COLUMN pl_radjerr2:    Planet Radius Lower Unc. [Jupiter Radius]
- COLUMN pl_radjlim:     Planet Radius Limit Flag
- COLUMN pl_bmasse:      Planet Mass or Mass*sin(i) [Earth Mass]
- COLUMN pl_bmasseerr1:  Planet Mass or Mass*sin(i) [Earth Mass] Upper Unc.
- COLUMN pl_bmasseerr2:  Planet Mass or Mass*sin(i) [Earth Mass] Lower Unc.
- COLUMN pl_bmasselim:   Planet Mass or Mass*sin(i) [Earth Mass] Limit Flag
- COLUMN pl_bmassj:      Planet Mass or Mass*sin(i) [Jupiter Mass]
- COLUMN pl_bmassjerr1:  Planet Mass or Mass*sin(i) [Jupiter Mass] Upper Unc.
- COLUMN pl_bmassjerr2:  Planet Mass or Mass*sin(i) [Jupiter Mass] Lower Unc.
- COLUMN pl_bmassjlim:   Planet Mass or Mass*sin(i) [Jupiter Mass] Limit Flag
- COLUMN pl_bmassprov:   Planet Mass or Mass*sin(i) Provenance
- COLUMN pl_orbeccen:    Eccentricity
- COLUMN pl_orbeccenerr1: Eccentricity Upper Unc.
- COLUMN pl_orbeccenerr2: Eccentricity Lower Unc.
- COLUMN pl_orbeccenlim: Eccentricity Limit Flag
- COLUMN pl_insol:       Insolation Flux [Earth Flux]
- COLUMN pl_insolerr1:   Insolation Flux Upper Unc. [Earth Flux]
- COLUMN pl_insolerr2:   Insolation Flux Lower Unc. [Earth Flux]
- COLUMN pl_insollim:    Insolation Flux Limit Flag
- COLUMN pl_eqt:         Equilibrium Temperature [K]
- COLUMN pl_eqterr1:     Equilibrium Temperature Upper Unc. [K]
- COLUMN pl_eqterr2:     Equilibrium Temperature Lower Unc. [K]
- COLUMN pl_eqtlim:      Equilibrium Temperature Limit Flag
- COLUMN ttv_flag:       Data show Transit Timing Variations
- COLUMN st_spectype:    Spectral Type
- COLUMN st_teff:        Stellar Effective Temperature [K]
- COLUMN st_tefferr1:    Stellar Effective Temperature Upper Unc. [K]
- COLUMN st_tefferr2:    Stellar Effective Temperature Lower Unc. [K]
- COLUMN st_tefflim:     Stellar Effective Temperature Limit Flag
- COLUMN st_rad:         Stellar Radius [Solar Radius]
- COLUMN st_raderr1:     Stellar Radius Upper Unc. [Solar Radius]
- COLUMN st_raderr2:     Stellar Radius Lower Unc. [Solar Radius]
- COLUMN st_radlim:      Stellar Radius Limit Flag
- COLUMN st_mass:        Stellar Mass [Solar mass]
- COLUMN st_masserr1:    Stellar Mass Upper Unc. [Solar mass]
- COLUMN st_masserr2:    Stellar Mass Lower Unc. [Solar mass]
- COLUMN st_masslim:     Stellar Mass Limit Flag
- COLUMN st_met:         Stellar Metallicity [dex]
- COLUMN st_meterr1:     Stellar Metallicity Upper Unc. [dex]
- COLUMN st_meterr2:     Stellar Metallicity Lower Unc. [dex]
- COLUMN st_metlim:      Stellar Metallicity Limit Flag
- COLUMN st_metratio:    Stellar Metallicity Ratio
- COLUMN st_logg:        Stellar Surface Gravity [log10(cm/s**2)]
- COLUMN st_loggerr1:    Stellar Surface Gravity Upper Unc. [log10(cm/s**2)]
- COLUMN st_loggerr2:    Stellar Surface Gravity Lower Unc. [log10(cm/s**2)]
- COLUMN st_logglim:     Stellar Surface Gravity Limit Flag
- COLUMN rastr:          RA [sexagesimal]
- COLUMN ra:             RA [deg]
- COLUMN decstr:         Dec [sexagesimal]
- COLUMN dec:            Dec [deg]
- COLUMN sy_dist:        Distance [pc]
- COLUMN sy_disterr1:    Distance [pc] Upper Unc
- COLUMN sy_disterr2:    Distance [pc] Lower Unc
- COLUMN sy_vmag:        V (Johnson) Magnitude
- COLUMN sy_vmagerr1:    V (Johnson) Magnitude Upper Unc
- COLUMN sy_vmagerr2:    V (Johnson) Magnitude Lower Unc
- COLUMN sy_kmag:        Ks (2MASS) Magnitude
- COLUMN sy_kmagerr1:    Ks (2MASS) Magnitude Upper Unc
- COLUMN sy_kmagerr2:    Ks (2MASS) Magnitude Lower Unc
- COLUMN sy_gaiamag:     Gaia Magnitude
- COLUMN sy_gaiamagerr1: Gaia Magnitude Upper Unc
- COLUMN sy_gaiamagerr2: Gaia Magnitude Lower Unc
- 

## Schema and missing values

Missingness is calculated from pandas' parsed source values. Percentages use all dataset records as the denominator.

| Column | Inferred dtype | Missing | Missing % |
|---|---:|---:|---:|
| pl_name | str | 0 | 0% |
| hostname | str | 0 | 0% |
| sy_snum | int64 | 0 | 0% |
| sy_pnum | int64 | 0 | 0% |
| discoverymethod | str | 0 | 0% |
| disc_year | int64 | 0 | 0% |
| disc_facility | str | 0 | 0% |
| pl_controv_flag | int64 | 0 | 0% |
| pl_orbper | float64 | 354 | 5.48752% |
| pl_orbpererr1 | float64 | 850 | 13.1763% |
| pl_orbpererr2 | float64 | 850 | 13.1763% |
| pl_orbperlim | float64 | 354 | 5.48752% |
| pl_orbsmax | float64 | 495 | 7.67323% |
| pl_orbsmaxerr1 | float64 | 2,429 | 37.6531% |
| pl_orbsmaxerr2 | float64 | 2,429 | 37.6531% |
| pl_orbsmaxlim | float64 | 494 | 7.65773% |
| pl_rade | float64 | 50 | 0.775074% |
| pl_radeerr1 | float64 | 1,974 | 30.5999% |
| pl_radeerr2 | float64 | 1,974 | 30.5999% |
| pl_radelim | float64 | 50 | 0.775074% |
| pl_radj | float64 | 50 | 0.775074% |
| pl_radjerr1 | float64 | 1,974 | 30.5999% |
| pl_radjerr2 | float64 | 1,974 | 30.5999% |
| pl_radjlim | float64 | 50 | 0.775074% |
| pl_bmasse | float64 | 30 | 0.465044% |
| pl_bmasseerr1 | float64 | 3,343 | 51.8214% |
| pl_bmasseerr2 | float64 | 3,343 | 51.8214% |
| pl_bmasselim | float64 | 30 | 0.465044% |
| pl_bmassj | float64 | 30 | 0.465044% |
| pl_bmassjerr1 | float64 | 3,343 | 51.8214% |
| pl_bmassjerr2 | float64 | 3,343 | 51.8214% |
| pl_bmassjlim | float64 | 30 | 0.465044% |
| pl_bmassprov | str | 0 | 0% |
| pl_orbeccen | float64 | 1,068 | 16.5556% |
| pl_orbeccenerr1 | float64 | 4,507 | 69.8651% |
| pl_orbeccenerr2 | float64 | 4,507 | 69.8651% |
| pl_orbeccenlim | float64 | 1,068 | 16.5556% |
| pl_insol | float64 | 596 | 9.23888% |
| pl_insolerr1 | float64 | 1,681 | 26.058% |
| pl_insolerr2 | float64 | 1,681 | 26.058% |
| pl_insollim | float64 | 596 | 9.23888% |
| pl_eqt | float64 | 540 | 8.37079% |
| pl_eqterr1 | float64 | 3,694 | 57.2624% |
| pl_eqterr2 | float64 | 3,694 | 57.2624% |
| pl_eqtlim | float64 | 540 | 8.37079% |
| ttv_flag | int64 | 0 | 0% |
| st_spectype | str | 4,041 | 62.6415% |
| st_teff | float64 | 307 | 4.75895% |
| st_tefferr1 | float64 | 614 | 9.5179% |
| st_tefferr2 | float64 | 614 | 9.5179% |
| st_tefflim | float64 | 307 | 4.75895% |
| st_rad | float64 | 332 | 5.14649% |
| st_raderr1 | float64 | 606 | 9.39389% |
| st_raderr2 | float64 | 607 | 9.40939% |
| st_radlim | float64 | 332 | 5.14649% |
| st_mass | float64 | 9 | 0.139513% |
| st_masserr1 | float64 | 287 | 4.44892% |
| st_masserr2 | float64 | 288 | 4.46442% |
| st_masslim | float64 | 9 | 0.139513% |
| st_met | float64 | 699 | 10.8355% |
| st_meterr1 | float64 | 985 | 15.269% |
| st_meterr2 | float64 | 985 | 15.269% |
| st_metlim | float64 | 699 | 10.8355% |
| st_metratio | str | 716 | 11.0991% |
| st_logg | float64 | 337 | 5.224% |
| st_loggerr1 | float64 | 626 | 9.70392% |
| st_loggerr2 | float64 | 626 | 9.70392% |
| st_logglim | float64 | 337 | 5.224% |
| rastr | str | 0 | 0% |
| ra | float64 | 0 | 0% |
| decstr | str | 0 | 0% |
| dec | float64 | 0 | 0% |
| sy_dist | float64 | 28 | 0.434041% |
| sy_disterr1 | float64 | 138 | 2.1392% |
| sy_disterr2 | float64 | 138 | 2.1392% |
| sy_vmag | float64 | 313 | 4.85196% |
| sy_vmagerr1 | float64 | 321 | 4.97597% |
| sy_vmagerr2 | float64 | 326 | 5.05348% |
| sy_kmag | float64 | 299 | 4.63494% |
| sy_kmagerr1 | float64 | 336 | 5.2085% |
| sy_kmagerr2 | float64 | 347 | 5.37901% |
| sy_gaiamag | float64 | 358 | 5.54953% |
| sy_gaiamagerr1 | float64 | 358 | 5.54953% |
| sy_gaiamagerr2 | float64 | 358 | 5.54953% |

## Duplicate checks

- Planet identifier column: `pl_name`.
- Duplicate identifier groups: 0.
- Rows in duplicate identifier groups: 0.
- Exact duplicate record groups: 0.
- Exact duplicate rows beyond the first copy: 0.

## Planned feature quality

Descriptive statistics use finite numeric values only. IQR flags use the 1.5×IQR rule for review; they do not remove records.

| Feature (unit) | dtype | Missing | Non-numeric | +∞ | −∞ | Zero | Negative | Min | Mean | Q1 | Median | Q3 | Max | Sample SD | IQR flags |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pl_rade (Earth radii) | float64 | 50 | 0 | 0 | 0 | 0 | 0 | 0.3098 | 5.84466 | 1.85 | 2.86 | 11.9 | 87.2059 | 5.40044 | 5 |
| pl_orbper (days) | float64 | 354 | 0 | 0 | 0 | 0 | 0 | 0.0907063 | 70,216.2 | 4.28818 | 10.6413 | 37.9933 | 4.02e+08 | 5.15076e+06 | 1057 |
| pl_eqt (K) | float64 | 540 | 0 | 0 | 0 | 0 | 0 | 1.48 | 836.377 | 486.185 | 758 | 1,095 | 7,777.78 | 495.75 | 132 |
| pl_orbeccen (dimensionless) | float64 | 1068 | 0 | 0 | 0 | 3156 | 0 | 0 | 0.0791066 | 0 | 0 | 0.09 | 0.95 | 0.152438 | 671 |

### Distribution quantiles (raw units)

| Feature (unit) | P05 | P10 | Q1 / P25 | Median / P50 | Q3 / P75 | P90 | P95 | P99 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pl_rade (Earth radii) | 1.08 | 1.28 | 1.85 | 2.86 | 11.9 | 13.6 | 14.3 | 18.2707 |
| pl_orbper (days) | 1.55397 | 2.45402 | 4.28818 | 10.6413 | 37.9933 | 435.78 | 1,536.9 | 13,125.4 |
| pl_eqt (K) | 183.09 | 288 | 486.185 | 758 | 1,095 | 1,513 | 1,742 | 2,249 |
| pl_orbeccen (dimensionless) | 0 | 0 | 0 | 0 | 0.09 | 0.27 | 0.4184 | 0.73 |

### Extreme-value review flags

- `pl_rade`: 0 below the lower fence and 5 above the upper fence.
  Examples: V2376 Ori b=87.2059 (record 6183); HD 100546 b=77.3421 (record 528); GQ Lup b=33.6 (record 363); DH Tau b=30.2643 (record 143); Kepler-1979 b=29.33 (record 3497).
- `pl_orbper`: 0 below the lower fence and 1,057 above the upper fence.
  Examples: COCONUTS-2 b=4.02e+08 (record 101); CFHTWIR-Oph 98 b=8.04e+06 (record 98); Oph 11 b=7.3e+06 (record 5172); VHS J125601.92-125723.9 b=5.8e+06 (record 6185); b Cen AB b=1.79e+06 (record 6409).
- `pl_eqt`: 0 below the lower fence and 132 above the upper fence.
  Examples: KOI-55 b=7,777.78 (record 2158); KOI-55 c=6,910.74 (record 2159); KELT-9 b=3,921 (record 1971); TOI-2109 b=3,646 (record 5556); WASP-189 b=3,353 (record 6276).
- `pl_orbeccen`: 0 below the lower fence and 671 above the upper fence.
  Examples: HD 20782 b=0.95 (record 940); HD 28254 b=0.95 (record 1070); HIP 66074 b=0.948 (record 1414); TIC 241249530 b=0.9412 (record 5236); HD 80606 b=0.93183 (record 1276).

## Discovery metadata distributions

### `discoverymethod`

| Value | Records | Percent |
|---|---:|---:|
| Transit | 4,785 | 74.1745% |
| Radial Velocity | 1,204 | 18.6638% |
| Microlensing | 292 | 4.52643% |
| Imaging | 98 | 1.51914% |
| Transit Timing Variations | 29 | 0.449543% |
| Eclipse Timing Variations | 17 | 0.263525% |
| Orbital Brightness Modulation | 9 | 0.139513% |
| Pulsar Timing | 8 | 0.124012% |
| Astrometry | 6 | 0.093009% |
| Pulsation Timing Variations | 2 | 0.031003% |
| Disk Kinematics | 1 | 0.015501% |

### `pl_bmassprov`

| Value | Records | Percent |
|---|---:|---:|
| M-R relationship | 3,035 | 47.047% |
| Mass | 2,477 | 38.3971% |
| Msini | 924 | 14.3234% |
| Msin(i)/sin(i) | 15 | 0.232522% |

### `disc_year`

Finite numeric records: 6,451; missing: 0; non-numeric: 0.
Range: 1,992–2,026; median: 2,016; Q1: 2,014; Q3: 2,021; sample SD: 5.20251.

| Discovery year | Records |
|---:|---:|
| 1992 | 2 |
| 1994 | 1 |
| 1995 | 1 |
| 1996 | 6 |
| 1997 | 1 |
| 1998 | 6 |
| 1999 | 13 |
| 2000 | 16 |
| 2001 | 12 |
| 2002 | 29 |
| 2003 | 22 |
| 2004 | 27 |
| 2005 | 36 |
| 2006 | 32 |
| 2007 | 52 |
| 2008 | 62 |
| 2009 | 87 |
| 2010 | 93 |
| 2011 | 141 |
| 2012 | 144 |
| 2013 | 128 |
| 2014 | 872 |
| 2015 | 155 |
| 2016 | 1,504 |
| 2017 | 152 |
| 2018 | 308 |
| 2019 | 194 |
| 2020 | 234 |
| 2021 | 564 |
| 2022 | 367 |
| 2023 | 323 |
| 2024 | 260 |
| 2025 | 246 |
| 2026 | 361 |

## Host-star relationships

- Records with a hostname: 6,451; without one: 0.
- Unique host stars: 4,847.
- Hosts with multiple planet records: 1,069.
- Planet records in those multi-planet systems: 2,673 (41.4354% of named-host records).

| Planets per host | Number of hosts |
|---:|---:|
| 1 | 3,778 |
| 2 | 720 |
| 3 | 223 |
| 4 | 83 |
| 5 | 29 |
| 6 | 12 |
| 7 | 1 |
| 8 | 1 |

Largest multi-planet hosts:

- `KOI-351`: 8 planet records.
- `TRAPPIST-1`: 7 planet records.
- `HD 10180`: 6 planet records.
- `HD 110067`: 6 planet records.
- `HD 191939`: 6 planet records.
- `HD 219134`: 6 planet records.
- `HD 34445`: 6 planet records.
- `HIP 41378`: 6 planet records.
- `K2-138`: 6 planet records.
- `Kepler-11`: 6 planet records.
- `Kepler-20`: 6 planet records.
- `Kepler-80`: 6 planet records.
- `TOI-1136`: 6 planet records.
- `TOI-178`: 6 planet records.
- `55 Cnc`: 5 planet records.
- `GJ 667 C`: 5 planet records.
- `HD 108236`: 5 planet records.
- `HD 134606`: 5 planet records.
- `HD 158259`: 5 planet records.
- `HD 23472`: 5 planet records.

## Clustering eligibility

The all-four-feature log-eligible count requires all four fields to be present, finite numeric values, and requires positive radius and orbital period for `log10`. Eccentricity zero is retained. `pl_eqt <= 0` and eccentricity outside `[0, 1)` are review flags only, not silent filters.

- All four fields present: **5,273** / 6,451.
- All four fields finite and numeric: **5,273**.
- Eligible for the proposed all-four-feature transforms: **5,273**.

Stepwise partition (rows at each step are assigned once; counts sum to the source total):

| Step | Records |
|---|---:|
| Missing one or more required features | 1,178 |
| Nonnumeric value among complete rows | 0 |
| Infinite value among otherwise numeric complete rows | 0 |
| Nonpositive radius among finite complete rows | 0 |
| Nonpositive period after positive-radius rule | 0 |
| Eligible with all four features | 5,273 |

Independent rule counts can overlap:

- `any_missing_required_feature`: 1,178 records.
- `any_nonnumeric_required_feature`: 0 records.
- `any_infinite_required_feature`: 0 records.
- `nonpositive_radius`: 0 records.
- `nonpositive_orbital_period`: 0 records.

Without `pl_eqt`, the finite-and-log-eligible count for `pl_rade`, `pl_orbper`, and `pl_orbeccen` is **5,335** (all required fields present: 5,335; finite numeric: 5,335).

Review-only domain flags, not used to reduce the eligibility count:

- `pl_rade_nonpositive`: 0 records.
- `pl_orbper_nonpositive`: 0 records.
- `pl_eqt_nonpositive`: 0 records.
- `pl_orbeccen_negative`: 0 records.
- `pl_orbeccen_at_least_1`: 0 records.

## Preprocessing decisions requiring approval

- Decide how missing values will be handled, and compare the all-four-feature cohort with the cohort that omits equilibrium temperature. No values were imputed.
- Confirm that only positive `pl_rade` and `pl_orbper` values should enter the log-transformed feature space. These are excluded from the reported transform-eligible count, but remain in the source and audit.
- Review nonpositive equilibrium temperatures and eccentricities outside `[0, 1)` against archive documentation before deciding whether any should be excluded. They remain in the audit and were not silently removed.
- Review the IQR-flagged extremes and any duplicate identifiers/records. IQR flags are descriptive and no extremes or duplicates were deleted.
- Decide whether discovery-method and host-star group structure should influence later comparisons. These distributions are descriptive and do not establish causal effects.

No imputation, log transformation, standardization, model training, or source-data modification was performed.
