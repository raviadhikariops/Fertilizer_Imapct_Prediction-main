#!/usr/bin/env python3
"""Chunked CSV loader for large datasets.

Usage:
  python scripts/load_large_csv.py --csv /path/to/large.csv --db data/large.db --table large_table --chunksize 50000

The script reads the CSV in chunks and writes to a SQLite table (creating it if needed).
It can also write Parquet files instead by passing --parquet-dir.
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("The 'pandas' package is required. Install with: pip install pandas")
    sys.exit(1)


def to_sqlite(csv_path, db_path, table_name, chunksize=50000, if_exists="append"):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    first = True
    for i, chunk in enumerate(pd.read_csv(csv_path, chunksize=chunksize)):
        print(f"Writing chunk {i+1} (rows={len(chunk)}) to table '{table_name}'...")
        if first:
            chunk.to_sql(table_name, conn, if_exists="replace", index=False)
            first = False
        else:
            chunk.to_sql(table_name, conn, if_exists=if_exists, index=False)
    conn.close()
    print("Done writing to SQLite.")


def to_parquet(csv_path, out_dir, chunksize=50000):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, chunk in enumerate(pd.read_csv(csv_path, chunksize=chunksize)):
        out_file = out_dir / f"part-{i+1:04d}.parquet"
        print(f"Writing chunk {i+1} -> {out_file} (rows={len(chunk)})")
        chunk.to_parquet(out_file, index=False)
    print("Done writing Parquet parts.")


def main():
    parser = argparse.ArgumentParser(description="Load large CSV files in chunks into SQLite or Parquet parts.")
    parser.add_argument("--csv", required=True, help="Path to input CSV file")
    parser.add_argument("--db", default="data/large.db", help="SQLite DB path (used if --parquet-dir not set)")
    parser.add_argument("--table", default="large_table", help="SQLite table name")
    parser.add_argument("--chunksize", type=int, default=50000, help="Rows per chunk")
    parser.add_argument("--parquet-dir", default="", help="If set, write parquet files into this directory instead of SQLite")

    args = parser.parse_args()
    csv_path = args.csv
    if not os.path.exists(csv_path):
        print(f"CSV file not found: {csv_path}")
        sys.exit(2)

    if args.parquet_dir:
        to_parquet(csv_path, args.parquet_dir, chunksize=args.chunksize)
    else:
        to_sqlite(csv_path, args.db, args.table, chunksize=args.chunksize)


if __name__ == "__main__":
    main()
