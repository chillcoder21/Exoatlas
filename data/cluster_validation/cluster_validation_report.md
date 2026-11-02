# ExoAtlas — Cluster Validation Report

## Scope and inputs

This validation examined the NASA Exoplanet Archive PSCompPars snapshot dated 2026-10-30. The source contains 6,451 records and 84 columns. Both saved K=4 candidates use the same 5,273 unique planets, joined to the source by `pl_name`.

Candidate A uses the existing four-feature standardized matrix (log10 radius, log10 orbital period, raw equilibrium temperature, raw eccentricity). Candidate B uses the existing three-feature matrix (log10 radius, log10 orbital period, raw eccentricity). This validation reads the saved seed-42 assignments and feature matrices; it does not refit K-means, alter preprocessing, or modify observations.

## K=4 physical profiles

All values below are original NASA physical measurements. Each range is the observed minimum to maximum; full mean, sample standard deviation, quartiles and IQR are in `cluster_distribution_validation.csv`. A median difference by itself does not establish a distinct planet population.

### Candidate A — four features including temperature

| Cluster ID | Planets | Radius median [min, max] (R⊕) | Period median [min, max] (days) | Temperature median [min, max] (K) | Eccentricity median [min, max] |
|---:|---:|---:|---:|---:|---:|
| 0 | 871 (16.52%) | 12.8 [0.982, 22] | 654 [2.43, 5.8e+06] | 294 [24.4, 1.61e+03] | 0.24 [0, 0.95] |
| 1 | 1,361 (25.81%) | 1.54 [0.31, 4.98] | 4.29 [0.18, 37.3] | 1.09e+03 [450, 3.19e+03] | 0 [0, 0.549] |
| 2 | 2,223 (42.16%) | 2.57 [0.37, 14.3] | 19.7 [1.41, 704] | 579 [148, 1.1e+03] | 0 [0, 0.47] |
| 3 | 818 (15.51%) | 13.2 [2.56, 29.3] | 3.66 [0.654, 184] | 1.43e+03 [593, 3.92e+03] | 0.017 [0, 0.6] |

### Candidate B — three features excluding temperature

| Cluster ID | Planets | Radius median [min, max] (R⊕) | Period median [min, max] (days) | Temperature median [min, max] (K) | Eccentricity median [min, max] |
|---:|---:|---:|---:|---:|---:|
| 0 | 3,339 (63.32%) | 2.12 [0.31, 5.99] | 10.4 [0.18, 510] | 758 [148, 3.19e+03] | 0 [0, 0.44] |
| 1 | 341 (6.47%) | 12.4 [0.982, 16.8] | 290 [1.69, 5.8e+06] | 349 [53.8, 2.01e+03] | 0.5 [0.3, 0.95] |
| 2 | 643 (12.19%) | 12.9 [1.81, 22] | 622 [41.3, 1.17e+05] | 310 [24.4, 1.61e+03] | 0.13 [0, 0.401] |
| 3 | 950 (18.02%) | 12.7 [3.89, 29.3] | 3.98 [0.654, 77.5] | 1.31e+03 [163, 3.92e+03] | 0.02 [0, 0.39] |

For radius, orbital period, and temperature, the supplied distribution plots use logarithmic horizontal axes because their positive values span broad ranges. Histogram fractions are computed from original measurements; eccentricity is plotted on a linear axis and zeros are retained.

## K=4 separation and overlap

The full-cohort Euclidean silhouette is 0.3413 for Candidate A and 0.4904 for Candidate B. Silhouette is a geometric diagnostic in the standardized input space, not scientific validation by itself.

Per-cluster mean silhouettes and negative-silhouette counts:

| Candidate | Cluster | Mean silhouette | Negative observations | Negative (%) |
|---|---:|---:|---:|---:|
| A — with temperature | 0 | 0.2828 | 85 | 9.76% |
| A — with temperature | 1 | 0.3199 | 1 | 0.07% |
| A — with temperature | 2 | 0.3474 | 14 | 0.63% |
| A — with temperature | 3 | 0.4224 | 19 | 2.32% |
| B — without temperature | 0 | 0.5130 | 6 | 0.18% |
| B — without temperature | 1 | 0.2456 | 53 | 15.54% |
| B — without temperature | 2 | 0.4461 | 11 | 1.71% |
| B — without temperature | 3 | 0.5286 | 1 | 0.11% |
Candidate A: cluster 0 has the lowest cluster-average silhouette (0.2828) and 85 negative-silhouette members (9.76% of that cluster).
Candidate B: cluster 1 has the lowest cluster-average silhouette (0.2456) and 53 negative-silhouette members (15.54% of that cluster).

