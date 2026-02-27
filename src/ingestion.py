# 01 - Fetch satellite data and store in PostGIS

import requests
from tqdm import tqdm
from src.database import DatabaseManager
from src.config import config

AOI_BOX = "{},{},{},{}".format(*config.AOI_BOUNDS)

def run_ingestion():
    search_url = "https://catalogue.dataspace.copernicus.eu/resto/api/collections/Sentinel1/search.json"
    params = {
        "box": AOI_BOX,
        "productType": "GRD",
        "maxRecords": 15 # corridor needs 2-3 overlapping scenes, 15 gives room for recent passes
    }
    
    response = requests.get(search_url, params=params)
    if response.status_code != 200:
        print(f"Search failed: HTTP {response.status_code}")
        return

    scenes = response.json().get('features', [])
    if not scenes:
        print("No scenes found for the given area and filters.")
        return
    
    db = DatabaseManager()
    
    with db.get_conn() as conn:
        with conn.cursor() as cur:

            # Create the PostGIS extension and catalog table if they don't exist yet
            cur.execute("""
                CREATE EXTENSION IF NOT EXISTS postgis;
                CREATE TABLE IF NOT EXISTS satellite_catalog (
                    id               UUID PRIMARY KEY,
                    title            TEXT,
                    acquisition_date TIMESTAMP,
                    footprint        GEOMETRY(Polygon, 4326)
                );
            """)

            # Insert each scene, skipping any already in the catalog
            for s in tqdm(scenes, desc="Inserting scenes into DB"):
                cur.execute("""
                    INSERT INTO satellite_catalog (id, title, acquisition_date, footprint)
                    VALUES (%s, %s, %s, ST_GeomFromGeoJSON(%s))
                    ON CONFLICT (id) DO NOTHING;
                """, (
                    s["id"],
                    s["properties"]["title"],
                    s["properties"]["startDate"],
                    str(s["geometry"]),
                ))

    print(f"Cataloged {len(scenes)} scenes.")

if __name__ == "__main__":
    run_ingestion()