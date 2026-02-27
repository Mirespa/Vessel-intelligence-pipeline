# Land mask utility - zeros out land pixels in a GeoTIFF before detection
#
# Downloads Natural Earth 10m land polygons on first run and reuses them after that.

import requests
import zipfile
import numpy as np
import rasterio
import geopandas as gpd
from rasterio.features import geometry_mask
from shapely.geometry import box
from src.config import config

# Natural Earth 10m land polygons
LAND_URL  = "https://naciscdn.org/naturalearth/10m/physical/ne_10m_land.zip"
LAND_ZIP  = config.PROCESSED_DIR / "ne_10m_land.zip"
LAND_SHP  = config.PROCESSED_DIR / "ne_10m_land.shp"


def _download_land_polygons():
    # Only download once — reuse on subsequent runs
    if LAND_SHP.exists():
        return

    print("Downloading Natural Earth land polygons...")
    r = requests.get(LAND_URL, stream=True)
    r.raise_for_status()

    with open(LAND_ZIP, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)

    with zipfile.ZipFile(LAND_ZIP) as z:
        z.extractall(config.PROCESSED_DIR)

    # Clean up the ZIP once extracted
    LAND_ZIP.unlink()
    print("Land polygons ready.")


def apply_land_mask(tif_path):
    # Zero out all pixels that fall on land so CFAR only sees water clutter
    _download_land_polygons()

    with rasterio.open(tif_path) as src:
        bounds  = src.bounds
        data    = src.read(1).astype(np.float32)
        meta    = src.meta.copy()
        tf      = src.transform
        h, w    = src.height, src.width

    # Clip land polygons to the scene extent for speed and build a boolean mask of land pixels
    scene_bounds = box(bounds.left, bounds.bottom, bounds.right, bounds.top)
    land = gpd.read_file(LAND_SHP)
    land_clipped = land.clip(scene_bounds)

    if land_clipped.empty:
        # No land intersects this scene, nothing to mask
        return

    # Build a boolean mask where True = land pixel
    land_pixels = geometry_mask(
        land_clipped.geometry,
        transform=tf,
        invert=True,    # invert=True means True inside polygons (land)
        out_shape=(h, w),
    )

    # Zero out land pixels so _load_band in detection.py will then treat
    # these as invalid and replace them with NaN
    data[land_pixels] = 0.0

    # Overwrite the processed GeoTIFF with land pixels zeroed
    meta.update({"dtype": "float32"})
    with rasterio.open(tif_path, "w", **meta) as dst:
        dst.write(data, 1)

    n_masked = int(land_pixels.sum())
    print(f"Land mask applied: {n_masked:,} land pixels zeroed in {tif_path.name}")




