Pairwise centroid distances use the exact standardized K-means input space. Larger distances indicate more separated centroids, but do not imply non-overlapping observations. Binned univariate overlap coefficients range from 0 (no shared bin mass) to 1 (identical binned distributions); binning is shared across clusters within each feature. These one-dimensional coefficients complement, and do not replace, multivariate diagnostics.

**Candidate A centroid distances (ascending):** C1–C2 1.571; C1–C3 2.313; C2–C3 2.605; C0–C2 2.903; C0–C3 3.654; C0–C1 4.085.
Highest binned 1-D overlaps in Candidate A: C1–C2 pl_orbeccen=0.86; C2–C3 pl_orbeccen=0.75; C1–C3 pl_orbper=0.75; C1–C3 pl_eqt=0.63.

**Candidate B centroid distances (ascending):** C0–C3 1.955; C2–C3 2.490; C1–C2 2.716; C0–C2 2.893; C1–C3 3.710; C0–C1 4.089.
Highest binned 1-D overlaps in Candidate B: C1–C2 pl_eqt=0.76; C1–C2 pl_rade=0.74; C0–C3 pl_orbeccen=0.68; C1–C2 pl_orbper=0.64.

The lowest cluster-average silhouette identifies the group with the weakest average geometric assignment; its negative-silhouette share identifies observations closer, on average, to another cluster. Full per-planet values are in `cluster_silhouette_validation.csv`. No observations were removed based on these diagnostics.

## Discovery-method composition

Overall method counts in the full source and the 5,273-planet cohort are shown below. Candidate A and B use the same overall cohort methods, but cluster composition can differ.

| Discovery method | Full source n (%) | Primary cohort n (%) |
|---|---:|---:|
| Transit | 4,785 (74.17%) | 4,133 (78.38%) |
| Radial Velocity | 1,204 (18.66%) | 1,089 (20.65%) |
| Microlensing | 292 (4.53%) | 1 (0.02%) |
| Imaging | 98 (1.52%) | 16 (0.30%) |
| Transit Timing Variations | 29 (0.45%) | 22 (0.42%) |
| Eclipse Timing Variations | 17 (0.26%) | 7 (0.13%) |
| Orbital Brightness Modulation | 9 (0.14%) | 1 (0.02%) |
| Pulsar Timing | 8 (0.12%) | 0 (0.00%) |
| Astrometry | 6 (0.09%) | 3 (0.06%) |
| Pulsation Timing Variations | 2 (0.03%) | 1 (0.02%) |
| Disk Kinematics | 1 (0.02%) | 0 (0.00%) |

Cluster-by-method counts and within-cluster / within-method percentages are in the three discovery-method CSVs. Dominant method composition by cluster:

| Candidate | Cluster | Most common discovery method | Share within cluster |
|---|---:|---|---:|
| A — with temperature | 0 | Radial Velocity | 83.47% |
| A — with temperature | 1 | Transit | 96.40% |
| A — with temperature | 2 | Transit | 88.62% |
| A — with temperature | 3 | Transit | 91.08% |
| B — without temperature | 0 | Transit | 92.45% |
| B — without temperature | 1 | Radial Velocity | 65.98% |
| B — without temperature | 2 | Radial Velocity | 81.65% |
| B — without temperature | 3 | Transit | 89.37% |

| Candidate | n | χ² | df | p-value | Cramér’s V | Expected cells <5 | Expected cells <1 | Heuristic met? |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| A — with temperature | 5,273 | 2771.42 | 24 | <5e-324 (float64 underflow) | 0.419 | 25/36 (69.4%) | 15 | No |
| B — without temperature | 5,273 | 2568.53 | 24 | <5e-324 (float64 underflow) | 0.403 | 26/36 (72.2%) | 17 | No |

Discovery methods have different detection sensitivities and survey selection effects. The confirmed-planet catalogue is not an unbiased sample of planetary systems. These tests describe association only; they do not imply that discovery method causes a planet’s properties or cluster membership.

The Pearson chi-square asymptotic p-value should not be overinterpreted when expected-count assumptions fail. Rare method categories were retained rather than pooled; use the reported Cramér’s V and counts descriptively and consider an approved category-handling or exact/resampling analysis if inferential claims are needed.

## Temperature-inclusion comparison

The adjusted Rand index between the K=4 partitions is **0.4563**. After one-to-one cluster alignment by maximum membership overlap, 1,956 planets (37.09%) change matched cluster membership; the changed planet identifiers are in `temperature_feature_membership_changes.csv`.

Cluster labels are aligned by the Hungarian assignment on shared membership, not by their numeric IDs. The comparison CSV contains the full 4×4 membership-overlap matrix as well as matched-pair Jaccard overlap and original-unit median differences.

