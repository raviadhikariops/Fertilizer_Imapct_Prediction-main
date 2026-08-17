# Datasets Report — Fertilizer Impact Prediction

This document summarizes the CSV datasets included in this repository, explains their schema and usage, provides sample rows and guidance to extend or validate them, and points to the code modules that consume them.

## Summary
- Location: `data/`
- Primary files:
  - `crop_recommendation.csv` — crop feature samples and crop labels
  - `fertilizer_prediction.csv` — fertilizer recommendation training rows

These files are plain CSVs used by the backend for simple analytics and local ML model building. They are small, column-oriented datasets suitable for examples and local ML development.

---

## 1) crop_recommendation.csv

Path: `data/crop_recommendation.csv`

Purpose: sample environmental & soil feature vectors mapped to a crop label. Used by the app to build crop profiles, compute feature ranges, and provide simple crop-similarity recommendations.

Schema (header row):

- `N` (int) — Nitrogen content (numeric)
- `P` (int) — Phosphorous (numeric)
- `K` (int) — Potassium (numeric)
- `temperature` (float) — ambient temperature (°C)
- `humidity` (float) — relative humidity (%)
- `ph` (float) — soil pH
- `rainfall` (float) — total rainfall (mm)
- `label` (string) — crop name label (e.g., `rice`, `maize`)

Example (first 6 data rows):

```
N,P,K,temperature,humidity,ph,rainfall,label
90,42,43,20.87974371,82.00274423,6.502985292000001,202.9355362,rice
85,58,41,21.77046169,80.31964408,7.038096361,226.6555374,rice
60,55,44,23.00445915,82.3207629,7.840207144,263.9642476,rice
74,35,40,26.49109635,80.15836264,6.980400905,242.8640342,rice
78,42,42,20.13017482,81.60487287,7.628472891,262.7173405,rice
69,37,42,23.05804872,83.37011772,7.073453503,251.0549998,rice
```

Notes and observations:
- Many rows are labeled `rice` and `maize` in this example dataset; the file contains multiple crops.
- Numeric columns are mostly integer-like for N,P,K and floats for environmental measurements.
- The dataset is suitable for computing profile averages (per-crop mean), feature ranges, and similarity measures as implemented in the repo.

