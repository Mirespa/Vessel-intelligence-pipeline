# 02 - Download satellite data using Copernicus API and store locally

import requests
import zipfile
from tqdm import tqdm
from src.database import DatabaseManager
from src.config import config

def _get_token():
    # Exchange Copernicus credentials for a short-lived bearer token
    url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    r = requests.post(url, data={
        "grant_type": "password",
        "client_id":  "cdse-public",
        "username":   config.COPERNICUS_USER,
        "password":   config.COPERNICUS_PASS,
    })
    return r.json().get("access_token")


def _download_scene(scene_id, title, token):
    target_path = config.RAW_DIR / f"{title}.zip"

    if target_path.exists():
        # Check the existing file is actually a valid ZIP before skipping
        if zipfile.is_zipfile(target_path):
            print(f"Already exists, skipping: {title}")
            return
        else:
            print(f"Corrupt ZIP found, re-downloading: {title}")
            target_path.unlink()

    url = f"https://download.dataspace.copernicus.eu/odata/v1/Products({scene_id})/$value"
    response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, stream=True)
    total_size = int(response.headers.get("content-length", 0))

    # Stream the file to disk in 1 MB chunks and show a per-scene progress bar
    with open(target_path, "wb") as f, tqdm(
        desc=title[:30] + "...",
        total=total_size,
        unit="iB",
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            bar.update(f.write(chunk))

    print(f"Saved: {target_path.name}")


def download():
    db = DatabaseManager()
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title FROM satellite_catalog;")
            scenes = cur.fetchall()

    if not scenes:
        print("No scenes in DB. Run ingestion.py first.")
        return

    print(f"Downloading {len(scenes)} scene(s)...")

    # Fetch a single token up front — valid for all scenes in this session
    token = _get_token()

    for i, (scene_id, title) in enumerate(scenes, start=1):
        print(f"\nScene {i}/{len(scenes)}: {title}")
        _download_scene(scene_id, title, token)

    print("\nAll downloads complete.")


if __name__ == "__main__":
    download()