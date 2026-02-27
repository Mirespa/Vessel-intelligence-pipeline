# Global Vessel Intelligence Pipeline 🛰️🚢

## Overview
A data engineering pipeline designed to detect **"Dark Vessels"** (ships with disabled AIS) in the Baltic Sea. By cross-referencing Sentinel-1 SAR satellite imagery with AIS (Automatic Identification System) data, this tool identifies spatial anomalies where a physical vessel exists but no digital signal is broadcast. The current area of interest covers the Stockholm-Turku corridor.

## Tech Stack
* **Language:** Python 3.10+
* **Database:** PostgreSQL + PostGIS (Dockerized)
* **Satellite Data:** Copernicus Dataspace (Sentinel-1 GRD, VH polarization)
* **Spatial Libraries:** Rasterio, Psycopg2, Shapely, GeoPandas, TQDM, SciPy

## Architecture
1. **Ingestion:** Automated querying of Sentinel-1 SAR products via OData API and metadata storage in PostGIS.
2. **Download:** Streamed multi-scene download with per-file integrity checks
3. **Processing:** GCP-based reprojection to WGS-84, geographic AOI crop, and per-scene GeoTIFF export.
4. **Detection:** Vectorised CA-CFAR adaptive thresholding to extract vessel candidates, with GeoJSON export for QGIS.
5. **Spatial Join:** PostGIS distance-based query against AIS historical data to isolate dark targets.


## Getting Started

### 1. Prerequisites
Ensure you have **Docker** and **Python 3.10+** installed. You will also need a free account at the [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/).

### 2. Environment Setup
Create a `.env` file in the root directory:

```env
DB_HOST=
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_PORT=

COPERNICUS_USER=
COPERNICUS_PASSWORD=
```

### 3. Infrastructure
Spin up the database container:

```Bash
docker-compose up -d
```

### 4. Installation
Install the required Python dependencies:

```Bash
pip install python-dotenv psycopg2-binary requests rasterio tqdm scipy shapely geopandas matplotlib
```

### 5. Area of Interest
The corridor bounding box is defined once in config.py and shared across all pipeline stages:
```
AOI_BOUNDS = (18, 59, 23, 61) # (lon_min, lat_min, lon_max, lat_max)
```
To change the area, update this single value and re-run the pipeline from `ingestion.py`.

### 6. Running the Pipeline
Execute the modules in sequence from the root directory:

```Bash
# Step 1: Catalog scenes covering the Stockholm-Turku corridor
python -m src.ingestion

# Step 2: Download all catalogued scenes (approx. 1 GB per file)
python -m src.download

# Step 3: Reproject from GCPs to WGS-84 and crop to AOI
python -m src.processing

# Step 4: Detect vessel candidates with CA-CFAR
python -m src.detection
```

Each step skips files that already exist on disk, so the pipeline is safe to re-run after failures or partial completions.

### 7. Outputs
Each processed scene produces three files in `data/processed/`:

`*_vh_subset.tif`: Cropped GeoTIFF in WGS-84

`*_detections.json`: Pixel coordinates, peak dB, blob area, threshold

`*_detections.geojson`: WGS-84 point features, drag into QGIS directly

`*_quicklook.png`: SAR image with detection circles overlaid

## Project Structure
```
vessel_intelligence/
├── data/
│   ├── raw/                  # Downloaded Sentinel-1 ZIP files
│   └── processed/            # GeoTIFFs, detection JSON/GeoJSON, quicklooks
├── src/
│   ├── config.py             # Environment, paths, and AOI_BOUNDS
│   ├── database.py           # PostGIS connection handling
│   ├── ingestion.py          # Copernicus API querying and cataloging
│   ├── download.py           # Streamed downloads with integrity checks
│   ├── processing.py         # GCP reproject, AOI crop, GeoTIFF export
│   └── detection.py          # Vectorised CA-CFAR vessel detection
├── .env
├── .gitignore
├── docker-compose.yml
└── README.md
```

## Roadmap
[X] Automated metadata ingestion

[X] Streamed multi-scene download with integrity checks

[X] GCP reprojection and geographic AOI cropping

[X] Vectorised CA-CFAR vessel detection

[X] GeoJSON export for QGIS verification

[ ] Natural Earth land mask to suppress false detections on land

[ ] AIS data integration and dark vessel anomaly scoring

[ ] Confidence scoring and false-positive suppression