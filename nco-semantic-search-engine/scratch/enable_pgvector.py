import psycopg2

conn = psycopg2.connect(
    dbname='statathon_nco', user='postgres', password='postgres',
    host='localhost', port=5432
)
conn.autocommit = True
cur = conn.cursor()

try:
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    print("pgvector extension enabled successfully!")
except Exception as e:
    print(f"Error: {e}")
    print("You may need to install pgvector for PostgreSQL 18.")

# Verify
cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
result = cur.fetchone()
if result:
    print(f"Extension: {result[0]} v{result[1]}")
else:
    print("vector extension NOT found after attempt.")

conn.close()
