# ExoAtlas K-means Experiment Report

## Dataset and method

- Source snapshot: `PSCompPars_2026.10.30_13.47.46.csv` (download snapshot 2026-10-30).
- Source SHA-256: `16bb38b253d375b49cdb286b45e38435746c74bfde10d3ba580199fa822b6c30`; raw data and approved preprocessing artifacts were unchanged during the run.
- Observations: **5,273 planets** in both experiments, with identical `pl_name` values in the same order.
- Primary K-means: `init=k-means++`, `n_init=20`, `max_iter=300`, `tol=0.0001`, `copy_x=True`, `verbose=0`, primary `random_state=42`, algorithm `lloyd`.
- Stability seeds: 42, 17, 23, 29, 31, 37, 43, 47, 53, 59 (10 total, including primary seed 42).
- Evaluation: full-cohort Euclidean silhouette; same method and observations in both feature configurations. The small-cluster review flag is under 1% of the cohort (52.73 observations), and does not filter data.

Experiment A passed `scaled_log10_pl_rade`, `scaled_log10_pl_orbper`, `scaled_pl_eqt`, and `scaled_pl_orbeccen` to K-means. Experiment B passed only `scaled_log10_pl_rade`, `scaled_log10_pl_orbper`, and `scaled_pl_orbeccen`. Its raw `pl_eqt` column is retained in the CSV for context but excluded from the model input. Existing StandardScaler artifacts were loaded and verified; no new scaler was fitted and no feature was transformed again.

K-means labels are arbitrary partition identifiers. These profiles describe assigned observations; they are not established scientific planet types. No K was selected automatically.

## Primary seed-42 results

Inertia values are specific to each feature space, so compare their trends within an experiment rather than interpreting cross-configuration differences as directly equivalent. Silhouette is a full-data Euclidean separation summary and does not alone determine a suitable K.

| Experiment | K | Inertia | Silhouette | Clusters | Cluster sizes (ID: count) | Min | Max | Mean | Iterations | Reached max_iter | Clusters below 1% |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|---|
| with_temp | 2 | 13320.512761 | 0.458656 | 2 | 0:4269, 1:1004 | 1004 | 4269 | 2636.50 | 18 | False | none |
| with_temp | 3 | 9371.579633 | 0.422730 | 3 | 0:3287, 1:953, 2:1033 | 953 | 3287 | 1757.67 | 10 | False | none |
| with_temp | 4 | 7557.505468 | 0.341264 | 4 | 0:871, 1:1361, 2:2223, 3:818 | 818 | 2223 | 1318.25 | 7 | False | none |
| with_temp | 5 | 6062.332239 | 0.358685 | 5 | 0:811, 1:2270, 2:322, 3:1200, 4:670 | 322 | 2270 | 1054.60 | 15 | False | none |
| with_temp | 6 | 5377.163984 | 0.368468 | 6 | 0:764, 1:286, 2:638, 3:1187, 4:2159, 5:239 | 239 | 2159 | 878.83 | 11 | False | none |
| with_temp | 7 | 4780.310238 | 0.318663 | 7 | 0:1342, 1:511, 2:1563, 3:605, 4:220, 5:754, 6:278 | 220 | 1563 | 753.29 | 35 | False | none |
| with_temp | 8 | 4303.241584 | 0.314542 | 8 | 0:1495, 1:1276, 2:510, 3:258, 4:492, 5:453, 6:578, 7:211 | 211 | 1495 | 659.12 | 42 | False | none |
| without_temp | 2 | 8927.165399 | 0.527156 | 2 | 0:994, 1:4279 | 994 | 4279 | 2636.50 | 9 | False | none |
| without_temp | 3 | 6156.152179 | 0.462747 | 3 | 0:3354, 1:849, 2:1070 | 849 | 3354 | 1757.67 | 6 | False | none |
| without_temp | 4 | 4631.030055 | 0.490383 | 4 | 0:3339, 1:341, 2:643, 3:950 | 341 | 3339 | 1318.25 | 15 | False | none |
| without_temp | 5 | 3713.530583 | 0.379481 | 5 | 0:1860, 1:609, 2:912, 3:1564, 4:328 | 328 | 1860 | 1054.60 | 9 | False | none |
| without_temp | 6 | 3067.244115 | 0.396880 | 6 | 0:1522, 1:589, 2:1787, 3:854, 4:300, 5:221 | 221 | 1787 | 878.83 | 14 | False | none |
| without_temp | 7 | 2767.397162 | 0.358822 | 7 | 0:296, 1:569, 2:1541, 3:823, 4:221, 5:811, 6:1012 | 221 | 1541 | 753.29 | 13 | False | none |
| without_temp | 8 | 2505.321416 | 0.349930 | 8 | 0:1510, 1:235, 2:821, 3:457, 4:128, 5:1008, 6:829, 7:285 | 128 | 1510 | 659.12 | 18 | False | none |

## Random-initialization stability

Each experiment/K has 10 runs. Inertia and silhouette mean/SD cover all 10 runs. ARI mean/SD compares the nine non-primary seeds with the seed-42 labels; the seed-42 self-comparison (ARI=1) is present in `stability_metrics.csv` but excluded from that summary to avoid inflating stability. Standard deviations below use the sample convention (ddof=1).

