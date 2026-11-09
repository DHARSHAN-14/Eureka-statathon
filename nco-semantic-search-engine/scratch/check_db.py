import psycopg2

conn = psycopg2.connect(
    dbname='statathon_nco', user='postgres', password='postgres',
    host='localhost', port=5433
)
cur = conn.cursor()

cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' ORDER BY table_name
""")
tables = [r[0] for r in cur.fetchall()]
print(f"Tables ({len(tables)}):")
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM \"{t}\"")
    count = cur.fetchone()[0]
    print(f"  {t}: {count} rows")

conn.close()
