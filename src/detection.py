# 04 - Detect vessel candidates in processed VH GeoTIFFs
#
# Loops over every scene produced by processing.py and writes a separate
# detections JSON and GeoJSON file for each one.
#
# Detection mode:
#   "cfar" - adapts the threshold to local clutter per pixel so bright
#            coastlines and islands in the corridor don't cause false hits

import json
import numpy as np
import rasterio
from pathlib import Path
from tqdm import tqdm
from scipy.ndimage import label, center_of_mass, uniform_filter
from src.config import config


def _load_band(path):
    # Read band 1 and replace nodata / physically invalid values with NaN
    with rasterio.open(path) as src:
        meta = src.meta.copy()
        data = src.read(1).astype(np.float32)
        nodata = src.nodata

    if nodata is not None:
        data[data == nodata] = np.nan
    data[data <= 0] = np.nan   # zero and negative have no meaning in power
    return data, meta


def _to_db(data):
    # Convert linear power values to decibels: 10 * log10(x)
    out = np.full_like(data, np.nan)
    valid = ~np.isnan(data)
    out[valid] = 10.0 * np.log10(data[valid])
    return out


def _drop_small_blobs(mask, min_area):
    # Remove blobs smaller than min_area pixels to filter out speckle noise
    labeled, _ = label(mask)
    sizes = np.bincount(labeled.ravel())
    sizes[0] = min_area + 1   # exclude background (label 0) from the filter
    mask[sizes[labeled] < min_area] = False


def _extract_detections(mask, data_db, threshold_map):
    # Find connected bright regions and record their centroid, peak, and size
    labeled, n_blobs = label(mask)
    if n_blobs == 0:
        return []

    detections = []
    for blob_id in range(1, n_blobs + 1):
        blob = labeled == blob_id
        row, col = center_of_mass(blob)
        peak = float(np.nanmax(data_db[blob]))

        # Use the lowest threshold inside the blob (most conservative value)
        thresh_vals = threshold_map[blob]
        valid_thresh = thresh_vals[~np.isnan(thresh_vals)]
        thresh = float(np.nanmin(valid_thresh)) if len(valid_thresh) else float("nan")

        detections.append({
            "pixel_row":    round(row, 2),
            "pixel_col":    round(col, 2),
            "peak_db":      round(peak, 3),
            "area_px":      int(blob.sum()),
            "threshold_db": round(thresh, 3),
        })
    return detections


def _apply_cfar(data_db, guard, train, pfa, min_area):
    # Cell-Averaging CFAR: compute a per-pixel threshold from the surrounding
    # clutter rather than using a single global value.
    #
    # The guard ring (inner band) is excluded so a bright vessel doesn't raise
    # its own local clutter estimate and hide itself.
    #
    # Threshold multiplier for exponentially-distributed clutter power:
    #   T = N * (P_fa ^ (-1/N) - 1)
    # where N is the number of training cells in the outer annulus.
    #
    # scipy.ndimage.uniform_filter computes the sliding box mean in vectorised
    # C — equivalent to the pixel loop but roughly 100x faster.

    if guard >= train:
        raise ValueError("train must be greater than guard.")

    n_outer  = (2 * train + 1) ** 2
    n_inner  = (2 * guard + 1) ** 2
    n_train  = n_outer - n_inner
    T        = n_train * (pfa ** (-1.0 / n_train) - 1.0)

    # Work in linear power so the mean is statistically correct
    linear = np.where(np.isnan(data_db), 0.0, 10.0 ** (data_db / 10.0))

    # Sliding box means for the outer and guard windows
    outer_mean = uniform_filter(linear, size=2 * train + 1, mode="reflect")
    inner_mean = uniform_filter(linear, size=2 * guard + 1, mode="reflect")

    # Training ring mean = weighted difference of the two box means
    mu = (outer_mean * n_outer - inner_mean * n_inner) / n_train

    # Adaptive threshold in linear power, converted to dB for comparison
    alpha    = T * mu
    alpha_db = np.where(alpha > 0, 10.0 * np.log10(np.maximum(alpha, 1e-30)), np.nan)

    mask = (~np.isnan(data_db)) & (~np.isnan(alpha_db)) & (data_db > alpha_db)
    threshold_map = alpha_db.astype(np.float32)

    _drop_small_blobs(mask, min_area)
    return mask, threshold_map