| Experiment | K | Runs | Inertia mean +/- SD | Silhouette mean +/- SD | ARI mean +/- SD vs seed 42 (9 runs) |
|---|---:|---:|---:|---:|---:|
| with_temp | 2 | 10 | 13320.512761 +/- 0.000000 | 0.458656 +/- 0.000000 | 1.000000 +/- 0.000000 |
| with_temp | 3 | 10 | 9371.545915 +/- 0.044455 | 0.422075 +/- 0.000596 | 0.995701 +/- 0.003690 |
| with_temp | 4 | 10 | 7557.592748 +/- 0.114438 | 0.341955 +/- 0.000586 | 0.986744 +/- 0.007086 |
| with_temp | 5 | 10 | 6062.297056 +/- 0.030584 | 0.358165 +/- 0.000393 | 0.989302 +/- 0.006336 |
| with_temp | 6 | 10 | 5377.227775 +/- 0.030892 | 0.368611 +/- 0.000150 | 0.997170 +/- 0.002929 |
| with_temp | 7 | 10 | 4780.281221 +/- 0.061193 | 0.318640 +/- 0.000048 | 0.999388 +/- 0.001242 |
| with_temp | 8 | 10 | 4303.295831 +/- 0.058558 | 0.314841 +/- 0.000272 | 0.986620 +/- 0.005029 |
| without_temp | 2 | 10 | 8927.160832 +/- 0.003217 | 0.527234 +/- 0.000067 | 0.999405 +/- 0.000447 |
| without_temp | 3 | 10 | 6156.159210 +/- 0.006568 | 0.462792 +/- 0.000095 | 0.998407 +/- 0.000714 |
| without_temp | 4 | 10 | 4631.030287 +/- 0.000299 | 0.490383 +/- 0.000000 | 0.999743 +/- 0.000305 |
| without_temp | 5 | 10 | 3713.533466 +/- 0.014920 | 0.379504 +/- 0.000078 | 0.998206 +/- 0.001858 |
| without_temp | 6 | 10 | 3067.245234 +/- 0.002443 | 0.396879 +/- 0.000016 | 0.999865 +/- 0.000269 |
| without_temp | 7 | 10 | 2767.413438 +/- 0.021530 | 0.358821 +/- 0.000066 | 0.995490 +/- 0.004429 |
| without_temp | 8 | 10 | 2505.554208 +/- 0.429007 | 0.349910 +/- 0.000601 | 0.987223 +/- 0.008475 |

## Temperature-feature sensitivity

Adjusted Rand Index (ARI) compares the two seed-42 partitions at each K. It describes partition sensitivity to the feature configuration; it does not show that temperature causes a difference.

| K | ARI (A vs B) | A clusters | B clusters | Observations per experiment |
|---:|---:|---:|---:|---:|
| 2 | 0.875162 | 2 | 2 | 5273 |
| 3 | 0.729179 | 3 | 3 | 5273 |
| 4 | 0.456270 | 4 | 4 | 5273 |
| 5 | 0.603667 | 5 | 5 | 5273 |
| 6 | 0.617257 | 6 | 6 | 5273 |
| 7 | 0.504411 | 7 | 7 | 5273 |
| 8 | 0.460466 | 8 | 8 | 5273 |

## Cluster profiles in physical units

The two profile CSVs contain one row per seed-42 cluster at each K. They report planet count and percentage, plus median, Q1, Q3, IQR, mean, and sample standard deviation for radius (Earth radii), orbital period (days), equilibrium temperature (K), and eccentricity (dimensionless). Profiles use original measurements from the master dataset, not standardized values.

Cluster IDs have no physical ordering or scientific type label. A change in profile between K values reflects a different partition of the same cohort, not a validated taxonomy.

## Feature distributions, correlations, and extreme observations

`feature_diagnostics.json` records distributions and the Pearson correlation matrix for the exact standardized columns passed to each experiment. It also lists the five largest absolute standardized observations per input feature, with identifiers, raw physical values, and their seed-42 cluster assignment at each K.

- with_temp: largest absolute pairwise correlation is scaled_log10_pl_orbper vs scaled_pl_eqt (r=-0.7049).
- without_temp: largest absolute pairwise correlation is scaled_log10_pl_orbper vs scaled_pl_orbeccen (r=0.4483).
The two largest absolute standardized eccentricity observations (HD 20782 b and HD 28254 b) are assigned together at every K in both feature configurations. This is a descriptive grouping of extreme values, not evidence that they caused a boundary; no outlier-removal sensitivity run was done.
Cluster-size tables above include empty clusters and review-only under-1% clusters. No empty clusters or observations were silently removed, merged, or filtered. Extreme-value assignments are descriptive; identifying influence causally would require a separately approved sensitivity experiment.

## Outputs and limitations

- `experiment_metrics.csv`: seed-42 metrics for both experiments and K=2..8.
- `stability_metrics.csv`: per-seed metrics and ARI against the seed-42 partition.
- `cluster_profiles_with_temp.csv` and `cluster_profiles_without_temp.csv`: physical-unit summaries for every primary cluster.
- `temperature_sensitivity.csv`: A-vs-B ARI for each K.
- Assignment files named `cluster_assignments_<experiment>_k<K>.csv`: one seed-42 `pl_name,cluster_id` file for every experiment/K pair.
- `feature_diagnostics.json`, `clustering_report.json`, and this report: input distributions/correlations, size diagnostics, settings, results, hashes, and interpretation limits.
- `artifacts/clustering/`: 14 fitted seed-42 K-means models, one for each experiment/K combination.

K-means favors compact Euclidean clusters, and silhouette, inertia, and initialization stability capture different properties. They are evidence for review, not an automatic K selector. The analysis makes no causal claims, adds no features, removes no observations, and does not establish scientific planet classes.
