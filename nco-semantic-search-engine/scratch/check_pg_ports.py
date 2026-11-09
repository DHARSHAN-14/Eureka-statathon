import psycopg2

# Try PostgreSQL 18 on port 5433
for port in [5433, 5434, 5432]:
    for db in ['statathon_nco', 'postgres']:
        try:
            conn = psycopg2.connect(
                dbname=db, user='postgres', password='postgres',
                host='localhost', port=port
            )
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("SELECT version();")
            ver = cur.fetchone()[0]
            
            cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
            has_vector = cur.fetchone()
            
            print(f"Port {port}, DB '{db}': {ver[:60]}... | pgvector: {'YES' if has_vector else 'NO'}")
            
            if not has_vector and db == 'statathon_nco':
                try:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    print(f"  -> pgvector enabled on port {port}!")
                except Exception as e:
                    print(f"  -> Cannot enable: {e}")
            
            conn.close()
        except Exception as e:
            pass  # Skip if can't connect
