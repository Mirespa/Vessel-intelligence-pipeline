# Configuration management (Setting menu)

import os
from pathlib import Path
from dotenv import load_dotenv

# Find the root directory
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Config:
    # Database
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", "vessel_intelligence")
    DB_USER = os.getenv("DB_USER")
    DB_PASS = os.getenv("DB_PASSWORD")
    DB_PORT = os.getenv("DB_PORT", "5432")

    # Copernicus API
    COPERNICUS_USER = os.getenv("COPERNICUS_USER")
    COPERNICUS_PASS = os.getenv("COPERNICUS_PASSWORD")
    
    # Folders
    RAW_DIR = BASE_DIR / "data" / "raw"
    PROCESSED_DIR = BASE_DIR / "data" / "processed"

    # AOI bounding box in geographic coordinates (min_lon, min_lat, max_lon, max_lat)
    AOI_BOUNDS = (18, 59, 23, 61)

    def __init__(self):
        # Create folders if they don't exist
        self.RAW_DIR.mkdir(parents=True, exist_ok=True)
        self.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

config = Config()