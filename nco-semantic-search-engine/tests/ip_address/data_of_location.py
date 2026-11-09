import os
import sys
import random
import psycopg2
from dotenv import load_dotenv

# Add the project root to sys.path so we can import utils.ip_location
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from utils.ip_location import resolve_ip_location

def get_database_url():
    load_dotenv()
    return os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/statathon_nco")

# A pool of valid Indian public IPs. We do not hardcode the locations (e.g. state/city)
# associated with them, but rather let the ip-api.com resolution handle it.
PUBLIC_IPS = [
    "14.139.182.2",   
    "14.139.60.2",    
    "14.139.116.2",   
    "14.139.161.2",   
    "14.139.155.2",   
    "14.139.185.2",   
    "117.239.180.2",  
    "117.211.160.2",  
    "117.211.89.2",   
    "117.211.75.2",   
    "117.211.120.2",  
    "117.211.140.2",  
    "14.139.206.2",   
    "14.139.197.2",   
    "14.139.208.2",   
    "103.21.124.0",
    "103.22.100.0",
    "103.23.104.0",
    "103.24.112.0",
    "103.25.128.0"
]

def main():
    db_url = get_database_url()
    
    rows_processed = 0
    rows_updated = 0
    rows_skipped = 0
    
    print("Connecting to database...")
    try:
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cur:
            # Read every row id
            cur.execute("SELECT id FROM prompt_history")
            records = cur.fetchall()
            
            for record in records:
                row_id = record[0]
                rows_processed += 1
                
                # Pick a random IP to simulate organic search traffic
                test_ip = random.choice(PUBLIC_IPS)
                
                # Resolve the IP automatically
                location = resolve_ip_location(test_ip)
                
                city = location.get('city', '')
                state = location.get('state', '')
                country = location.get('country', '')
                
                if state and country:
                    # Update only geo fields
                    cur.execute(
                        """
                        UPDATE prompt_history
                        SET geo_city = %s, geo_state = %s, geo_country = %s
                        WHERE id = %s
                        """,
                        (city, state, country, row_id)
                    )
                    rows_updated += 1
                else:
                    rows_skipped += 1
            
            # Commit transaction safely at the end
            conn.commit()
            
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            
    print("\n==================================")
    print("Dummy Location Generator")
    print("==================================")
    print(f"Rows Processed : {rows_processed}")
    print(f"Rows Updated   : {rows_updated}")
    print(f"Rows Skipped   : {rows_skipped}")
    print("\nCompleted Successfully")

if __name__ == "__main__":
    main()
