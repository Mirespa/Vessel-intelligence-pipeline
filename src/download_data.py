import os
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_token():
    url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    data = {
        "grant_type": "password",
        "client_id": "cdse-public",
        "username": os.getenv("COPERNICUS_USER"),
        "password": os.getenv("COPERNICUS_PASSWORD"),
    }
    response = requests.post(url, data=data)
    
    if response.status_code != 200:
        print(f"❌ Token Failed: {response.status_code}")
        print(f"Response: {response.text}") # Look for "invalid_user_credentials"
        return None
        
    return response.json().get("access_token")

def download_latest():
    # Get Scene ID from DB
    conn = psycopg2.connect(
        host="localhost",
        database="vessel_intelligence",
        user="admin",
        password=os.getenv("DB_PASSWORD"),
        port="5432"
    )
    cur = conn.cursor()
    cur.execute("SELECT id, title FROM satellite_catalog LIMIT 1;")
    scene = cur.fetchone()
    cur.close()
    conn.close()

    if not scene:
        print("❌ No scenes found in database. Run ingestion.py first!")
        return

    scene_id, title = scene
    
    token = get_token()
    if not token: return

    # 2. Download
    os.makedirs("data/raw", exist_ok=True)
    url = f"https://download.dataspace.copernicus.eu/odata/v1/Products({scene_id})/$value"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"📡 Downloading: {title}...")
    with requests.get(url, headers=headers, stream=True) as r:
        r.raise_for_status()
        with open(f"data/raw/{title}.zip", "wb") as f:
            for chunk in r.iter_content(chunk_size=1024*1024): # 1MB chunks
                f.write(chunk)
                print(".", end="", flush=True) # Progress dots
    print("\n✅ Download complete!")

if __name__ == "__main__":
    download_latest()