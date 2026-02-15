# Global Vessel Intelligence Pipeline 🛰️🚢

## Overview
A high-performance data engineering pipeline designed to detect **"Dark Vessels"** (ships with disabled AIS) in the Baltic Sea. By cross-referencing **Sentinel-1 SAR** satellite imagery with **AIS (Automatic Identification System)** data, this tool identifies spatial anomalies where a physical vessel exists but no digital signal is broadcast.

## Tech Stack
* **Language:** Python 3.10+
* **Database:** PostgreSQL + PostGIS (Dockerized)
* **Satellite Data:** Copernicus Dataspace (Sentinel-1 GRD)
* **Spatial Libraries:** GeoPandas, Shapely, Rasterio

## Architecture
1. **Ingestion:** Automated querying of Sentinel-1 SAR products via API.
2. **Preprocessing:** Calibration, Speckle Filtering, and Land Masking using Python.
3. **Detection:** CFAR (Constant False Alarm Rate) algorithm to extract vessel coordinates.
4. **Spatial Join:** PostGIS distance-based query against AIS historical data.