def _export_geojson(tif_path, detections, out_path):
    # Convert pixel coordinates to WGS-84 lat/lon using the scene geotransform
    # and write a GeoJSON file that can be dragged directly into QGIS
    with rasterio.open(tif_path) as src:
        transform = src.transform

    features = []
    for d in detections:
        lon, lat = transform * (d["pixel_col"], d["pixel_row"])
        features.append({
            "type": "Feature",
            "geometry": {
                "type":        "Point",
                "coordinates": [round(lon, 6), round(lat, 6)],
            },
            "properties": {
                "peak_db":      d["peak_db"],
                "area_px":      d["area_px"],
                "threshold_db": d["threshold_db"],
            },
        })

    geojson = {"type": "FeatureCollection", "features": features}
    with open(out_path, "w") as f:
        json.dump(geojson, f, indent=2)
    print(f"GeoJSON saved: {out_path.name}")


def _detect_scene(tif_path, guard, train, pfa, min_area):
    # Skip scenes that have already been detected
    out_json    = config.PROCESSED_DIR / f"{tif_path.stem}_detections.json"
    out_geojson = config.PROCESSED_DIR / f"{tif_path.stem}_detections.geojson"
    if out_json.exists() and out_geojson.exists():
        print(f"Already detected, skipping: {tif_path.name}")
        return

    with tqdm(total=5, desc=tif_path.stem[:35]) as pbar:

        # Step 1: Load the GeoTIFF from disk
        pbar.set_description("Loading GeoTIFF")
        data, meta = _load_band(tif_path)
        nodata_pct = round(np.isnan(data).mean() * 100, 1)
        pbar.update(1)

        # Step 2: Convert raw power values to decibels
        pbar.set_description("Converting to dB")
        data_db = _to_db(data)
        pbar.update(1)

        # Step 3: Run CA-CFAR to produce a binary hit mask
        pbar.set_description(f"Applying CA-CFAR (P_fa={pfa:.0e})")
        mask, threshold_map = _apply_cfar(data_db, guard, train, pfa, min_area)
        pbar.update(1)

        # Step 4: Label connected blobs and save results to JSON
        pbar.set_description("Extracting detections")
        detections = _extract_detections(mask, data_db, threshold_map)

        result = {
            "source":          str(tif_path),
            "image_shape":     list(data_db.shape),
            "nodata_pct":      nodata_pct,
            "detection_count": len(detections),
            "detections":      detections,
        }
        with open(out_json, "w") as f:
            json.dump(result, f, indent=2)
        pbar.update(1)

        # Step 5: Export geographic coordinates for QGIS
        pbar.set_description("Exporting GeoJSON for QGIS")
        _export_geojson(tif_path, detections, out_geojson)
        pbar.update(1)

    print(f"Found {len(detections)} vessel candidate(s).  (nodata: {nodata_pct}%)")


def run_detection(guard=2, train=8, pfa=1e-6, min_area=3):
    tifs = list(config.PROCESSED_DIR.glob("*_vh_subset.tif"))
    if not tifs:
        print("No processed GeoTIFFs found. Run processing.py first.")
        return

    print(f"Running detection on {len(tifs)} scene(s)...")

    for i, tif_path in enumerate(tifs, start=1):
        print(f"\nScene {i}/{len(tifs)}: {tif_path.name}")
        _detect_scene(tif_path, guard, train, pfa, min_area)

    print("\nAll scenes complete.")


if __name__ == "__main__":
    run_detection()