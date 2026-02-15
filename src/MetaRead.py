import zipfile
import rasterio
from rasterio.io import MemoryFile

zip_path = "data/raw/S1A_IW_GRDH_1SDV_20260101T162132_20260101T162157_062576_07D7CD_DD2F.SAFE.zip" # Replace with your actual filename

with zipfile.ZipFile(zip_path, 'r') as z:
    # Find the largest .tiff file (the measurement data)
    tiff_files = [f for f in z.namelist() if f.endswith('.tiff') and 'measurement' in f]
    
    with z.open(tiff_files[0]) as tiff:
        with MemoryFile(tiff) as memfile:
            with memfile.open() as dataset:
                print(f"✅ Image Width: {dataset.width}")
                print(f"✅ Image Height: {dataset.height}")
                print(f"✅ Coordinate System: {dataset.crs}")