import os
import psycopg2
from dotenv import load_dotenv

def get_database_url():
    load_dotenv()
    return os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/statathon_nco")

def main():
    db_url = get_database_url()
    
    rows_cleared = 0
    
    print("Connecting to database...")
    try:
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cur:
            # Update every row to clear only the geo fields
            cur.execute(
                """
                UPDATE prompt_history
                SET geo_city = '', geo_state = '', geo_country = ''
                """
            )
            # The number of rows affected by the UPDATE statement
            rows_cleared = cur.rowcount
            
            # Commit the cleanup transaction
            conn.commit()
            
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            
    print("\n==================================")
    print("Location Cleanup")
    print("==================================")
    print(f"Rows Cleared : {rows_cleared}")
    print("\nCompleted Successfully")

if __name__ == "__main__":
    main()
