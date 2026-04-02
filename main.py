"""
Test version - BigQuery connection test
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery
from google.oauth2 import service_account
import os
import base64
import json
import traceback

app = FastAPI(title="Smaartbrand BQ Test")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Globals
client = None
PROJECT = "gen-lang-client-0143536012"
DATASET = "auto"

def init_client():
    global client
    gcp_creds = os.environ.get("GCP_CREDENTIALS_JSON", "")
    
    if not gcp_creds:
        print("[ERROR] GCP_CREDENTIALS_JSON not set")
        return
    
    gcp_creds = gcp_creds.strip().strip('"').strip("'")
    
    try:
        if gcp_creds.startswith("{"):
            creds_dict = json.loads(gcp_creds)
        else:
            padding = 4 - len(gcp_creds) % 4
            if padding != 4:
                gcp_creds += "=" * padding
            decoded = base64.b64decode(gcp_creds).decode('utf-8')
            creds_dict = json.loads(decoded)
        
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        client = bigquery.Client(credentials=credentials, project=credentials.project_id)
        print(f"[SUCCESS] BigQuery client initialized for project: {credentials.project_id}")
    except Exception as e:
        print(f"[ERROR] Credential error: {e}")
        traceback.print_exc()

@app.on_event("startup")
async def startup():
    print("[STARTUP] Initializing BigQuery...")
    init_client()
    print("[STARTUP] Done")

@app.get("/")
async def root():
    return HTMLResponse(content="<h1>Smaartbrand BQ Test</h1><p>Check /health and /test-query</p>")

@app.get("/health")
async def health():
    return {"status": "healthy", "bq_connected": client is not None}

@app.get("/test-query")
async def test_query():
    if not client:
        return {"error": "BigQuery not connected"}
    
    try:
        query = f"SELECT COUNT(*) as cnt FROM `{PROJECT}.{DATASET}.aspects` WHERE product_id LIKE 'CAR_%' LIMIT 1"
        result = client.query(query).to_dataframe()
        count = int(result['cnt'].iloc[0])
        return {"success": True, "aspects_count": count}
    except Exception as e:
        return {"error": str(e)}

@app.get("/test-load")
async def test_load():
    """Test loading aspects table"""
    if not client:
        return {"error": "BigQuery not connected"}
    
    try:
        import time
        start = time.time()
        query = f"SELECT * FROM `{PROJECT}.{DATASET}.aspects` WHERE product_id LIKE 'CAR_%'"
        df = client.query(query).to_dataframe()
        elapsed = time.time() - start
        
        brands = sorted(df['brand'].dropna().unique().tolist())
        
        return {
            "success": True, 
            "rows": len(df), 
            "load_time": f"{elapsed:.2f}s",
            "brand_count": len(brands),
            "brands": brands
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

@app.get("/api/brands")
async def get_brands():
    return ["Maruti", "Tata", "Hyundai", "Honda", "Kia"]

@app.get("/api/config")
async def get_config():
    return {
        "vehicle_type": "car",
        "title": "Smaartbrand Auto",
        "subtitle": "Auto Intelligence",
        "icon": "🚗",
        "aspects": ["Performance", "Comfort", "Safety"],
        "aspect_icons": {},
        "bq_connected": client is not None
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
