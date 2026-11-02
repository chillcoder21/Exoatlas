# ExoAtlas

ExoAtlas is an interactive scientific atlas for exploring confirmed exoplanets through five connected chapters: The Universe, The Patterns, The Explorer, The Outliers, and The Discovery Lens. It includes a reproducible NASA dataset audit, frozen clustering artifacts, descriptive outlier analysis, and an offline Discovery Lens pipeline. Supervised modeling has not been implemented.

## Project layout

```text
ExoAtlas/
├── AGENTS.md                 # Architecture, scientific integrity, and development rules
├── backend/
│   ├── __init__.py
│   ├── app.py                # Read-only Flask API over prepared application data
│   ├── requirements.txt      # Flask and API data dependencies
│   └── tests/                # API integration tests
├── data/
│   ├── cluster_experiments/  # K-means metrics, profiles, assignments, and reports
│   ├── cluster_validation/   # Validation diagnostics and reports
│   ├── metadata/             # Audit, preprocessing, cluster, app, and Discovery Lens reports
│   ├── processed/            # Master, feature matrices, app data, and Discovery Lens summaries
│   └── raw/                  # Unchanged NASA source CSV; ignored by Git
├── artifacts/
│   ├── clustering/           # Seed-42 models and frozen model registry
│   └── preprocessing/        # Fitted StandardScaler objects
├── frontend/                 # React + TypeScript + Vite client
├── scripts/                  # Windows startup checks
├── start_exoatlas.bat         # One-click Windows launcher
├── ml/
│   ├── data_audit.py         # Reproducible read-only dataset audit
│   ├── preprocessing.py      # Eligibility, transformations, and scalers
│   ├── pipeline.py           # Reproducible preprocessing outputs and reports
│   ├── clustering.py         # K-means and evaluation helpers
│   ├── clustering_pipeline.py # Primary, stability, and sensitivity experiments
│   ├── cluster_validation.py # Profile, separation, and association diagnostics
│   ├── validation_pipeline.py # Reproducible candidate-cluster validation reports
│   ├── application_data.py   # Build app data from saved assignments; never refits
│   ├── discovery_lens.py     # Offline catalogue composition, timeline, property, and facility summaries
│   ├── tests/                # Preprocessing and clustering tests
│   └── requirements.txt      # Pinned data and preprocessing dependencies
├── .gitignore
└── README.md
```

## Requirements

- Python 3.12 or newer
- Node.js 20.19 or newer (the installed Node.js 24.20.0 is suitable)
- npm

## Python API

From the repository root, create and activate the virtual environment, then install the backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

If PowerShell prevents script activation, use Command Prompt and run `.venv\Scripts\activate.bat` instead.