| With-temperature cluster | Without-temperature C0 | C1 | C2 | C3 |
|---:|---:|---:|---:|---:|
| 0 | 1 | 302 | 554 | 14 |
| 1 | 1,352 | 5 | 0 | 4 |
| 2 | 1,975 | 16 | 83 | 149 |
| 3 | 11 | 18 | 6 | 783 |

The overlap pattern indicates more than a small boundary shift: Candidate A clusters 1 and 2 contribute 1,352 and 1,975 planets, respectively, to Candidate B cluster 0. Temperature inclusion separates those two groups in the four-feature partition, while the three-feature solution largely combines them. The matched A1↔B1 pair has only 5 shared planets, so that forced one-to-one match should not be read as a physical equivalence. This is a descriptive partition comparison, not evidence that temperature causes a planetary class.
Among the four one-to-one membership-matched cluster pairs, discovery-method composition has a mean total-variation distance of 0.189 (maximum 0.668); 0 means identical method proportions and 1 means disjoint compositions. This is descriptive and inherits the survey-selection limitations above.

## Four-feature K choice: K=2–5

| K | Silhouette | Inertia | Cluster sizes | Centroid distances (min–max) | Median 1-D overlap | Stability ARI mean ± SD | Iterations |
|---:|---:|---:|---|---:|---:|---:|---:|
| 2 | 0.4587 | 13320.5 | 4269, 1004 | 3.09–3.09 | 0.29 | 1.0000 ± 0.0000 | 18 |
| 3 | 0.4227 | 9371.6 | 3287, 953, 1033 | 2.25–3.72 | 0.29 | 0.9957 ± 0.0037 | 10 |
| 4 | 0.3413 | 7557.5 | 871, 1361, 2223, 818 | 1.57–4.08 | 0.23 | 0.9867 ± 0.0071 | 7 |
| 5 | 0.3587 | 6062.3 | 811, 2270, 322, 1200, 670 | 1.57–4.84 | 0.21 | 0.9893 ± 0.0063 | 15 |

For the four-feature experiment, K=2 has the highest silhouette among K=2–5. K=4 lowers silhouette substantially relative to K=2 and K=3, while K=5 improves slightly over K=4. Across K, all candidate partitions are stable across the tested initializations; stability does not distinguish K=4. The centroid-distance and binned-overlap summaries add geometric/profile evidence but are not directly equivalent to astronomical separation.

Original-unit profiles suggest K=3 adds a hot, short-period, large-radius group to the broad K=2 split. K=4 further divides the smaller-radius population into a hotter, shorter-period group (median radius 1.54 R⊕, median period 4.29 days, median temperature 1,086 K) and a cooler/intermediate group (2.57 R⊕, 19.67 days, 579 K). At K=5, a 322-planet group has median eccentricity 0.512, compared with 0.129 for another large-radius, longer-period group; this is a plausible exploratory distinction, while the remaining profiles also shift. These are summaries of partitions, not claims of validated classes. Cluster membership transitions and physical medians by K are included in `k_selection_comparison.csv`.

### Recommendation

K=4 is defensible as an exploratory view, but the current evidence is not strong enough to freeze it as the primary scientific configuration. Its lower four-feature silhouette than K=2/K=3, the slight K=5 improvement, and the strong sensitivity to temperature leave the preferred granularity unresolved. Keep K=2 and K=3 as simpler references, retain K=5 as a refinement comparison, and request scientific review of the original-unit profiles and discovery-selection effects before promoting any K. This is a recommendation, not an automatic model-selection decision.

## Integrity, plots, and limitations

The raw source and preprocessing inputs were byte-identical before and after validation: **True**. Source SHA-256: `16bb38b253d375b49cdb286b45e38435746c74bfde10d3ba580199fa822b6c30`. No values were deleted, imputed, or transformed in saved source/preprocessing data; no new clustering model or supervised model was trained.

Full-source extreme-value context (extremes may not all belong to the primary cohort):

| Feature | Units | Minimum planet (value) | Maximum planet (value) |
|---|---|---|---|
| pl_rade | Earth radii | `Kepler-37 b` (0.3098) | `V2376 Ori b` (87.2059) |
| pl_orbper | days | `PSR J1719-1438 b` (0.0907063) | `COCONUTS-2 b` (4.02e+08) |
| pl_eqt | K | `GJ 900 b` (1.48) | `KOI-55 b` (7,777.78) |
| pl_orbeccen | dimensionless | `14 And b` (0) | `HD 20782 b` (0.95) |

Eight labelled SVG plots are saved under `data/cluster_validation/plots/`, with one original-unit feature distribution per feature and candidate. The JSON report records input and output hashes, statistical results, category-count diagnostics, and runtime versions.

Limitations: K-means produces geometric partitions, not established astronomical classes; silhouette assesses geometry only; binned univariate overlap depends on the stated common bins; discovery-method association is subject to catalogue selection; and this milestone does not model dependence among planets around the same host star.
