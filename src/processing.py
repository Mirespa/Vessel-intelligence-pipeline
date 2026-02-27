# 03 - Process Sentinel-1 data: unzip, reproject from GCPs, crop to AOI, save
#
# Sentinel-1 GRD products have no CRS in their GeoTIFF metadata. Geographic
# location is stored as GCP tie-points (a grid of lat/lon anchor pixels).
# We must reproject to EPSG:4326 using those GCPs before we can crop by
# geographic bounding box.

import zipfile
import numpy as np
import rasterio
import rasterio.mask
from rasterio.crs import CRS
from rasterio.warp import reproject, Resampling, calculate_default_transform
from rasterio.io import MemoryFile
from shapely.geometry import box
from tqdm import tqdm
from src.config import config
from src.landmask import apply_land_mask

# Build the AOI polygon from the single source of truth in config
AOI_polygon = box(*config.AOI_BOUNDS)
WGS84 = CRS.from_epsg(4326)


def _reproject_with_gcps(src):
    # Read the GCPs that Sentinel-1 uses instead of a standard geotransform
    gcps, gcp_crs = src.gcps
    if not gcps:
        raise ValueError("No GCPs found in this file. Cannot geolocate.")

    # Calculate the output transform and dimensions for a WGS-84 grid
    transform, width, height = calculate_default_transform(
        gcp_crs, WGS84, src.width, src.height, gcps=gcps
    )

    # Warp the raw pixel data into geographic space using the GCPs
    data_wgs84 = np.zeros((src.count, height, width), dtype=np.float32)
    reproject(
        source=rasterio.band(src, 1),
        destination=data_wgs84[0],
        gcps=gcps,
        src_crs=gcp_crs,
        dst_crs=WGS84,
        dst_transform=transform,
        resampling=Resampling.bilinear,
    )

    # Build a fresh in-memory raster in EPSG:4326 that rasterio.mask can work with
    meta = src.meta.copy()
    meta.update({
        "crs":       WGS84,
        "transform": transform,
        "width":     width,
        "height":    height,
        "dtype":     "float32",
        "count":     1,
    })
    return data_wgs84, meta


def _process_scene(zip_path):
    scene_title = zip_path.stem
    out_path = config.PROCESSED_DIR / f"{scene_title}_vh_subset.tif"

    # Skip scenes that have already been processed
    if out_path.exists():
        print(f"Already processed, skipping: {zip_path.name}")
        return

    with tqdm(total=6, desc=scene_title[:35]) as pbar:

        # Step 1: Open the ZIP archive
        pbar.set_description("Opening ZIP archive")
        with zipfile.ZipFile(zip_path, "r") as z:
            pbar.update(1)

            # Step 2: Locate the VH polarization TIFF inside the archive
            pbar.set_description("Finding VH channel")
            vh_files = [f for f in z.namelist() if "-vh-" in f.lower() and f.endswith(".tiff")]
            if not vh_files:
                print(f"No VH channel found in {zip_path.name}, skipping.")
                return
            pbar.update(1)

            # Step 3: Reproject from GCPs to EPSG:4326
            pbar.set_description("Reprojecting from GCPs to WGS-84 (this takes a moment)")
            with z.open(vh_files[0]) as tiff:
                with MemoryFile(tiff) as memfile:
                    with memfile.open() as src:
                        data_wgs84, meta = _reproject_with_gcps(src)
            pbar.update(1)

            # Step 4: Crop to the AOI bounding box
            pbar.set_description("Cropping to AOI")
            with MemoryFile() as mem:
                with mem.open(**meta) as tmp:
                    tmp.write(data_wgs84)
                with mem.open() as tmp:
                    data_cropped, crop_transform = rasterio.mask.mask(
                        tmp, [AOI_polygon], crop=True, nodata=0
                    )

            meta.update({
                "height":    data_cropped.shape[1],
                "width":     data_cropped.shape[2],
                "transform": crop_transform,
            })
            pbar.update(1)

            # Step 5: Save the cropped subset to disk
            pbar.set_description("Saving processed GeoTIFF")
            with rasterio.open(out_path, "w", **meta) as dest:
                dest.write(data_cropped)
            pbar.update(1)

        # Step 6: Zero out land pixels so detection only runs over water
        pbar.set_description("Applying land mask")
        apply_land_mask(out_path)
        pbar.update(1)

    print(f"Saved: {out_path.name}")


def process_all():
    zips = list(config.RAW_DIR.glob("*.zip"))
    if not zips:
        print("No ZIP files found. Run download.py first.")
        return

    # Filter to only scenes that have a VH channel before starting
    valid_zips = []
    for z in zips:
        if not zipfile.is_zipfile(z):
            print(f"Corrupt ZIP, skipping: {z.name}")
            continue
        with zipfile.ZipFile(z) as zf:
            has_vh = any("-vh-" in f.lower() and f.endswith(".tiff") for f in zf.namelist())
        if has_vh:
            valid_zips.append(z)
        else:
            print(f"No VH channel, skipping: {z.name}")

    if not valid_zips:
        print("No scenes with VH channel found.")
        return

    print(f"Processing {len(valid_zips)} VH scene(s)...")

    for i, zip_path in enumerate(valid_zips, start=1):
        print(f"\nScene {i}/{len(valid_zips)}: {zip_path.name}")
        _process_scene(zip_path)

    print("\nAll scenes processed.")


if __name__ == "__main__":
    process_all()