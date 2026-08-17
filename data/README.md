Large dataset guidance
=======================

This folder contains instructions and helpers for loading and working with large CSV datasets.

Recommended approaches
- SQLite (local): Use `scripts/load_large_csv.py` to stream CSV rows into a SQLite database in chunks.
- Parquet (columnar): Use the same script with `--parquet-dir` to write chunked Parquet files for analytics.
- Cloud storage: Upload Parquet parts to S3/GCS for processing with cloud compute or BigQuery.

Usage examples

Load into SQLite:

```bash
python scripts/load_large_csv.py --csv /path/to/huge.csv --db data/huge.db --table observations --chunksize 50000
```

Write Parquet parts:

```bash
python scripts/load_large_csv.py --csv /path/to/huge.csv --parquet-dir data/huge_parquet --chunksize 100000
```

Tips
- Set `chunksize` according to memory available. 50k-200k rows is a good starting point.
- For production analytics prefer Parquet and cloud object storage.
- Consider adding a schema JSON to validate columns before importing.
