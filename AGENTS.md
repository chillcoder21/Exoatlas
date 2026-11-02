# ExoAtlas project guidance

## Architecture

- `frontend/` is the React + TypeScript + Vite client. Use CSS Modules for component styles and CSS custom properties for shared design tokens.
- `backend/` is the Python + Flask REST API. Keep API behavior small and explicit; add persistence only when a concrete requirement calls for it.
- `data/raw/` is reserved for the original NASA Exoplanet Archive CSV. Keep raw source data out of Git and never edit it in place.
- Keep model training and data preparation separate from request handling when those stages are approved and implemented.
- Do not add empty directories or placeholder modules for planned experiences.

## Scientific integrity

- Do not invent, simulate, or present fabricated planet records as observations.
- Inspect the supplied CSV before reporting row counts, column availability, missingness, or data quality. Record the source and download date when presenting results.
- Treat the planned clustering features and transformations as hypotheses to validate against the actual data. Do not silently drop eccentricity zeros or change feature transformations.
- Label feature choices, units, transformations, and model settings wherever results are eventually shown. Distinguish measured values from derived values.
- Preserve the source CSV unchanged. Write derived data and models to separate, documented locations.

## Development rules

- Keep changes scoped to the current milestone. Do not implement the data pipeline or clustering until the user approves that milestone.
- Prefer the smallest dependency set that supports the current work. Add D3, Motion, pandas, NumPy, scikit-learn, Joblib, and test packages when implementation needs them, rather than during initial setup.
- Keep API responses JSON and use clear HTTP status codes. Do not add CORS, authentication, or database infrastructure until a use case requires them.
- Run the relevant build or checks after making changes, and report the commands and results accurately.
- Explain non-obvious scientific and architectural decisions in code or project documentation.
