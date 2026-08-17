import sqlite3
import os

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fertilizer.db')
conn = sqlite3.connect(DB)
cur = conn.cursor()
for table in ('crop_recommendation', 'fertilizer_prediction'):
    try:
        cur.execute(f"SELECT count(*) FROM {table}")
        n = cur.fetchone()[0]
    except Exception as e:
        n = f'error: {e}'
    print(table, n)
conn.close()
