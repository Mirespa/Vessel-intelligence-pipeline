import os
import requests
import psycopg2
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

class SentinelPipeline:
    def __init__(self):
        self.db_params = {
            "host": os.getenv("DB_HOST"),
            "database": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "port": os.getenv("DB_PORT")
        }
        self.search_url = "https://catalogue.dataspace.copernicus.eu/resto/api/collections/Sentinel1/search.json"

    def init_db(self):
        """Initializes the database table with spatial support."""
        query = """
        CREATE EXTENSION IF NOT EXISTS postgis;
        CREATE TABLE IF NOT EXISTS satellite_catalog (
            id UUID PRIMARY KEY,
            title TEXT,
            acquisition_date TIMESTAMP,
            size_bytes BIGINT,
            footprint GEOMETRY(Polygon, 4326)
        );
        CREATE INDEX IF NOT EXISTS idx_satellite_footprint ON satellite_catalog USING GIST(footprint);
        """
        with psycopg2.connect(**self.db_params) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
            conn.commit()

    def store_scenes(self, scenes):
        """Inserts the 5 discovered scenes into PostgreSQL."""
        with psycopg2.connect(**self.db_params) as conn:
            with conn.cursor() as cur:
                for scene in scenes:
                    props = scene['properties']
                    # Extract GeoJSON geometry for PostGIS
                    geom_json = str(scene['geometry']) 
                    
                    cur.execute("""
                        INSERT INTO satellite_catalog (id, title, acquisition_date, size_bytes, footprint)
                        VALUES (%s, %s, %s, %s, ST_GeomFromGeoJSON(%s))
                        ON CONFLICT (id) DO NOTHING;
                    """, (
                        scene['id'], 
                        props['title'], 
                        props['startDate'], 
                        props.get('services', {}).get('download', {}).get('size', 0),
                        geom_json
                    ))
                conn.commit()
        logging.info(f"✅ Successfully stored {len(scenes)} scenes in Docker DB.")

if __name__ == "__main__":
    pipeline = SentinelPipeline()
    pipeline.init_db()
    
    # Use your working search logic
    params = {"box": "21.5,59.8,22.8,60.5", "productType": "GRD", "maxRecords": 5}
    response = requests.get(pipeline.search_url, params=params)
    
    if response.status_code == 200:
        scenes = response.json().get('features', [])
        pipeline.store_scenes(scenes)