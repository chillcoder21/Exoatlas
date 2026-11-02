# The Outliers — Analysis Report

## Dataset and method

The catalogue contains **6,451** confirmed-planet records. The frozen four-feature K=4 model covers **5,273**; **1,178** remain searchable but have no model diagnostics.

For each assigned planet, the pipeline measures Euclidean distance to its existing assigned K-means centroid in the saved standardized space: log10 radius, log10 orbital period, raw equilibrium temperature, and raw eccentricity after the already-fitted StandardScaler. It ranks distance within the assigned cluster using average empirical ranks (ties share their average rank). No model or scaler is fitted.

The saved `with_temp` silhouette result is joined by `pl_name`; it is not recomputed. A negative silhouette is a weak-separation diagnostic under this representation, not a physical classification.

## Population summaries

The within-cluster distance percentile has median **50.04%** (Q1 25.06%, Q3 75.03%). There are **119** negative saved silhouettes among assigned planets.

### Feature relations to assigned-cluster quartiles

| Measurement | Below Q1 | Within Q1–Q3 | Above Q3 |
| --- | ---: | ---: | ---: |
| Planetary radius (Earth radii) | 1,306 | 2,689 | 1,278 |
| Orbital period (days) | 1,319 | 2,635 | 1,319 |
| Equilibrium temperature (K) | 1,317 | 2,637 | 1,319 |
| Orbital eccentricity (dimensionless) | 214 | 3,902 | 1,157 |

A value outside Q1–Q3 is a descriptive comparison, not evidence of error or physical exceptionalism. The optional IQR displacement is `(measurement − cluster median) / cluster IQR`; it is omitted when IQR is zero. It is not a probability or a combined outlier score.

## Highest within-cluster distance percentiles

These are the largest empirical distance percentiles under this specific model representation. They are review candidates, not asserted anomalies.

| Planet | Cluster | Distance (standardized space) | Within-cluster percentile | Saved silhouette |
| --- | ---: | ---: | ---: | ---: |
| KELT-9 b | 3 | 5.3067 | 100.00% | 0.1760 |
| Kepler-127 b | 2 | 3.0642 | 100.00% | 0.0250 |
| Kepler-1547 b | 1 | 4.3985 | 100.00% | 0.0822 |
| VHS J125601.92-125723.9 b | 0 | 5.3342 | 100.00% | 0.2753 |
| Kepler-391 b | 2 | 2.9856 | 99.96% | 0.0213 |
| HD 93351 b | 1 | 3.5575 | 99.93% | 0.0832 |
| K2-25 b | 2 | 2.8006 | 99.91% | 0.1124 |
| TOI-6716 b | 0 | 5.2424 | 99.89% | 0.0688 |
| WASP-189 b | 3 | 4.0859 | 99.88% | 0.2231 |
| TOI-269 b | 2 | 2.7546 | 99.87% | 0.0989 |
| Kepler-770 c | 1 | 3.3831 | 99.85% | 0.1201 |
| Kepler-1928 b | 2 | 2.6653 | 99.82% | 0.1258 |

## Interpretation limits

- High centroid distance, unusual individual measurements, and low silhouette describe different properties; they are not combined into one score.
- A high distance does not prove an observation is incorrectly assigned. A low silhouette indicates weak separation in the selected feature space.
- Quartiles are reference summaries of the assigned groups. An outside-IQR value is not automatically anomalous or erroneous.
- Cluster IDs are arbitrary partition labels. The result depends on selected features, transformations, and scaling.
- This confirmed-planet catalogue reflects observational and discovery biases; four measurements do not support claims about habitability, atmospheres, composition, or physical mechanisms.
- Unassigned planets have null centroid, percentile, silhouette, and cluster-relative feature diagnostics. No missing values are imputed.

## Reproducibility and integrity

The frozen source, application data, feature matrix, assignments, silhouette file, scaler, model, and cluster profiles were checksum-verified before and after computation. The prepared diagnostics CSV SHA-256 is `87009f5ff021caf4dbb6c77c0f87ac51bbc3672efff182298ea15b0e80804851`.