How the app uses this file:
- `backend/app.py` loads and summarizes this file via `load_crop_profiles()` and `load_feature_ranges()` to compute `CROP_PROFILES` and `FEATURE_RANGES` used at runtime. See: [backend/app.py](backend/app.py#L939-L976).

Recommendations for extending:
- Keep the header exact and columns in the same order when appending rows.
- Add additional crop rows for under-represented crops to improve profile stability.
- For larger datasets, consider converting to Parquet/SQLite and using `scripts/load_large_csv.py` to ingest in chunks.

---

## 2) fertilizer_prediction.csv

Path: `data/fertilizer_prediction.csv`

Purpose: rows used to build fertilizer recommendation ML models (or to serve as a lookup example). Each row maps environmental/soil/crop features to a recommended `Fertilizer Name`.

Schema (header row):

- `Temparature` (int) — ambient temperature (°C). Note the header spelling `Temparature` (preserve it when appending).
- `Humidity ` (int) — relative humidity (%) — note the header includes a trailing space in some rows; keep exact header.
- `Moisture` (int) — soil moisture
- `Soil Type` (string) — categorical soil class (Sandy, Loamy, Clayey, etc.)
- `Crop Type` (string) — categorical crop name (Maize, Wheat, Cotton, etc.)
- `Nitrogen` (int) — N content
- `Potassium` (int) — K content
- `Phosphorous` (int) — P content
- `Fertilizer Name` (string) — the target label (Urea, DAP, 14-35-14, Organic, etc.)

Example (first 6 data rows):

```
Temparature,Humidity ,Moisture,Soil Type,Crop Type,Nitrogen,Potassium,Phosphorous,Fertilizer Name
26,52,38,Sandy,Maize,37,0,0,Urea
29,52,45,Loamy,Sugarcane,12,0,36,DAP
34,65,62,Black,Cotton,7,9,30,14-35-14
32,62,34,Red,Tobacco,22,0,20,28-28
28,54,46,Clayey,Paddy,35,0,0,Urea
26,52,35,Sandy,Barley,12,10,13,17-17-17
```

Notes and observations:
- Headers include inconsistent spacing and a misspelling (`Temparature`, `Humidity `). The consuming code currently expects these exact header strings (see `backend/ml_models.py` and `backend/app.py`).
- The repo contains code to build models from this CSV: `_build_fertilizer_models()` in `backend/ml_models.py`. See: [backend/ml_models.py](backend/ml_models.py#L103-L170).

How the app uses this file:
- `backend/ml_models.py` reads `data/fertilizer_prediction.csv` in `_build_fertilizer_models()` to construct training rows used by the in-repo model builder (used when prebuilt model artifacts are absent). Also `backend/app.py` loads fertilizer rows with `load_fertilizer_rows()` for simple lookup. See: [backend/app.py](backend/app.py#L992-L1008).

Recommendations for extending:
- Normalize header names before appending or when importing into other tooling: rename `Temparature` → `temperature`, `Humidity ` → `humidity` (trim spaces). If you prefer to keep the existing code unchanged, append rows using the exact current headers.
- Prefer consistent capitalization of categorical fields (soil/crop names) to reduce cardinality noise.

---

## Provenance

- There is no script included in the repository that *generated* these CSVs (no explicit data-generation or scraping notebook found). The codebase consumes these CSVs but does not claim they were produced by a particular script or external module.
- The main consumers are:
  - `backend/app.py` — `load_crop_profiles()`, `load_feature_ranges()`, `load_fertilizer_rows()` (see [backend/app.py](backend/app.py#L939-L1008)).
  - `backend/ml_models.py` — `_build_fertilizer_models()` and other ML helpers that read the fertilizer CSV (see [backend/ml_models.py](backend/ml_models.py#L103-L170)).

If you need to record provenance metadata (who created the file, when, and by which process), add a small YAML or JSON sidecar file next to each CSV (for example `crop_recommendation.csv.meta.json`) with fields like `created_by`, `source`, `created_at`, and `generation_script`.

---

## How to safely add rows (recommended practices)

1. Make a backup copy before editing:

```powershell
copy data\crop_recommendation.csv data\crop_recommendation.csv.bak
copy data\fertilizer_prediction.csv data\fertilizer_prediction.csv.bak
```

2. Append a single row safely using a small Python snippet (validates columns):

```python
import csv

def append_row(path, row_dict, header):
    with open(path, 'r', encoding='utf-8', newline='') as fh:
        reader = csv.DictReader(fh)
        if set(header) != set(reader.fieldnames):
            raise SystemExit('Header mismatch')
    with open(path, 'a', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=reader.fieldnames)
        writer.writerow(row_dict)

# Example usage: provide keys exactly matching the existing header names
```

3. For bulk additions (>10k rows):
- Convert to Parquet or load into SQLite using `scripts/load_large_csv.py` to avoid repeated CSV parsing costs. The script supports chunked ingestion and is suitable for larger datasets.

4. Validate categorical values and trim whitespace programmatically before insertion. Example: lowercase crop names, strip spaces from `Humidity ` header values (or rename header first).

---

## Suggested quick improvements (next steps)

- Add a small normalization script to standardize headers (`Temparature` → `temperature`, trim spaces) and optionally rewrite the CSV to canonical headers.
- Add JSON sidecar provenance files with `created_at`, `author`, and `notes` fields for each CSV.
- Add a `data/schema.json` with JSON Schema for each dataset to enable automated validation before ingesting new rows.
- Add a short unit test to ensure `backend/ml_models.py` can read the fertilizer CSV and that `backend/app.py` loads crop profiles without exceptions.

---

If you want, I can:
- Create/commit a header-normalization script and canonicalized copies of the two CSVs.
- Add `data/DATASETS_SCHEMA.json` and a validation helper that runs before ingestion.
- Generate a small synthetic-data generator to augment either dataset with plausible rows.

Which of these would you like me to do next?
