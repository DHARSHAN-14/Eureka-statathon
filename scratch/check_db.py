import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

try:
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    tables = cur.fetchall()
    print("Tables:")
    for t in tables:
        tablename = t[0]
        cur.execute(f"SELECT count(*) FROM {tablename}")
        cnt = cur.fetchone()[0]
        print(f"  - {tablename}: {cnt} rows")
except Exception as e:
    print("Error:", e)
finally:
    cur.close()
    conn.close()
