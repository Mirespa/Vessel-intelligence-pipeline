# Database connection manager for PostGIS

import psycopg2
from src.config import config

class DatabaseManager:
    @staticmethod
    def get_conn():
        return psycopg2.connect(
            host=config.DB_HOST,
            database=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASS,
            port=config.DB_PORT
        )

    def test_connection(self):
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT PostGIS_Full_Version();")
                    print(f"Connected to PostGIS: {cur.fetchone()[0][:30]}...")
        except Exception as e:
            print(f"DB Connection Failed: {e}")