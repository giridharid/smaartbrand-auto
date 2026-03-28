"""
Smaartbrand Auto/Moto - Unified FastAPI Backend
Single codebase for Cars and Bikes Intelligence Platform

Deploy twice on Railway:
- auto.smaartbrand.com: VEHICLE_TYPE=car
- moto.smaartbrand.com: VEHICLE_TYPE=bike
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery
from google.oauth2 import service_account
import json
import os
import base64
import traceback
from pydantic import BaseModel
from typing import Optional, List

# ─────────────────────────────────────────
# VEHICLE TYPE FROM ENV VAR
# ─────────────────────────────────────────
VEHICLE_TYPE = os.environ.get("VEHICLE_TYPE", "car").lower()

# Validate
if VEHICLE_TYPE not in ["car", "bike"]:
    print(f"[WARNING] Invalid VEHICLE_TYPE '{VEHICLE_TYPE}', defaulting to 'car'")
    VEHICLE_TYPE = "car"

print(f"[CONFIG] Running in {VEHICLE_TYPE.upper()} mode")

app = FastAPI(title=f"Smaartbrand {'Auto' if VEHICLE_TYPE == 'car' else 'Moto'} API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────
PROJECT = "gen-lang-client-0143536012"
DATASET = "auto"

CAR_ASPECTS = ["Performance", "Comfort", "Safety", "Features", "Space", "Mileage", "Ownership", "Value", "Brand", "Style"]
BIKE_ASPECTS = ["Performance", "Handling", "Comfort", "Build", "Features", "Mileage", "Ownership", "Value", "Brand", "Style"]

ASPECT_ICONS = {
    "Performance": "🏎️",
    "Comfort": "🛋️",
    "Safety": "🛡️",
    "Features": "⚙️",
    "Space": "📦",
    "Mileage": "⛽",
    "Ownership": "🔧",
    "Value": "💰",
    "Brand": "🏷️",
    "Style": "✨",
    "Handling": "🎯",
    "Build": "🔩"
}

# Map non-standard aspects to standard ones
ASPECT_MAPPING = {
    # Direct matches (lowercase to standard)
    "performance": "Performance",
    "comfort": "Comfort",
    "safety": "Safety",
    "features": "Features",
    "space": "Space",
    "mileage": "Mileage",
    "ownership": "Ownership",
    "value": "Value",
    "brand": "Brand",
    "style": "Style",
    "handling": "Handling",
    "build": "Build",
    # Common variations
    "design": "Style",
    "looks": "Style",
    "aesthetics": "Style",
    "styling": "Style",
    "appearance": "Style",
    "price": "Value",
    "cost": "Value",
    "pricing": "Value",
    "money": "Value",
    "affordable": "Value",
    "maintenance": "Ownership",
    "service": "Ownership",
    "after-sales": "Ownership",
    "after sales": "Ownership",
    "aftersales": "Ownership",
    "reliability": "Build",
    "quality": "Build",
    "build quality": "Build",
    "durability": "Build",
    "engine": "Performance",
    "power": "Performance",
    "acceleration": "Performance",
    "speed": "Performance",
    "ride": "Comfort",
    "ride quality": "Comfort",
    "seating": "Comfort",
    "interior": "Comfort",
    "boot": "Space",
    "storage": "Space",
    "legroom": "Space",
    "headroom": "Space",
    "fuel": "Mileage",
    "fuel efficiency": "Mileage",
    "fuel economy": "Mileage",
    "economy": "Mileage",
    "technology": "Features",
    "infotainment": "Features",
    "tech": "Features",
    "airbags": "Safety",
    "brakes": "Safety",
    "abs": "Safety",
    "braking": "Safety",
    # Additional variations that might come from LLM
    "overall": None,  # Skip "Overall" aspect
    "availability": None,  # Skip availability
    "general": None,  # Skip general
}

# Standard aspects for validation
STANDARD_ASPECTS = {"Performance", "Comfort", "Safety", "Features", "Space", "Mileage", "Ownership", "Value", "Brand", "Style", "Handling", "Build"}

def normalize_aspect(aspect: str) -> str:
    """Map raw aspect to standard aspect name"""
    if not aspect:
        return None
    
    aspect_stripped = aspect.strip()
    
    # If already a standard aspect (case-insensitive match)
    for std in STANDARD_ASPECTS:
        if aspect_stripped.lower() == std.lower():
            return std
    
    # Try mapping
    aspect_lower = aspect_stripped.lower()
    mapped = ASPECT_MAPPING.get(aspect_lower, None)
    
    # If mapped to None explicitly, skip it
    if aspect_lower in ASPECT_MAPPING and mapped is None:
        return None
    
    return mapped

# Minimum mentions threshold
MIN_MENTIONS_THRESHOLD = 5

PERSONAS = ["value_seeker", "enthusiast", "family", "commuter", "first_buyer", "tech"]
INTENTS = ["considering", "bought", "owns", "rejected", "recommending", "warning"]

import numpy as np

def clean_dataframe(df):
    """Replace NaN and Infinity with 0 for JSON serialization"""
    return df.replace([np.inf, -np.inf], 0).fillna(0)

# ─────────────────────────────────────────
# CREDENTIALS & CLIENT
# ─────────────────────────────────────────
client = None

def init_client():
    global client
    if client is not None:
        return client
    
    gcp_creds = os.environ.get("GCP_CREDENTIALS_JSON", "")
    
    if not gcp_creds:
        print("[ERROR] GCP_CREDENTIALS_JSON not set")
        return None
    
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
        return client
    except Exception as e:
        print(f"[ERROR] Credential error: {e}")
        traceback.print_exc()
        return None

@app.on_event("startup")
async def startup():
    init_client()

def get_client():
    global client
    if client is None:
        init_client()
    return client

def get_vehicle_filter() -> str:
    """Return SQL filter based on VEHICLE_TYPE env var"""
    if VEHICLE_TYPE == "bike":
        return "product_id LIKE 'BIKE_%'"
    return "product_id LIKE 'CAR_%'"

def get_aspects() -> list:
    """Return aspect list based on VEHICLE_TYPE"""
    return BIKE_ASPECTS if VEHICLE_TYPE == "bike" else CAR_ASPECTS

# ─────────────────────────────────────────
# CONFIG ENDPOINT - Frontend fetches this on load
# ─────────────────────────────────────────
@app.get("/api/config")
async def get_config():
    """Return app configuration based on VEHICLE_TYPE env var"""
    return {
        "vehicle_type": VEHICLE_TYPE,
        "title": "Smaartbrand Moto" if VEHICLE_TYPE == "bike" else "Smaartbrand Auto",
        "subtitle": "Bikes Intelligence" if VEHICLE_TYPE == "bike" else "Auto Intelligence",
        "icon": "🏍️" if VEHICLE_TYPE == "bike" else "🚗",
        "aspects": get_aspects(),
        "aspect_icons": ASPECT_ICONS
    }

# ─────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────

@app.get("/")
async def root():
    try:
        with open("index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(content=f"<h1>Smaartbrand API</h1><p>Use /docs for API documentation</p>")

@app.get("/health")
async def health():
    c = get_client()
    return {
        "status": "healthy" if c else "degraded",
        "database": "connected" if c else "disconnected",
        "vehicle_type": VEHICLE_TYPE
    }

@app.get("/api/brands")
async def get_brands():
    c = get_client()
    if not c:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    vehicle_filter = get_vehicle_filter()
    
    query = f"""
    SELECT DISTINCT brand
    FROM `{PROJECT}.{DATASET}.aspects`
    WHERE {vehicle_filter} AND brand IS NOT NULL
    ORDER BY brand
    """
    
    try:
        result = c.query(query).to_dataframe()
        return result['brand'].tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/models")
async def get_models(brand: Optional[str] = None):
    c = get_client()
    if not c:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    vehicle_filter = get_vehicle_filter()
    where_clauses = [vehicle_filter, "model IS NOT NULL"]
    
    if brand:
        where_clauses.append(f"brand = '{brand.replace(chr(39), chr(39)+chr(39))}'")
    
    query = f"""
    SELECT DISTINCT model, brand
    FROM `{PROJECT}.{DATASET}.aspects`
    WHERE {' AND '.join(where_clauses)}
    ORDER BY model
    """
    
    try:
        result = c.query(query).to_dataframe()
        return clean_dataframe(result).to_dict(orient='records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/segments")
async def get_segments():
    c = get_client()
    if not c:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    vt = "bike" if VEHICLE_TYPE == "bike" else "car"
    
    query = f"""
    SELECT DISTINCT segment
    FROM `{PROJECT}.{DATASET}.product_master`
    WHERE vehicle_type = '{vt}' AND segment IS NOT NULL
    ORDER BY segment
    """
    
    try:
        result = c.query(query).to_dataframe()
        return result['segment'].tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/drivers")
async def get_drivers(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    persona: Optional[str] = None
):
    """Get share of voice and satisfaction by aspect"""
    c = get_client()
    if not c:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    if not brand and not model:
        raise HTTPException(status_code=400, detail="Either brand or model required")
    
    vehicle_filter = get_vehicle_filter()
    where_clauses = [vehicle_filter]
    
    if model:
        where_clauses.append(f"model = '{model.replace(chr(39), chr(39)+chr(39))}'")
    elif brand:
        where_clauses.append(f"brand = '{brand.replace(chr(39), chr(39)+chr(39))}'")
    
    if persona:
        where_clauses.append(f"persona = '{persona.replace(chr(39), chr(39)+chr(39))}'")
    
    # Get raw aspect data
    query = f"""
    SELECT 
        aspect,
        SUM(CASE WHEN sentiment = 1 THEN 1 ELSE 0 END) AS positive_count,
        SUM(CASE WHEN sentiment = -1 THEN 1 ELSE 0 END) AS negative_count,
        COUNT(*) AS total_mentions
    FROM `{PROJECT}.{DATASET}.aspects`
    WHERE {' AND '.join(where_clauses)}
    GROUP BY aspect
    """
    
    try:
        raw_result = c.query(query).to_dataframe()
        raw_result = clean_dataframe(raw_result)
        
        # Normalize aspects and aggregate
        raw_result['normalized_aspect'] = raw_result['aspect'].apply(normalize_aspect)
        
        # Filter out unmapped aspects
        mapped = raw_result[raw_result['normalized_aspect'].notna()].copy()
        
        if mapped.empty:
            return []
        
        # Aggregate by normalized aspect
        aggregated = mapped.groupby('normalized_aspect').agg({
            'positive_count': 'sum',
            'negative_count': 'sum',
            'total_mentions': 'sum'
        }).reset_index()
        aggregated.columns = ['aspect', 'positive_count', 'negative_count', 'total_mentions']
        
        # Filter out aspects with < MIN_MENTIONS_THRESHOLD mentions
        aggregated = aggregated[aggregated['total_mentions'] >= MIN_MENTIONS_THRESHOLD]
        
        if aggregated.empty:
            return []
        
        # Calculate metrics
        grand_total = aggregated['total_mentions'].sum()
        aggregated['share_of_voice'] = (aggregated['total_mentions'] * 100.0 / grand_total).round(0)
        aggregated['satisfaction'] = (aggregated['positive_count'] * 100.0 / aggregated['total_mentions'].replace(0, 1)).round(0)
        
        # Add icons and sort
        aggregated['icon'] = aggregated['aspect'].map(ASPECT_ICONS)
        aggregated = aggregated.sort_values('share_of_voice', ascending=False)
        
        return clean_dataframe(aggregated).to_dict(orient='records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/satisfaction")
async def get_satisfaction(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    persona: Optional[str] = None
):
    """Get satisfaction by aspect"""
    c = get_client()
    if not c:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    if not brand and not model:
        raise HTTPException(status_code=400, detail="Either brand or model required")
    
    vehicle_filter = get_vehicle_filter()
    where_clauses = [vehicle_filter]
    
    if model:
        where_clauses.append(f"model = '{model.replace(chr(39), chr(39)+chr(39))}'")
    elif brand:
        where_clauses.append(f"brand = '{brand.replace(chr(39), chr(39)+chr(39))}'")
    
    if persona:
        where_clauses.append(f"persona = '{persona.replace(chr(39), chr(39)+chr(39))}'")
    
    query = f"""
    SELECT 
        aspect,
        SUM(CASE WHEN sentiment = 1 THEN 1 ELSE 0 END) AS positive_count,
        SUM(CASE WHEN sentiment = -1 THEN 1 ELSE 0 END) AS negative_count,
        COUNT(*) AS total_mentions
    FROM `{PROJECT}.{DATASET}.aspects`
    WHERE {' AND '.join(where_clauses)}
    GROUP BY aspect
    """
    
    try:
        raw_result = c.query(query).to_dataframe()
        raw_result = clean_dataframe(raw_result)
        
        # Normalize aspects
        raw_result['normalized_aspect'] = raw_result['aspect'].apply(normalize_aspect)
        mapped = raw_result[raw_result['normalized_aspect'].notna()].copy()
        
        if mapped.empty:
            return []
        
        # Aggregate by normalized aspect
        aggregated = mapped.groupby('normalized_aspect').agg({
            'positive_count': 'sum',
            'negative_count': 'sum',
            'total_mentions': 'sum'
        }).reset_index()
        aggregated.columns = ['aspect', 'positive_count', 'negative_count', 'total_mentions']
        
        # Filter out aspects with < MIN_MENTIONS_THRESHOLD mentions
        aggregated = aggregated[aggregated['total_mentions'] >= MIN_MENTIONS_THRESHOLD]
        
        if aggregated.empty:
            return []
        
        # Calculate satisfaction
        aggregated['satisfaction'] = (aggregated['positive_count'] * 100.0 / aggregated['total_mentions'].replace(0, 1)).round(0)
        aggregated['icon'] = aggregated['aspect'].map(ASPECT_ICONS)
        aggregated = aggregated.sort_values('total_mentions', ascending=False)
        
        return clean_dataframe(aggregated).to_dict(orient='records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/demographics")
async def get_demographics(
    brand: Optional[str] = None,
    model: Optional[str] = None
):
    """Get persona and intent breakdown"""
    c = get_client()
    if not c:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    if not brand and not model:
        raise HTTPException(status_code=400, detail="Either brand or model required")
    
    vehicle_filter = get_vehicle_filter()
    where_clauses = [vehicle_filter]
    
    if model:
        where_clauses.append(f"model = '{model.replace(chr(39), chr(39)+chr(39))}'")
    elif brand:
        where_clauses.append(f"brand = '{brand.replace(chr(39), chr(39)+chr(39))}'")
    
    base_where = ' AND '.join(where_clauses)
    
    persona_query = f"""
    SELECT persona, COUNT(*) AS count
    FROM `{PROJECT}.{DATASET}.aspects`
    WHERE {base_where} AND persona IS NOT NULL AND persona != ''
    GROUP BY persona ORDER BY count DESC
    """
    
    intent_query = f"""
    SELECT intent, COUNT(*) AS count
    FROM `{PROJECT}.{DATASET}.aspects`
    WHERE {base_where} AND intent IS NOT NULL AND intent != ''
    GROUP BY intent ORDER BY count DESC
    """
    
    gender_query = f"""
    SELECT gender, COUNT(*) AS count
    FROM `{PROJECT}.{DATASET}.aspects`
    WHERE {base_where} AND gender IS NOT NULL AND gender != ''
    GROUP BY gender ORDER BY count DESC
    """
    
    try:
        return {
            "persona": clean_dataframe(c.query(persona_query).to_dataframe()).to_dict(orient='records'),
            "intent": clean_dataframe(c.query(intent_query).to_dataframe()).to_dict(orient='records'),
            "gender": clean_dataframe(c.query(gender_query).to_dataframe()).to_dict(orient='records')
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/comparison")
async def get_comparison(
    items: str,
    compare_by: str = "brand",
    persona: Optional[str] = None,
    gender: Optional[str] = None
):
    """
    Compare multiple brands or models - matching hotels structure exactly
    Returns: { item_name: { aspects: [...], overall: {...} } }
    """
    c = get_client()
    if not c:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    item_list = [i.strip() for i in items.split(",") if i.strip()]
    if len(item_list) < 2:
        raise HTTPException(status_code=400, detail="At least 2 items required")
    
    items_sql = "', '".join([i.replace("'", "''") for i in item_list])
    vehicle_filter = get_vehicle_filter()
    name_field = "model" if compare_by == "model" else "brand"
    
    extra_where = ""
    if persona:
        extra_where += f" AND persona = '{persona.replace(chr(39), chr(39)+chr(39))}'"
    if gender:
        extra_where += f" AND gender = '{gender.replace(chr(39), chr(39)+chr(39))}'"
    
    query = f"""
    SELECT 
        {name_field} AS item_name,
        aspect,
        SUM(CASE WHEN sentiment = 1 THEN 1 ELSE 0 END) AS positive_count,
        SUM(CASE WHEN sentiment = -1 THEN 1 ELSE 0 END) AS negative_count,
        COUNT(*) AS total_mentions
    FROM `{PROJECT}.{DATASET}.aspects`
    WHERE {vehicle_filter} AND {name_field} IN ('{items_sql}') {extra_where}
    GROUP BY {name_field}, aspect
    """
    
    try:
        raw_result = c.query(query).to_dataframe()
        raw_result = clean_dataframe(raw_result)
        
        # Normalize aspects
        raw_result['normalized_aspect'] = raw_result['aspect'].apply(normalize_aspect)
        mapped = raw_result[raw_result['normalized_aspect'].notna()].copy()
        
        comparison = {}
        for item in item_list:
            item_data = mapped[mapped['item_name'] == item]
            if not item_data.empty:
                # Aggregate by normalized aspect
                agg = item_data.groupby('normalized_aspect').agg({
                    'positive_count': 'sum',
                    'negative_count': 'sum',
                    'total_mentions': 'sum'
                }).reset_index()
                agg.columns = ['aspect', 'positive_count', 'negative_count', 'total_mentions']
                
                # Filter out aspects with < MIN_MENTIONS_THRESHOLD mentions
                agg = agg[agg['total_mentions'] >= MIN_MENTIONS_THRESHOLD]
                
                agg['satisfaction'] = (agg['positive_count'] * 100.0 / agg['total_mentions'].replace(0, 1)).round(0)
                agg['aspect_name'] = agg['aspect']
                
                total_pos = int(agg['positive_count'].sum())
                total_neg = int(agg['negative_count'].sum())
                total_mentions = int(agg['total_mentions'].sum())
                
                comparison[item] = {
                    "aspects": clean_dataframe(agg).to_dict(orient='records'),
                    "overall": {
                        "positive": total_pos,
                        "negative": total_neg,
                        "total_mentions": total_mentions,
                        "satisfaction": round(total_pos * 100 / max(total_mentions, 1))
                    }
                }
            else:
                comparison[item] = {
                    "aspects": [],
                    "overall": {"positive": 0, "negative": 0, "total_mentions": 0, "satisfaction": 0}
                }
        
        return comparison
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/features")
async def get_features(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = 20
):
    """Get top features sought"""
    c = get_client()
    if not c:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    vehicle_filter = get_vehicle_filter()
    where_clauses = [vehicle_filter, "features_sought IS NOT NULL", "features_sought != ''"]
    
    if model:
        where_clauses.append(f"model = '{model.replace(chr(39), chr(39)+chr(39))}'")
    elif brand:
        where_clauses.append(f"brand = '{brand.replace(chr(39), chr(39)+chr(39))}'")
    
    query = f"""
    SELECT features_sought AS feature, COUNT(*) AS count
    FROM `{PROJECT}.{DATASET}.rd_insights`
    WHERE {' AND '.join(where_clauses)}
    GROUP BY features_sought
    ORDER BY count DESC
    LIMIT {limit}
    """
    
    try:
        result = c.query(query).to_dataframe()
        return clean_dataframe(result).to_dict(orient='records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats():
    """Get overall dataset stats"""
    c = get_client()
    if not c:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    vehicle_filter = get_vehicle_filter()
    
    query = f"""
    SELECT 
        COUNT(DISTINCT brand) AS brands,
        COUNT(DISTINCT model) AS models,
        COUNT(*) AS total_aspects,
        ROUND(SUM(CASE WHEN sentiment = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS avg_satisfaction
    FROM `{PROJECT}.{DATASET}.aspects`
    WHERE {vehicle_filter}
    """
    
    review_query = f"""
    SELECT COUNT(*) AS total_reviews
    FROM `{PROJECT}.{DATASET}.reviews`
    WHERE {vehicle_filter}
    """
    
    try:
        stats_df = clean_dataframe(c.query(query).to_dataframe())
        stats = stats_df.iloc[0].to_dict()
        reviews_df = clean_dataframe(c.query(review_query).to_dataframe())
        reviews = reviews_df.iloc[0].to_dict()
        stats.update(reviews)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────
# AUTH ENDPOINT
# ─────────────────────────────────────────
class AuthRequest(BaseModel):
    key: str

@app.post("/api/auth")
async def authenticate(request: AuthRequest):
    """Validate admin key for full access"""
    admin_key = os.environ.get("SMAARTBRAND_ADMIN_KEY", "")
    
    if not admin_key:
        return {"success": False, "message": "No admin key configured"}
    
    if request.key == admin_key:
        return {"success": True, "message": "Full access granted"}
    else:
        return {"success": False, "message": "Invalid key"}
