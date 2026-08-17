import sqlite3
import os
DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fertilizer.db')
conn = sqlite3.connect(DB)
cur = conn.cursor()

def inspect_table(table, limit=10):
    print('\n--- TABLE:', table, '---')
    cur.execute(f"PRAGMA table_info({table})")
    cols = cur.fetchall()
    print('COLUMNS:')
    for c in cols:
        print(' ', c)
    cur.execute(f"SELECT count(*) FROM {table}")
    print('COUNT:', cur.fetchone()[0])
    cur.execute(f"SELECT * FROM {table} LIMIT {limit}")
    rows = cur.fetchall()
    if rows:
        print('\nSAMPLE ROWS:')
        # print header
        names = [c[1] for c in cols]
        print(' | '.join(names))
        for r in rows:
            print(' | '.join(str(x) for x in r))
    else:
        print('No rows')

for t in ('crop_recommendation','fertilizer_prediction'):
    inspect_table(t, limit=5)

conn.close()