The API serves the generated data layer. Build it as described under [Frozen primary model and data API](#frozen-primary-model-and-data-api). For routine use, the one-click startup instructions below run both services.

```powershell
python -m flask --app backend.app run --debug --port 5000
```

## Frontend application

The frontend uses React, TypeScript, Vite, D3, and Motion for React. Its five chapters read prepared records and saved scientific summaries through the Flask API.

### One-click Windows startup

Complete setup once from the repository root. Use the existing `.venv` and prepared application data:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Set-Location frontend
npm install
Set-Location ..
```

Then double-click `start_exoatlas.bat`, or run it in PowerShell:

```powershell
.\start_exoatlas.bat
```

The launcher checks the prepared data, installed dependencies, and ports 5000 and 5173. It reuses healthy ExoAtlas services, reports a clear conflict if a port belongs to another service, and starts Flask and Vite in separate visible command windows when needed. After both readiness checks pass, it opens `http://127.0.0.1:5173/` in the default browser. Startup does not audit, preprocess, refit scalers, or train models. To stop services started by the launcher, press Ctrl+C in each service window. The launcher never terminates an existing process.

### Manual startup

If preferred, run Flask from the repository root:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend.app run --debug --host 127.0.0.1 --port 5000
```

Then run Vite in a second terminal:

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1 --strictPort
```

Open `http://127.0.0.1:5173/`. Vite proxies `/api` to Flask on port 5000. Run frontend tests, lint, and the TypeScript/production build from `frontend/`:

```powershell
npm test
npx tsc -b --pretty false
npm run lint
npm run build
```

The `/universe` route explores the confirmed population. It reads `/api/overview`, `/api/clusters`, and every page of `/api/planets` (100 records per request, fetched in bounded batches). It validates totals, assignment counts, pagination, and unique `pl_name` identifiers before showing any records. Search works over the entire loaded population, including planets omitted from the current plot because selected axis values are unavailable. The list response already carries the measurements, host, discovery method/year, and saved assignment needed by the inspection panel, so no detail request is needed for selection.

The default feature-space axes are orbital period (days) and planetary radius (Earth radii), both logarithmic. Equilibrium temperature (K) and orbital eccentricity are linear when selected. Tick labels, tooltips, and inspection values use original physical measurements. Missing or non-finite values are not plotted; zero or negative values are omitted only while their measurement is on a logarithmic axis. Eccentricity zero remains valid on its linear axis. No data is imputed, re-clustered, or read from the raw CSV by the frontend.

Cluster IDs use stable colours and distinct point shapes. All four saved exploratory clusters and all unassigned planets are visible by default; unassigned confirmed planets use hollow neutral marks. The controls support cluster visibility, axis selection, name/host search, point selection, zoom, pan, and zoom reset. The page labels K=4 assignments as exploratory rather than astronomical classes. Loading, partial-page/API failures, and no-match search each have distinct states. Motion and D3 transitions respect the reduced-motion preference; keyboard users can search and select records, inspect the same physical fields, and use the labeled axis and population controls.

The `/patterns` route presents the saved K=4 cluster profiles, quartile ranges, silhouette summaries, centroid spacing, and the same-cohort temperature sensitivity experiment. It reads `/api/clusters`, `/api/model`, and `/api/validation/summary`; the backend summary exposes saved cluster-level silhouette results, pairwise centroid distances, the C1–C2 eccentricity overlap diagnostic, and the no-temperature cluster distribution summaries from the existing validation artifacts. The profile charts use original physical units, with an explicitly logarithmic axis for orbital period. Cluster selection highlights quartile ranges across all four features, and a tabular view exposes the medians, quartiles, IQRs, and sample sizes. The page does not fit or alter a model. It labels cluster IDs as arbitrary exploratory partition labels, distinguishes feature-space distances from physical measurements, and cautions that a higher silhouette in a different feature space does not establish a scientifically better configuration.

The `/explorer` route provides a searchable dossier for each confirmed planet, including available original planetary, discovery, and host-star measurements. Its cluster context shows saved K=4 physical-unit quartiles and where observed values fall relative to Q1–Q3. Unassigned records remain accessible and show their saved eligibility explanation. Similar Worlds ranks up to five other eligible planets by Euclidean distance in the exact saved standardized four-feature primary space: log10 radius, log10 period, raw equilibrium temperature, and raw eccentricity. Flask verifies and reuses the saved `StandardScaler`; no scaler or model is fitted at request time. Distance is a representation-specific measurement comparison, not a probability, identity, composition, or habitability claim. A side-by-side view compares original physical measurements. A selected planet is encoded in the URL and can be opened from The Universe.

The Outliers chapter investigates the existing frozen K=4 results. The Discovery Lens compares the full confirmed-planet catalogue by its recorded discovery methods, years, properties, measurement availability, and reporting facilities. It is descriptive: method counts are not occurrence rates, comparisons are not causal, and host-level observations may be dependent. Frontend test fixtures and mocks are not included in application output.

Frontend structure:

- `src/features/universe/api.ts`: bounded pagination and integrity checks for the existing Flask API.
- `src/features/universe/FeatureSpacePlot.tsx`: isolated D3 SVG map, scales, interactions, and zoom behavior.
- `src/features/universe/PlanetSearch.tsx` and `PlanetInspector.tsx`: full-population search and measurement inspection.
- `src/features/universe/UniversePage.tsx`: population summary, controls, loading/error handling, and page composition.
- `src/features/universe/*.module.css`: responsive experience styles using the shared design tokens.
- `src/features/universe/*.test.ts(x)`: API, eligibility, interaction, and reduced-motion tests; fixtures are test-only.
- `src/features/patterns/PatternsPage.tsx` and `PatternsCharts.tsx`: saved-results narrative and D3 population, physical-unit quartile, silhouette, and centroid-distance views.
- `src/features/patterns/PatternsPage.module.css`: responsive Patterns chapter styling, including interactive cluster highlighting and tabular data details.
- `src/features/explorer/ExplorerPage.tsx`: catalogue search, planet dossiers, saved cluster ranges, nearest-neighbor ranking, and side-by-side comparison.
- `src/features/explorer/ExplorerPage.module.css`: responsive Explorer layout and interaction states.
- `src/features/outliers/OutliersPage.tsx`: model-relative distance ranking, cluster-quartile measurement context, saved silhouette diagnostics, and observation comparison.
- `src/features/outliers/OutliersPage.module.css`: responsive outlier investigation layout and interaction states.
- `src/features/discovery-lens/DiscoveryLensPage.tsx`: five connected investigations, URL-based method/property selections, and catalogue caveats.
- `src/features/discovery-lens/DiscoveryLensCharts.tsx`: D3 composition, timeline, quartile, missingness, and facility charts.
- `src/features/discovery-lens/api.ts` and `types.ts`: abortable API requests and typed summary responses.
- `src/features/discovery-lens/DiscoveryLensPage.module.css`: responsive chapter styles using shared tokens.
- `src/features/discovery-lens/DiscoveryLensPage.test.tsx`: route content, filter state, and catalogue-source interactions.
- `scripts/start_exoatlas.ps1` and `start_exoatlas.bat`: preflight, port reuse/conflict checks, service readiness polling, and browser launch.
- `src/components/layout/AppShell.tsx`: shared masthead, navigation, route focus handling, and footer.
- `src/config/sections.ts`, `src/styles/tokens.css`, and `src/index.css`: route metadata, design tokens, global accessibility, and reduced-motion preferences.

The application does not train a model or change saved assignments. It uses only the frozen application data and API. No remote imagery, geographic sky mapping, or fabricated production observations are included.

## Dataset

The original file `PSCompPars_2026.10.30_13.47.46.csv` is stored at `data/raw/`. It was moved without editing its contents. The pre-move and post-move SHA-256 values are recorded in the generated audit report and JSON metadata. The `data/raw/` directory is ignored by Git.

## Dataset audit

From the repository root, activate the existing virtual environment and install the pinned data workflow dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r ml\requirements.txt
python ml\data_audit.py
```

The script accounts for NASA `#` comment metadata, verifies the recorded source checksum, and generates:

- `data/metadata/dataset_audit.json`
- `data/metadata/dataset_audit.md`

It does not modify the source CSV, impute values, transform features, or train models. It stops if the source checksum differs from the value captured before the move; review the source before changing that checksum in the script.

## Reproducible preprocessing

Preprocessing uses the same existing virtual environment and pinned dependencies. From the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r ml\requirements.txt
python -m ml.pipeline
```

The pipeline verifies the pinned source hash before reading the CSV and checks that the file is unchanged at the end. NASA comment metadata is skipped. Outputs are:

- `data/processed/planets_master.csv`: all 6,451 source records and all original columns, plus a source row number and eligibility indicators/reasons. It has no cluster labels.
- `data/processed/clustering_features_with_temp.csv`: the 5,273-planet primary cohort with radius and period log-transformed, raw equilibrium temperature and eccentricity, and separately named standardized feature columns.
- `data/processed/clustering_features_without_temp.csv`: the exact same 5,273 identifiers in the same order, using radius, period, and eccentricity as features. Raw equilibrium temperature remains in the file as context and is not included in this experiment's feature list.
- `artifacts/preprocessing/scaler_with_temp.joblib` and `scaler_without_temp.joblib`: separately fitted `StandardScaler` objects for the two feature sets.
- `data/metadata/preprocessing_report.json` and `preprocessing_report.md`: counts, transformations, scaler parameters, output hashes, and extreme-value review records.

The four-feature cohort requires nonmissing, finite numeric values for all four planned features. Radius and orbital period must also be positive for `log10`. This complete-case policy yields 5,273 primary records; no values are imputed. The 1,178 ineligible planets remain in the master dataset. The 5,335 records eligible without temperature are recorded as a sensitivity eligibility count only; the pipeline does not write or use that larger cohort for the primary comparison.

Base-10 logs make the positive radius and orbital-period scales less skewed and compress large multiplicative ranges while retaining rank order. `StandardScaler` centers and scales each experiment's transformed features to comparable numeric ranges. It is fitted independently for each feature set. Original physical columns are kept unchanged in the outputs; eccentricity zeros and IQR-flagged observations are retained. No clustering or supervised model is trained.

To run the validation suite:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest
```

Known limitations: statistical IQR flags do not establish that a value is invalid; extreme observations remain pending source-level scientific review. StandardScaler can be influenced by extremes. Multiple planets share host stars, so later modeling may need to consider dependence among planets from the same system. The sensitivity count without temperature is not used in the primary comparison.

## K-means experiments

Run the approved experiments after preprocessing has generated its feature matrices and scalers:

```powershell
.\.venv\Scripts\Activate.ps1
python -m ml.clustering_pipeline
python -m pytest -q
```

Both experiments use the same 5,273 ordered planet identifiers and the already-standardized matrices. Experiment A passes `scaled_log10_pl_rade`, `scaled_log10_pl_orbper`, `scaled_pl_eqt`, and `scaled_pl_orbeccen`. Experiment B passes only `scaled_log10_pl_rade`, `scaled_log10_pl_orbper`, and `scaled_pl_orbeccen`; its raw `pl_eqt` context column is not passed to K-means. The pipeline loads and verifies the existing separate scalers without refitting them or transforming the data again.

For each experiment, the pipeline evaluates K=2 through K=8 using `sklearn.cluster.KMeans` with `init="k-means++"`, `n_init=20`, `max_iter=300`, `tol=1e-4`, `copy_x=True`, `verbose=0`, Lloyd's algorithm, and primary `random_state=42`. Ten seeds (42, 17, 23, 29, 31, 37, 43, 47, 53, 59) are used for initialization stability. The full 5,273-observation Euclidean silhouette is computed for each run. Stability ARI compares each run to that experiment/K's seed-42 assignment; the ARI summary omits seed 42's trivial self-comparison, while the individual row remains in the run-level CSV.

Outputs are written to `data/cluster_experiments/`: primary and stability metrics, physical-unit cluster profiles, temperature sensitivity ARI, feature diagnostics, JSON/Markdown reports, and one `pl_name,cluster_id` seed-42 assignment CSV for each experiment/K pair. Fourteen seed-42 models are saved under `artifacts/clustering/`.

The report records cluster sizes, convergence iterations, empty/tiny-cluster review flags, input distributions, Pearson correlations, and extreme standardized observations. A cluster smaller than 1% of the cohort is flagged for review only; no cluster or observation is removed or merged. Inertia is specific to a feature space, silhouette is not a standalone K selector, and between-experiment ARI measures partition sensitivity rather than causation. Cluster labels are partition IDs, not established planet types. The pipeline does not choose a final K.

## Scientific cluster validation

Validate the saved seed-42 K=4 candidate assignments after running the K-means experiments:

```powershell
.\.venv\Scripts\Activate.ps1
python -m ml.validation_pipeline
python -m pytest -q
```

Validation joins the original NASA physical measurements to saved assignments by the stable `pl_name` identifier. It does not refit K-means, change feature transformations, delete or impute observations, or modify raw/preprocessed inputs. It reports original-unit min/max, quartiles, median, mean, sample standard deviation and IQR for radius, orbital period, equilibrium temperature and eccentricity. Per-observation Euclidean silhouettes use the exact existing standardized feature matrices. Pairwise centroid distances use that same standardized input space; one-dimensional feature overlap uses shared physical-value histogram bins and is a diagnostic, not a formal distribution test.

Discovery-method tables include full-source and primary-cohort counts, within-cluster and within-method percentages, Pearson chi-square and Cramér's V. Rare discovery categories are retained; the report flags low expected cell counts and cautions against overinterpreting asymptotic p-values. Associations are not causal: detection sensitivities and survey selection effects differ, and confirmed planets are not an unbiased sample of all planetary systems.

Generated results are saved under `data/cluster_validation/`:

- `cluster_distribution_validation.csv`: original-unit descriptive statistics for every candidate, cluster and physical feature.
- `cluster_silhouette_validation.csv`: one Euclidean silhouette value per planet and candidate, with cluster summaries in the report.
- `cluster_separation.csv`: pairwise standardized centroid distances and binned univariate overlap coefficients.
- `discovery_method_counts.csv`, `discovery_method_row_percentages.csv`, and `discovery_method_column_percentages.csv`: discovery-method count and composition tables.
- `discovery_method_tests.json`: chi-square, Cramér's V, expected-count diagnostics and interpretation notes.
- `temperature_feature_comparison.csv`: all 16 cross-configuration cluster pairs, the one-to-one membership matching, Jaccard overlap, original-unit median differences, and discovery-method composition distance.
- `temperature_feature_membership_changes.csv`: planet IDs whose memberships differ after that label alignment.
- `k_selection_comparison.csv`: four-feature K=2–5 size, silhouette, stability and iteration summary.
- `plots/`: eight labelled SVG histograms, one for each original physical feature and K=4 candidate. Broad positive ranges use logarithmic horizontal axes where appropriate; saved measurements remain in physical units.
- `cluster_validation_report.md` and `cluster_validation_report.json`: interpretation, caveats, recommendation, input integrity hashes, output hashes and runtime versions.

Cluster IDs are arbitrary labels and are aligned between models by shared membership, never by equal numeric ID alone. Silhouette and association tests are diagnostics, not scientific validation or proof of astronomical classes. The report recommends whether K=4 is justified as an exploratory configuration but does not automatically select or freeze a model. The validation treats planets independently and does not account for dependence among planets orbiting a shared host star.

## Frozen primary model and data API

Milestone 6 freezes the **existing with-temperature K=4 seed-42 run** as the primary exploratory configuration for ExoAtlas v1. This is the approved application-design choice; it is not a claim that K=4 is the objectively correct number of scientific populations. The registry is `artifacts/clustering/model_registry.json` and records checksums and metadata for the saved model, scaler, assignment file, source snapshot, and prior reports.

The exact primary artifacts are:

- Existing fitted K-means model: `artifacts/clustering/kmeans_with_temp_k4.joblib`.
- Existing four-feature scaler: `artifacts/preprocessing/scaler_with_temp.joblib`.
- Existing seed-42 assignments: `data/cluster_experiments/cluster_assignments_with_temp_k4.csv`.
- Ordered transformed features: `log10_pl_rade`, `log10_pl_orbper`, `pl_eqt`, `pl_orbeccen`; the saved scaler's exact estimator input columns are `scaled_log10_pl_rade`, `scaled_log10_pl_orbper`, `scaled_pl_eqt`, `scaled_pl_orbeccen`.
- Cohort: 5,273 complete-case records, with the original physical measurements retained in `data/processed/planets_master.csv`.

K-means uses `init="k-means++"`, `n_init=20`, `max_iter=300`, `tol=0.0001`, Lloyd's algorithm, and `random_state=42`. The chosen saved run has a Euclidean silhouette of 0.3413 and stability ARI mean 0.9867 across alternate initializations (seed-42 self-comparison omitted). The validation report found a higher silhouette for the simpler K=2 and K=3 choices; K=5 was slightly higher than K=4. The project selected K=4 to expose four descriptive profiles in v1, while preserving **with-temperature K=2, K=3, K=5 and no-temperature K=4** for future comparison. Paths, cohort sizes, metrics, and hashes for these alternatives are in the model registry.

These labels describe a geometric partition of confirmed planets, not established astronomical types. The four-feature silhouette is a diagnostic, not scientific validation. The selected partition has 119 negative silhouette observations (2.26%); adding temperature substantially changes memberships relative to no-temperature K=4 (ARI 0.4563; 37.09% changed after alignment). IQR-flagged extremes remain included and can influence StandardScaler. Discovery-method composition reflects differing detection sensitivities and catalogue selection effects; it is descriptive and not causal. Planet-level analysis does not account for dependence among planets around the same host star.

### Generate application data

Run this offline data-layer build after the audit, preprocessing, clustering, and validation artifacts exist:

```powershell
.\.venv\Scripts\Activate.ps1
python -m ml.application_data
```

The script verifies the audited source checksum and the checksums of the approved master table and existing K=4 assignments. It performs a `pl_name` join and does not fit K-means, refit a scaler, alter preprocessing outputs, impute measurements, or remove extremes. It writes:

- `data/processed/planets_application.csv`: all 6,451 master records and original columns, with `cluster_id` populated for 5,273 planets and null for 1,178; `assignment_status` is `assigned` or `unassigned`.
- `data/metadata/cluster_profiles.json`: K=4 counts, share of the 5,273-member cohort, median and IQR for the four original physical measurements, units, and neutral descriptive summaries.
- `artifacts/clustering/model_registry.json`: primary frozen configuration and comparison references.
- `data/metadata/application_data_report.json`: record counts, input checksums, and generated-output checksums.

The full app table keeps unassigned planets available for search and detail requests. No cluster is assigned to planets outside the approved complete-case cohort.

### Start ExoAtlas

Use [one-click Windows startup](#one-click-windows-startup) to start the API and frontend together. For an API-only session, install dependencies in the existing virtual environment if needed, then run Flask from the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m flask --app backend.app run --debug --port 5000
```

The API loads the generated application CSV, metadata, and frozen feature index once when the Flask app is created. It serves prepared outputs and does not rerun scientific analysis or fit a model on requests. It has no database or authentication.

### API endpoints

All successful responses are JSON. Errors use `{"error":{"code":"...","message":"..."}}`. List routes default to `page=1&page_size=50`; `page_size` must be from 1 through 100. Planet ordering is the deterministic source order. The stable planet identifier is the URL-encoded `pl_name`.

Planet-list search is case-insensitive and matches either `pl_name` or `hostname`.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Service/data readiness and dataset counts. |
| `GET /api/overview` | Dataset totals, discovery counts, dataset and model versions. |
| `GET /api/planets?page=1&page_size=50` | Paginated planet records. Optional filters: `search`, `cluster_id`, `discovery_method`, `assignment_status`. |
| `GET /api/planets/<planet_id>` | Complete available record for one URL-encoded `pl_name`. |
| `GET /api/planets/<planet_id>/similar?limit=5` | Up to five nearest other eligible records in the saved standardized four-feature space; maximum limit is 20. |
| `GET /api/clusters` | Four primary physical-unit cluster profiles. |
| `GET /api/clusters/<cluster_id>?page=1&page_size=50` | Cluster profile and paginated member records. |
| `GET /api/discovery/summary` | Discovery-method counts and within-cluster descriptive percentages. |
| `GET /api/discovery/overview` | Discovery Lens catalogue totals, method shares, unique hosts, facilities, and source snapshot. |
| `GET /api/discovery/timeline?method=Transit` | Catalogue counts for 1992–2026, with optional exact method filters; 2026 is marked partial. Repeat `method` or use comma-separated `methods` for comparisons. |
| `GET /api/discovery/distributions?property=pl_rade&method=Transit` | Measured and missing counts, quartiles, unique measured hosts, paired uncertainty availability, and measured observations. `property` is required; valid fields are `pl_rade`, `pl_orbper`, `pl_eqt`, and `pl_orbeccen`. |
| `GET /api/discovery/facilities?method=Transit` | Facility-attributed planet counts and denominator shares for the catalogue or selected methods. Counts are not independent surveys or host systems. |
| `GET /api/model` | Primary model configuration, caveats, and comparison metadata. |
| `GET /api/validation/summary` | Saved silhouette, stability, feature sensitivity, and association diagnostics. |

Examples:

```text
GET /api/overview
GET /api/planets?search=Kepler-22&cluster_id=2&page=1&page_size=20
GET /api/planets/11%20Com%20b
GET /api/planets/11%20Com%20b/similar?limit=5
GET /api/clusters/0?page=1&page_size=10
GET /api/validation/summary
GET /api/discovery/overview
GET /api/discovery/timeline?method=Transit&method=Radial%20Velocity
GET /api/discovery/distributions?property=pl_orbeccen&method=Transit
GET /api/discovery/facilities?method=Transit
```

### The Discovery Lens

Generate the descriptive tables offline after the prepared application dataset is available:

```powershell
.\.venv\Scripts\Activate.ps1
python -m ml.discovery_lens
```

The pipeline validates all 6,451 application records against the checksum-pinned raw PSCompPars snapshot and confirms the original 84 source columns match in row order. It preserves all 11 discovery methods, includes every year from 1992 through 2026 (with 1993 at zero and 2026 marked partial), and keeps the full catalogue instead of restricting analysis to the clustering cohort. It does not fit or modify a model, alter assignments, impute measurements, or write to the raw or prepared source tables. Before and after the run it hashes the frozen source, preprocessing, clustering, validation, and outlier artifacts.

Outputs:

- `data/processed/discovery_method_timeline.csv`: method counts for each catalogue year, including within-year percentages.
- `data/processed/discovery_method_property_summary.csv`: per-method measurement availability, missingness, quartiles, host counts, zero counts, and uncertainty-field availability for the four original properties.
- `data/processed/discovery_property_values.csv`: measured observations only, with planet/host identifiers and original signed `err1`/`err2` values.
- `data/processed/discovery_facility_counts.csv`: facility and method counts with catalogue and method denominators.
- `data/metadata/discovery_lens_report.json`: source and download timestamp, validation checks, snapshot facts, frozen-artifact checksums, and generated-output hashes.

The API loads these outputs at application startup; requests filter the precomputed tables and never rerun the pipeline. The source's signed asymmetric errors remain under their original `err1` and `err2` fields. They are not relabelled as lower/upper or converted into symmetric uncertainties.

## The Outliers

Generate the outlier diagnostics from the saved application data and frozen scientific artifacts:

```powershell
.\.venv\Scripts\Activate.ps1
python -m ml.outlier_analysis
```

The pipeline verifies the source, application table, four-feature matrix, K=4 assignments, saved silhouette results, fitted scaler and model, and cluster profiles against their existing checksums before and after the run. It reuses the fitted StandardScaler, K-means centroids, and saved `with_temp` silhouette values; it does not fit a model, refit scaling, alter assignments, or modify input artifacts.

Outputs:

- `data/processed/planet_outlier_diagnostics.csv`: one row per catalogue planet, in application-catalogue order. It preserves the host name and four original physical measurements, then adds assigned-centroid Euclidean distance in the frozen standardized four-feature space, empirical within-cluster distance percentile, saved silhouette, and per-feature quartile relation and median-relative IQR displacement. The 1,178 unassigned planets have null model diagnostics and cluster-relative comparisons.
- `data/metadata/outlier_analysis_report.json`: machine-readable counts, distributions, method definitions, input checksums, output checksum, and limitations.
- `data/metadata/outlier_analysis_report.md`: reproducible scientific summary and high-percentile review candidates.

Within-cluster distance percentiles use average empirical ranks for ties and are calculated separately for each frozen cluster. The interface's percentile control selects a review range; it is not a universal anomaly cutoff. Individual measurements are compared in original physical units against each assigned cluster's saved Q1, median, Q3, and IQR. IQR displacement is `(measurement - cluster median) / cluster IQR`, and is unavailable if that cluster's IQR is zero. The pipeline reuses per-planet silhouette values from validation rather than recalculating them. Distance, measurement position, and silhouette remain separate diagnostics; outside-IQR values are not automatically errors.

The prepared API endpoints are:

- `GET /api/outliers/overview`: catalogue counts, distance-percentile and silhouette distributions, method notes, and cluster profiles.
- `GET /api/outliers/observations?percentile_min=90&cluster_id=2&search=Kepler&page=1&page_size=20&sort_by=distance_percentile`: filter and paginate assigned observations. `sort_by` accepts `distance_percentile` or `silhouette`; the latter orders the lowest saved silhouettes first.
- `GET /api/outliers/planets/<url-encoded-pl_name>`: original catalogue record, available diagnostics, and per-feature cluster reference values. Unassigned records are returned with unavailable diagnostics explicitly labelled.

The prepared report records 6,451 catalogue planets, 5,273 assigned planets, 1,178 unassigned planets, and 119 negative saved silhouettes. These values describe this confirmed-planet snapshot and frozen feature representation; they do not establish physical types or causal explanations.

Example overview response:

```json
{
  "dataset": {
    "total_confirmed_planets": 6451,
    "with_primary_cluster_assignment": 5273,
    "without_cluster_assignment": 1178,
    "number_of_clusters": 4,
    "discovery_method_counts": {
      "Astrometry": 6,
      "Disk Kinematics": 1,
      "Eclipse Timing Variations": 17,
      "Imaging": 98,
      "Microlensing": 292,
      "Orbital Brightness Modulation": 9,
      "Pulsar Timing": 8,
      "Pulsation Timing Variations": 2,
      "Radial Velocity": 1204,
      "Transit": 4785,
      "Transit Timing Variations": 29
    },
    "version": "PSCompPars-2026-10-30",
    "source_sha256": "16bb38b253d375b49cdb286b45e38435746c74bfde10d3ba580199fa822b6c30"
  },
  "model": {
    "id": "exoatlas-kmeans-with-temperature-k4",
    "version": "1.0.0",
    "status": "frozen_exploratory_primary"
  }
}
```

Example paginated planet list response (record fields are abbreviated here; the API returns the full available row):

```json
{
  "pagination": {"page": 1, "page_size": 2, "total_records": 6451, "total_pages": 3226},
  "filters": {"search": null, "cluster_id": null, "discovery_method": null, "assignment_status": null},
  "records": [
    {"pl_name": "11 Com b", "hostname": "11 Com", "cluster_id": 0, "assignment_status": "assigned"},
    {"pl_name": "11 UMi b", "hostname": "11 UMi", "cluster_id": 0, "assignment_status": "assigned"}
  ]
}
```

An unassigned planet is still returned with its measurements and `"cluster_id": null`, `"assignment_status": "unassigned"`. Detail requests return `{"record": {...}}`; unknown planet identifiers return HTTP 404. Invalid query values return HTTP 400 with a clear error message. The API exposes no local artifact paths.

The API and generated data-layer tests are included in the full suite:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

## Current scope

The project includes the read-only dataset audit, approved reproducible preprocessing, K-means experiments, validation, a frozen exploratory primary configuration, descriptive outlier analysis, the Flask scientific data API, and all five ExoAtlas chapters. Supervised models remain out of scope.
