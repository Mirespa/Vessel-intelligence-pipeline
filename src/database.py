import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Database connection manager for PostGIS
class DatabaseManager:
    # Initialize connection parameters from environment variables
    def __init__(self):
        self.conn_params = {
            "host": os.getenv("DB_HOST"),
            "database": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "port": os.getenv("DB_PORT")
        }

    # Test the database connection and print the PostGIS version
    def test_connection(self):
        try:
            with psycopg2.connect(**self.conn_params) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT PostGIS_Full_Version();")
                    version = cur.fetchone()
                    print(f"Connected to PostGIS {version[0]}")
        except Exception as e:
            print(f"Database connection failed: {e}")

if __name__ == "__main__":
    db = DatabaseManager()
    db.test_connection()