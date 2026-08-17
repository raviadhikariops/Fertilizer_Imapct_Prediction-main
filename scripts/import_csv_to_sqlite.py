#!/usr/bin/env python3
"""Import data CSVs into the project's SQLite database (fertilizer.db).

Creates two tables if they don't exist:
- crop_recommendation
- fertilizer_prediction

This script normalizes known header quirks and inserts rows safely.
"""
import csv
import os
import sqlite3
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(BASE_DIR, "fertilizer.db")

def create_tables(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS crop_recommendation (
            id INTEGER PRIMARY KEY,
            N INTEGER,
            P INTEGER,
            K INTEGER,
            temperature REAL,
            humidity REAL,
            ph REAL,
            rainfall REAL,
            label TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS fertilizer_prediction (
            id INTEGER PRIMARY KEY,
            temperature REAL,
            humidity REAL,
            moisture REAL,
            soil_type TEXT,
            crop_type TEXT,
            nitrogen REAL,
            potassium REAL,
            phosphorous REAL,
            fertilizer_name TEXT
        )
        """
    )
    conn.commit()

def import_crop_csv(conn, path):
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        expected = ["N","P","K","temperature","humidity","ph","rainfall","label"]
        missing = [c for c in expected if c not in reader.fieldnames]
        if missing:
            raise SystemExit(f"crop_recommendation.csv missing columns: {missing}")
        rows = []
        for r in reader:
            rows.append((
                int(float(r["N"] or 0)),
                int(float(r["P"] or 0)),
                int(float(r["K"] or 0)),
                float(r["temperature"] or 0),
                float(r["humidity"] or 0),
                float(r["ph"] or 0),
                float(r["rainfall"] or 0),
                r["label"].strip()
            ))
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO crop_recommendation (N,P,K,temperature,humidity,ph,rainfall,label) VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return len(rows)

def import_fertilizer_csv(conn, path):
    # normalize headers: accept 'Temparature' and 'Humidity ' with trailing space
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        # map known header variants to canonical names
        mapping = {}
        for name in reader.fieldnames:
            key = name.strip().lower()
            if key.startswith("tempar") or key.startswith("temper"):
                mapping[name] = "temperature"
            elif key.startswith("humid"):
                mapping[name] = "humidity"
            elif key == "moisture":
                mapping[name] = "moisture"
            elif key in ("soil type", "soil"):
                mapping[name] = "soil_type"
            elif key in ("crop type", "crop"):
                mapping[name] = "crop_type"
            elif key == "nitrogen":
                mapping[name] = "nitrogen"
            elif key in ("potassium", "k"):
                mapping[name] = "potassium"
            elif key in ("phosphorous", "phosphorus"):
                mapping[name] = "phosphorous"
            elif "fertilizer" in key:
                mapping[name] = "fertilizer_name"
            else:
                mapping[name] = name

        rows = []
        for r in reader:
            # build a canonical dict
            cd = {mapping[k]: v for k,v in r.items()}
            rows.append((
                float(cd.get("temperature") or 0),
                float(cd.get("humidity") or 0),
                float(cd.get("moisture") or 0),
                (cd.get("soil_type") or "").strip(),
                (cd.get("crop_type") or "").strip(),
                float(cd.get("nitrogen") or 0),
                float(cd.get("potassium") or 0),
                float(cd.get("phosphorous") or 0),
                (cd.get("fertilizer_name") or "").strip(),
            ))

    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO fertilizer_prediction (temperature,humidity,moisture,soil_type,crop_type,nitrogen,potassium,phosphorous,fertilizer_name) VALUES (?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return len(rows)

def main():
    crop_csv = os.path.join(DATA_DIR, "crop_recommendation.csv")
    fert_csv = os.path.join(DATA_DIR, "fertilizer_prediction.csv")
    if not os.path.exists(crop_csv) or not os.path.exists(fert_csv):
        print("Data files not found in data/ directory")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    try:
        create_tables(conn)
        cur = conn.cursor()
        # Optional: clear existing rows to avoid duplicates
        cur.execute("DELETE FROM crop_recommendation")
        cur.execute("DELETE FROM fertilizer_prediction")
        conn.commit()

        n1 = import_crop_csv(conn, crop_csv)
        n2 = import_fertilizer_csv(conn, fert_csv)
        print(f"Imported {n1} crop rows and {n2} fertilizer rows into {DB_PATH}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
