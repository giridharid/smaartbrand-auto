"""
Smaartbrand Auto/Moto - Unified FastAPI Backend (CACHED VERSION)
Single codebase for Cars and Bikes Intelligence Platform

PERFORMANCE OPTIMIZATION:
- Loads all data into memory at startup (parallel BigQuery calls)
- All endpoints query in-memory DataFrames instead of BigQuery
- ~50ms response times vs 2-4 seconds with live BQ

Deploy twice on Railway:
- auto.smaartbrand.com: VEHICLE_TYPE=car
- moto.smaartbrand.com: VEHICLE_TYPE=bike
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery
from google.oauth2 import service_account
import json
import os
import base64
import traceback
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
import numpy as np
import asyncio
from concurrent.futures import ThreadPoolExecutor

# ─────────────────────────────────────────
# VEHICLE TYPE FROM ENV VAR
# ─────────────────────────────────────────
VEHICLE_TYPE = os.environ.get("VEHICLE_TYPE", "car").lower()

if VEHICLE_TYPE not in ["car", "bike"]:
    print(f"[WARNING] Invalid VEHICLE_TYPE '{VEHICLE_TYPE}', defaulting to 'car'")
    VEHICLE_TYPE = "car"

print(f"[CONFIG] Running in {VEHICLE_TYPE.upper()} mode")

app = FastAPI(title=f"Smaartbrand {'Auto' if VEHICLE_TYPE == 'car' else 'Moto'} API (Cached)")

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

ASPECT_MAPPING = {
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
    "overall": None,
    "availability": None,
    "general": None,
}

STANDARD_ASPECTS = {"Performance", "Comfort", "Safety", "Features", "Space", "Mileage", "Ownership", "Value", "Brand", "Style", "Handling", "Build"}

def normalize_aspect(aspect: str) -> str:
    if not aspect:
        return None
    aspect_stripped = aspect.strip()
    for std in STANDARD_ASPECTS:
        if aspect_stripped.lower() == std.lower():
            return std
    aspect_lower = aspect_stripped.lower()
    mapped = ASPECT_MAPPING.get(aspect_lower, None)
    if aspect_lower in ASPECT_MAPPING and mapped is None:
        return None
    return mapped

MIN_MENTIONS_THRESHOLD = 5

PERSONAS = ["value_seeker", "enthusiast", "family", "commuter", "first_buyer", "tech"]
INTENTS = ["considering", "bought", "owns", "rejected", "recommending", "warning"]

def clean_dataframe(df):
    return df.replace([np.inf, -np.inf], 0).fillna(0)

# ─────────────────────────────────────────
# IN-MEMORY DATA CACHE
# ─────────────────────────────────────────
class DataCache:
    """In-memory cache for all BigQuery data - loads once at startup"""
    
    def __init__(self):
        self.aspects: pd.DataFrame = None
        self.reviews: pd.DataFrame = None
        self.rd_insights: pd.DataFrame = None
        self.product_master: pd.DataFrame = None
        self.loaded: bool = False
        self.load_time: float = 0
        self.row_counts: dict = {}
    
    def is_ready(self) -> bool:
        return self.loaded and self.aspects is not None

_cache = DataCache()

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

def get_client():
    global client
    if client is None:
        init_client()
    return client

def get_vehicle_filter() -> str:
    if VEHICLE_TYPE == "bike":
        return "product_id LIKE 'BIKE_%'"
    return "product_id LIKE 'CAR_%'"

def get_aspects() -> list:
    return BIKE_ASPECTS if VEHICLE_TYPE == "bike" else CAR_ASPECTS

# ─────────────────────────────────────────
# PARALLEL DATA LOADING AT STARTUP
# ─────────────────────────────────────────
def _load_table(table_name: str, query: str) -> tuple:
    """Load a single table - runs in thread pool"""
    c = get_client()
    if not c:
        return table_name, None
    try:
        print(f"[CACHE] Loading {table_name}...")
        df = c.query(query).to_dataframe()
        print(f"[CACHE] Loaded {table_name}: {len(df)} rows")
        return table_name, df
    except Exception as e:
        print(f"[CACHE ERROR] Failed to load {table_name}: {e}")
        return table_name, None

def load_all_data_parallel():
    """Load all tables in parallel using ThreadPoolExecutor"""
    import time
    start = time.time()
    
    vehicle_filter = get_vehicle_filter()
    vt = "bike" if VEHICLE_TYPE == "bike" else "car"
    
    queries = {
        "aspects": f"SELECT * FROM `{PROJECT}.{DATASET}.aspects` WHERE {vehicle_filter}",
        "reviews": f"SELECT * FROM `{PROJECT}.{DATASET}.reviews` WHERE {vehicle_filter}",
        "rd_insights": f"SELECT * FROM `{PROJECT}.{DATASET}.rd_insights` WHERE {vehicle_filter}",
        "product_master": f"SELECT * FROM `{PROJECT}.{DATASET}.product_master` WHERE vehicle_type = '{vt}'"
    }
    
    print(f"[CACHE] Starting parallel load of {len(queries)} tables...")
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(_load_table, name, query)
            for name, query in queries.items()
        ]
        
        for future in futures:
            table_name, df = future.result()
            if df is not None:
                setattr(_cache, table_name, df)
                _cache.row_counts[table_name] = len(df)
    
    _cache.loaded = True
    _cache.load_time = time.time() - start
    
    print(f"[CACHE] ✅ All data loaded in {_cache.load_time:.2f}s")
    print(f"[CACHE] Row counts: {_cache.row_counts}")

@app.on_event("startup")
async def startup():
    init_client()
    load_all_data_parallel()

# ─────────────────────────────────────────
# CONFIG ENDPOINT
# ─────────────────────────────────────────
@app.get("/api/config")
async def get_config():
    return {
        "vehicle_type": VEHICLE_TYPE,
        "title": "Smaartbrand Moto" if VEHICLE_TYPE == "bike" else "Smaartbrand Auto",
        "subtitle": "Bikes Intelligence" if VEHICLE_TYPE == "bike" else "Auto Intelligence",
        "icon": "🏍️" if VEHICLE_TYPE == "bike" else "🚗",
        "aspects": get_aspects(),
        "aspect_icons": ASPECT_ICONS,
        "cached": True,
        "cache_load_time": f"{_cache.load_time:.2f}s",
        "row_counts": _cache.row_counts
    }

# ─────────────────────────────────────────
# API ENDPOINTS (CACHED)
# ─────────────────────────────────────────

@app.get("/")
async def root():
    try:
        with open("index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(content=f"<h1>Smaartbrand API (Cached)</h1><p>Use /docs for API documentation</p>")

@app.get("/acquink_logo.png")
async def logo():
    return FileResponse("acquink_logo.png", media_type="image/png")

@app.get("/health")
async def health():
    return {
        "status": "healthy" if _cache.is_ready() else "loading",
        "database": "cached" if _cache.is_ready() else "loading",
        "vehicle_type": VEHICLE_TYPE,
        "cache_loaded": _cache.loaded,
        "row_counts": _cache.row_counts
    }

@app.get("/api/brands")
async def get_brands():
    if not _cache.is_ready():
        raise HTTPException(status_code=503, detail="Cache still loading")
    
    brands = _cache.aspects['brand'].dropna().unique().tolist()
    return sorted(brands)

@app.get("/api/models")
async def get_models(brand: Optional[str] = None):
    if not _cache.is_ready():
        raise HTTPException(status_code=503, detail="Cache still loading")
    
    df = _cache.aspects
    if brand:
        df = df[df['brand'] == brand]
    
    result = df[['model', 'brand']].drop_duplicates().dropna()
    return clean_dataframe(result).to_dict(orient='records')

@app.get("/api/segments")
async def get_segments():
    if not _cache.is_ready():
        raise HTTPException(status_code=503, detail="Cache still loading")
    
    segments = _cache.product_master['segment'].dropna().unique().tolist()
    return sorted(segments)

@app.get("/api/drivers")
async def get_drivers(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    persona: Optional[str] = None
):
    """Get share of voice and satisfaction by aspect - FROM CACHE"""
    if not _cache.is_ready():
        raise HTTPException(status_code=503, detail="Cache still loading")
    
    if not brand and not model:
        raise HTTPException(status_code=400, detail="Either brand or model required")
    
    df = _cache.aspects.copy()
    
    # Filter
    if model:
        df = df[df['model'] == model]
    elif brand:
        df = df[df['brand'] == brand]
    
    if persona:
        df = df[df['persona'] == persona]
    
    if df.empty:
        return []
    
    # Create count columns first (avoid lambda in groupby)
    df['positive_count'] = (df['sentiment'] == 1).astype(int)
    df['negative_count'] = (df['sentiment'] == -1).astype(int)
    
    # Aggregate by aspect
    agg = df.groupby('aspect').agg({
        'positive_count': 'sum',
        'negative_count': 'sum',
        'sentiment': 'count'  # total_mentions
    }).reset_index()
    agg.columns = ['aspect', 'positive_count', 'negative_count', 'total_mentions']
    
    # Normalize aspects
    agg['normalized_aspect'] = agg['aspect'].apply(normalize_aspect)
    agg = agg[agg['normalized_aspect'].notna()]
    
    if agg.empty:
        return []
    
    # Re-aggregate by normalized aspect
    agg = agg.groupby('normalized_aspect').agg({
        'positive_count': 'sum',
        'negative_count': 'sum',
        'total_mentions': 'sum'
    }).reset_index()
    agg.columns = ['aspect', 'positive_count', 'negative_count', 'total_mentions']
    
    # Filter minimum mentions
    agg = agg[agg['total_mentions'] >= MIN_MENTIONS_THRESHOLD]
    
    if agg.empty:
        return []
    
    # Calculate metrics
    grand_total = agg['total_mentions'].sum()
    agg['share_of_voice'] = (agg['total_mentions'] * 100.0 / grand_total).round(0)
    
    sentiment_total = agg['positive_count'] + agg['negative_count']
    agg['satisfaction'] = (agg['positive_count'] * 100.0 / sentiment_total.replace(0, 1)).round(0)
    
    agg['icon'] = agg['aspect'].map(ASPECT_ICONS)
    agg = agg.sort_values('share_of_voice', ascending=False)
    
    return clean_dataframe(agg).to_dict(orient='records')

@app.get("/api/satisfaction")
async def get_satisfaction(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    persona: Optional[str] = None
):
    """Get satisfaction by aspect - FROM CACHE"""
    if not _cache.is_ready():
        raise HTTPException(status_code=503, detail="Cache still loading")
    
    if not brand and not model:
        raise HTTPException(status_code=400, detail="Either brand or model required")
    
    df = _cache.aspects.copy()
    
    if model:
        df = df[df['model'] == model]
    elif brand:
        df = df[df['brand'] == brand]
    
    if persona:
        df = df[df['persona'] == persona]
    
    if df.empty:
        return []
    
    # Create count columns first (avoid lambda in groupby)
    df['positive_count'] = (df['sentiment'] == 1).astype(int)
    df['negative_count'] = (df['sentiment'] == -1).astype(int)
    
    # Aggregate
    agg = df.groupby('aspect').agg({
        'positive_count': 'sum',
        'negative_count': 'sum',
        'sentiment': 'count'  # total_mentions
    }).reset_index()
    agg.columns = ['aspect', 'positive_count', 'negative_count', 'total_mentions']
    
    agg['normalized_aspect'] = agg['aspect'].apply(normalize_aspect)
    agg = agg[agg['normalized_aspect'].notna()]
    
    if agg.empty:
        return []
    
    agg = agg.groupby('normalized_aspect').agg({
        'positive_count': 'sum',
        'negative_count': 'sum',
        'total_mentions': 'sum'
    }).reset_index()
    agg.columns = ['aspect', 'positive_count', 'negative_count', 'total_mentions']
    
    agg = agg[agg['total_mentions'] >= MIN_MENTIONS_THRESHOLD]
    
    if agg.empty:
        return []
    
    sentiment_total = agg['positive_count'] + agg['negative_count']
    agg['satisfaction'] = (agg['positive_count'] * 100.0 / sentiment_total.replace(0, 1)).round(0)
    agg['icon'] = agg['aspect'].map(ASPECT_ICONS)
    agg = agg.sort_values('total_mentions', ascending=False)
    
    return clean_dataframe(agg).to_dict(orient='records')

@app.get("/api/demographics")
async def get_demographics(
    brand: Optional[str] = None,
    model: Optional[str] = None
):
    """Get persona and intent breakdown - FROM CACHE"""
    if not _cache.is_ready():
        raise HTTPException(status_code=503, detail="Cache still loading")
    
    if not brand and not model:
        raise HTTPException(status_code=400, detail="Either brand or model required")
    
    df = _cache.aspects.copy()
    
    if model:
        df = df[df['model'] == model]
    elif brand:
        df = df[df['brand'] == brand]
    
    # Persona breakdown
    persona_df = df[df['persona'].notna() & (df['persona'] != '')]
    persona_counts = persona_df.groupby('persona').size().reset_index(name='count')
    persona_counts = persona_counts.sort_values('count', ascending=False)
    
    total = persona_counts['count'].sum()
    persona_counts['percentage'] = (persona_counts['count'] * 100.0 / total).round(1) if total > 0 else 0
    
    # Gender breakdown
    gender_df = df[df['gender'].notna() & (df['gender'] != '')]
    gender_counts = gender_df.groupby('gender').size().reset_index(name='count')
    gender_counts = gender_counts.sort_values('count', ascending=False)
    
    return {
        "persona": clean_dataframe(persona_counts).to_dict(orient='records'),
        "gender": clean_dataframe(gender_counts).to_dict(orient='records')
    }

@app.get("/api/compare")
async def compare_items(
    items: str,
    compare_by: str = "brand",
    persona: Optional[str] = None,
    gender: Optional[str] = None
):
    """Compare brands or models - FROM CACHE"""
    if not _cache.is_ready():
        raise HTTPException(status_code=503, detail="Cache still loading")
    
    item_list = [i.strip() for i in items.split(",") if i.strip()]
    if len(item_list) < 2:
        raise HTTPException(status_code=400, detail="At least 2 items required")
    
    df = _cache.aspects.copy()
    name_field = "model" if compare_by == "model" else "brand"
    
    # Filter to only the items we want
    df = df[df[name_field].isin(item_list)]
    
    if persona:
        df = df[df['persona'] == persona]
    if gender:
        df = df[df['gender'] == gender]
    
    if df.empty:
        return {item: {"aspects": [], "overall": {"positive": 0, "negative": 0, "total_mentions": 0, "satisfaction": 0}} for item in item_list}
    
    # First aggregate by item + aspect (like the SQL GROUP BY)
    df['positive_count'] = (df['sentiment'] == 1).astype(int)
    df['negative_count'] = (df['sentiment'] == -1).astype(int)
    
    raw_agg = df.groupby([name_field, 'aspect']).agg({
        'positive_count': 'sum',
        'negative_count': 'sum',
        'sentiment': 'count'  # total_mentions
    }).reset_index()
    raw_agg.columns = [name_field, 'aspect', 'positive_count', 'negative_count', 'total_mentions']
    
    # Normalize aspects
    raw_agg['normalized_aspect'] = raw_agg['aspect'].apply(normalize_aspect)
    mapped = raw_agg[raw_agg['normalized_aspect'].notna()].copy()
    
    comparison = {}
    for item in item_list:
        item_data = mapped[mapped[name_field] == item]
        
        if item_data.empty:
            comparison[item] = {
                "aspects": [],
                "overall": {"positive": 0, "negative": 0, "total_mentions": 0, "satisfaction": 0}
            }
            continue
        
        # Re-aggregate by normalized aspect
        agg = item_data.groupby('normalized_aspect').agg({
            'positive_count': 'sum',
            'negative_count': 'sum',
            'total_mentions': 'sum'
        }).reset_index()
        agg.columns = ['aspect', 'positive_count', 'negative_count', 'total_mentions']
        
        # Filter minimum mentions
        agg = agg[agg['total_mentions'] >= MIN_MENTIONS_THRESHOLD]
        
        if agg.empty:
            comparison[item] = {
                "aspects": [],
                "overall": {"positive": 0, "negative": 0, "total_mentions": 0, "satisfaction": 0}
            }
            continue
        
        # Calculate satisfaction
        sentiment_total = agg['positive_count'] + agg['negative_count']
        agg['satisfaction'] = (agg['positive_count'] * 100.0 / sentiment_total.replace(0, 1)).round(0)
        agg['aspect_name'] = agg['aspect']
        
        total_pos = int(agg['positive_count'].sum())
        total_neg = int(agg['negative_count'].sum())
        total_mentions = int(agg['total_mentions'].sum())
        overall_satisfaction = round(total_pos * 100 / max(total_pos + total_neg, 1))
        
        comparison[item] = {
            "aspects": clean_dataframe(agg).to_dict(orient='records'),
            "overall": {
                "positive": total_pos,
                "negative": total_neg,
                "total_mentions": total_mentions,
                "satisfaction": overall_satisfaction
            }
        }
    
    return comparison

@app.get("/api/features")
async def get_features(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = 20
):
    """Get top features sought - FROM CACHE"""
    if not _cache.is_ready():
        raise HTTPException(status_code=503, detail="Cache still loading")
    
    df = _cache.rd_insights.copy()
    df = df[df['features_sought'].notna() & (df['features_sought'] != '')]
    
    if model:
        df = df[df['model'] == model]
    elif brand:
        df = df[df['brand'] == brand]
    
    if df.empty:
        return []
    
    counts = df.groupby('features_sought').size().reset_index(name='count')
    counts = counts.sort_values('count', ascending=False).head(limit)
    counts.columns = ['feature', 'count']
    
    return clean_dataframe(counts).to_dict(orient='records')

@app.get("/api/stats")
async def get_stats():
    """Get overall dataset stats - FROM CACHE"""
    if not _cache.is_ready():
        raise HTTPException(status_code=503, detail="Cache still loading")
    
    df = _cache.aspects
    
    brands = df['brand'].nunique()
    models = df['model'].nunique()
    total_aspects = len(df)
    
    positive = (df['sentiment'] == 1).sum()
    total = len(df)
    avg_satisfaction = round(positive * 100.0 / total, 1) if total > 0 else 0
    
    total_reviews = len(_cache.reviews) if _cache.reviews is not None else 0
    
    return {
        "brands": int(brands),
        "models": int(models),
        "total_aspects": int(total_aspects),
        "avg_satisfaction": float(avg_satisfaction),
        "total_reviews": int(total_reviews)
    }

# ─────────────────────────────────────────
# SAMPLE REVIEWS ENDPOINT
# ─────────────────────────────────────────
@app.get("/api/sample-reviews")
async def get_sample_reviews(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    aspect: str = None,
    sentiment: str = "all",
    limit: int = 5
):
    """Get sample review comments - FROM CACHE"""
    if not _cache.is_ready():
        raise HTTPException(status_code=503, detail="Cache still loading")
    
    if not aspect:
        raise HTTPException(status_code=400, detail="Aspect is required")
    
    if not brand and not model:
        raise HTTPException(status_code=400, detail="Either brand or model required")
    
    df = _cache.reviews.copy()
    
    if model:
        df = df[df['model'] == model]
    elif brand:
        df = df[df['brand'] == brand]
    
    if sentiment == "positive":
        df = df[df['masi_overall'].astype(str).isin(['1', '1.0'])]
    elif sentiment == "negative":
        df = df[df['masi_overall'].astype(str).isin(['-1', '-1.0'])]
    
    # Filter by aspect keywords
    aspect_keywords = {
        "Performance": ["engine", "power", "speed", "acceleration", "performance", "turbo", "torque"],
        "Comfort": ["comfort", "ride", "seat", "interior", "cabin", "suspension", "noise"],
        "Safety": ["safety", "airbag", "brake", "crash", "ncap", "safe"],
        "Features": ["feature", "tech", "infotainment", "screen", "sunroof", "camera"],
        "Space": ["space", "boot", "legroom", "headroom", "storage"],
        "Mileage": ["mileage", "fuel", "economy", "kmpl", "efficiency"],
        "Ownership": ["service", "maintenance", "dealer", "showroom", "spare", "ownership"],
        "Value": ["value", "price", "money", "worth", "expensive", "cheap"],
        "Brand": ["brand", "company", "trust", "reputation", "reliable"],
        "Style": ["design", "look", "style", "aesthetic", "beautiful"],
        "Handling": ["handling", "steering", "corner", "grip", "balance"],
        "Build": ["build", "quality", "fit", "finish", "solid", "sturdy"]
    }
    
    keywords = aspect_keywords.get(aspect, [aspect.lower()])
    
    # Filter where comment_body contains any keyword
    if 'comment_body' in df.columns:
        mask = df['comment_body'].str.lower().str.contains('|'.join(keywords), na=False)
        df = df[mask]
        
        # Additional filters
        df = df[df['comment_body'].notna()]
        df = df[df['comment_body'].str.len() > 30]
        df = df[df['comment_body'].str.len() < 1500]
    
    df = df.head(min(limit, 10))
    
    reviews = []
    for _, row in df.iterrows():
        masi_val = str(row.get('masi_overall', ''))
        if masi_val in ['1', '1.0']:
            sent = "positive"
        elif masi_val in ['-1', '-1.0']:
            sent = "negative"
        else:
            sent = "neutral"
        reviews.append({
            "text": row.get('comment_body', ''),
            "sentiment": sent,
            "brand": row.get('brand', ''),
            "model": row.get('model', ''),
            "subreddit": row.get('subreddit', ''),
            "date": str(row.get('created_date', ''))[:10]
        })
    
    return {
        "reviews": reviews,
        "aspect": aspect,
        "count": len(reviews),
        "query_brand": brand,
        "query_model": model
    }

# ─────────────────────────────────────────
# R&D INSIGHTS ENDPOINT
# ─────────────────────────────────────────
@app.get("/api/rd-insights")
async def get_rd_insights(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = 50
):
    """Get R&D insights - FROM CACHE"""
    if not _cache.is_ready():
        raise HTTPException(status_code=503, detail="Cache still loading")
    
    if not brand and not model:
        raise HTTPException(status_code=400, detail="Either brand or model required")
    
    df = _cache.rd_insights.copy()
    df = df[df['features_sought'].notna() & (df['features_sought'] != '')]
    
    if model:
        df = df[df['model'] == model]
    elif brand:
        df = df[df['brand'] == brand]
    
    if df.empty:
        return {"insights": [], "total": 0}
    
    # Aggregate
    agg = df.groupby('features_sought').agg({
        'model': 'nunique'
    }).reset_index()
    agg.columns = ['features_sought', 'models_affected']
    
    counts = df.groupby('features_sought').size().reset_index(name='mention_count')
    agg = agg.merge(counts, on='features_sought')
    agg = agg.sort_values('mention_count', ascending=False).head(limit)
    
    # Categorize
    insights = []
    for _, row in agg.iterrows():
        feature = str(row['features_sought']).strip()
        if not feature or feature == 'nan':
            continue
        
        category = "feature_request"
        feature_lower = feature.lower()
        
        pain_keywords = ['problem', 'issue', 'bad', 'poor', 'worst', 'fail', 'broke', 'broken', 
                        'expensive', 'costly', 'noise', 'noisy', 'uncomfortable', 'hard', 'difficult',
                        'lack', 'lacking', 'weak', 'slow', 'heavy', 'small', 'tight', 'cramped']
        
        improvement_keywords = ['need', 'want', 'should', 'missing', 'add', 'include', 'improve',
                               'better', 'wish', 'hope', 'would be nice', 'could use']
        
        if any(w in feature_lower for w in pain_keywords):
            category = "pain_point"
        elif any(w in feature_lower for w in improvement_keywords):
            category = "improvement"
        elif any(w in feature_lower for w in ['vs', 'better than', 'compared', 'competitor']):
            category = "competitive"
        
        insights.append({
            "feature": feature,
            "mentions": int(row['mention_count']),
            "models_affected": int(row['models_affected']),
            "category": category
        })
    
    categorized = {
        "feature_requests": [i for i in insights if i['category'] == 'feature_request'][:15],
        "pain_points": [i for i in insights if i['category'] == 'pain_point'][:10],
        "improvements": [i for i in insights if i['category'] == 'improvement'][:10],
        "competitive": [i for i in insights if i['category'] == 'competitive'][:10]
    }
    
    return {
        "insights": insights[:50],
        "categorized": categorized,
        "total": len(insights)
    }

# ─────────────────────────────────────────
# AUTH ENDPOINT
# ─────────────────────────────────────────
class AuthRequest(BaseModel):
    key: str

@app.post("/api/auth")
async def authenticate(request: AuthRequest):
    admin_key = os.environ.get("SMAARTBRAND_ADMIN_KEY", "")
    
    if not admin_key:
        return {"success": False, "message": "No admin key configured"}
    
    if request.key == admin_key:
        return {"success": True, "message": "Full access granted"}
    else:
        return {"success": False, "message": "Invalid key"}

# ─────────────────────────────────────────
# CHAT API - Data Agent Integration (CACHED)
# ─────────────────────────────────────────
import re
from fastapi import Request
import uuid

AGENT_ID = "agent_2ec1baf1-c0b3-47cb-acff-72bc0d34c930"
LOCATION = "global"
PRODUCT_PREFIX = "CAR_" if VEHICLE_TYPE == "car" else "BIKE_"

class ChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None

def detect_intent(message: str) -> dict:
    """Parse user message to detect intent, brand, aspects, etc."""
    message_lower = message.lower()
    
    intent = {
        "brand": None,
        "model": None,
        "compare": False,
        "aspects": [],
        "demographic": None,
        "analysis_type": "general"
    }
    
    car_brands = ["maruti", "tata", "hyundai", "mahindra", "kia", "honda", "toyota", "mg", "skoda", "volkswagen", "jeep", "citroen", "renault", "nissan", "ford"]
    bike_brands = ["royal enfield", "honda", "hero", "bajaj", "tvs", "yamaha", "ktm", "suzuki", "kawasaki", "bmw", "harley", "triumph", "jawa", "ather", "ola"]
    
    brands = car_brands if VEHICLE_TYPE == "car" else bike_brands
    for brand in brands:
        if brand in message_lower:
            intent["brand"] = brand.title()
            break
    
    if any(word in message_lower for word in ["compare", "vs", "versus", "against", "better", "difference"]):
        intent["compare"] = True
    
    personas = {
        "enthusiast": "enthusiast",
        "value seeker": "value_seeker",
        "budget": "value_seeker",
        "family": "family",
        "commuter": "commuter",
        "first buyer": "first_buyer",
        "tech": "tech"
    }
    for key, value in personas.items():
        if key in message_lower:
            intent["demographic"] = {"persona": value}
            break
    
    if any(word in message_lower for word in ["women", "female", "woman"]):
        intent["demographic"] = intent["demographic"] or {}
        intent["demographic"]["gender"] = "F"
    elif any(word in message_lower for word in ["men", "male", "man"]):
        intent["demographic"] = intent["demographic"] or {}
        intent["demographic"]["gender"] = "M"
    
    analysis_keywords = {
        "driver": ["driver", "what drives", "why do"],
        "swot": ["strength", "weakness", "swot"],
        "improvements": ["improve", "fix", "pain point", "problem", "issue"],
        "features": ["feature", "want", "wish", "need", "request"],
        "faq": ["faq", "questions", "frequently asked"],
        "comparison": ["compare", "vs", "versus"]
    }
    
    for analysis_type, keywords in analysis_keywords.items():
        if any(kw in message_lower for kw in keywords):
            intent["analysis_type"] = analysis_type
            break
    
    aspects = ["performance", "comfort", "safety", "features", "space", "mileage", "ownership", "value", "brand", "style", "handling", "build"]
    for aspect in aspects:
        if aspect in message_lower:
            intent["aspects"].append(aspect.title())
    
    return intent

def gather_context_data_cached(intent: dict) -> dict:
    """Get relevant data from cache instead of BigQuery"""
    if not _cache.is_ready():
        return {}
    
    data = {}
    brand = intent.get("brand")
    
    try:
        df = _cache.aspects.copy()
        
        # Brand satisfaction
        if brand:
            brand_df = df[df['brand'] == brand].copy()
            
            # Create count columns (avoid lambda)
            brand_df['positive_count'] = (brand_df['sentiment'] == 1).astype(int)
            brand_df['negative_count'] = (brand_df['sentiment'] == -1).astype(int)
            
            agg = brand_df.groupby('aspect').agg({
                'positive_count': 'sum',
                'negative_count': 'sum',
                'sentiment': 'count'
            }).reset_index()
            agg.columns = ['aspect', 'positive_count', 'negative_count', 'total']
            
            agg['satisfaction'] = (agg['positive_count'] * 100.0 / 
                (agg['positive_count'] + agg['negative_count']).replace(0, 1)).round(1)
            
            data["brand_satisfaction"] = [
                {
                    "brand": brand,
                    "aspect": row['aspect'],
                    "positive": int(row['positive_count']),
                    "negative": int(row['negative_count']),
                    "satisfaction": float(row['satisfaction'])
                }
                for _, row in agg.iterrows()
            ]
        
        # Demographics
        demo_df = df.copy()
        if brand:
            demo_df = demo_df[demo_df['brand'] == brand]
        
        demo_df = demo_df[demo_df['persona'].notna() & (demo_df['persona'] != '')]
        demo_agg = demo_df.groupby(['persona', 'gender']).size().reset_index(name='count')
        demo_agg = demo_agg.sort_values('count', ascending=False)
        
        data["demographics"] = [
            {"persona": row['persona'], "gender": row['gender'], "count": int(row['count'])}
            for _, row in demo_agg.iterrows()
        ]
        
        # Feature requests
        if intent.get("analysis_type") in ["features", "improvements"]:
            rd_df = _cache.rd_insights.copy()
            rd_df = rd_df[rd_df['features_sought'].notna() & (rd_df['features_sought'] != '')]
            
            if brand:
                rd_df = rd_df[rd_df['brand'] == brand]
            
            feat_agg = rd_df.groupby('features_sought').size().reset_index(name='mentions')
            feat_agg = feat_agg.sort_values('mentions', ascending=False).head(15)
            
            data["feature_requests"] = [
                {"feature": row['features_sought'], "mentions": int(row['mentions'])}
                for _, row in feat_agg.iterrows()
            ]
        
        # Brand comparison
        if intent.get("compare") or not brand:
            comp_df = df.copy()
            comp_df['positive'] = (comp_df['sentiment'] == 1).astype(int)
            comp_df['negative'] = (comp_df['sentiment'] == -1).astype(int)
            
            comp_agg = comp_df.groupby('brand').agg({
                'positive': 'sum',
                'negative': 'sum'
            }).reset_index()
            comp_agg['satisfaction'] = (comp_agg['positive'] * 100.0 / 
                (comp_agg['positive'] + comp_agg['negative']).replace(0, 1)).round(1)
            comp_agg['total'] = comp_agg['positive'] + comp_agg['negative']
            comp_agg = comp_agg.sort_values('total', ascending=False).head(10)
            
            data["brand_comparison"] = [
                {"brand": row['brand'], "positive": int(row['positive']), "negative": int(row['negative']), "satisfaction": float(row['satisfaction'])}
                for _, row in comp_agg.iterrows()
            ]
    
    except Exception as e:
        print(f"[CHAT] Data gathering error: {e}")
    
    return data

def format_data_for_llm(bq_data: dict, intent: dict) -> str:
    """Format data as readable context for LLM"""
    sections = ["=== EXACT DATA FROM DATABASE ===", "USE THESE NUMBERS EXACTLY — DO NOT MODIFY OR INVENT", ""]
    
    if "brand_satisfaction" in bq_data and bq_data["brand_satisfaction"]:
        brand = bq_data["brand_satisfaction"][0]["brand"]
        sections.append(f"## {brand} Satisfaction by Aspect")
        for row in bq_data["brand_satisfaction"]:
            icon = ASPECT_ICONS.get(row['aspect'], '')
            sections.append(f"- {icon} {row['aspect']}: {row['satisfaction']}% (👍 {row['positive']} / 👎 {row['negative']})")
        sections.append("")
    
    if "demographics" in bq_data and bq_data["demographics"]:
        sections.append("## Buyer Demographics")
        total = sum(row['count'] for row in bq_data["demographics"])
        for row in bq_data["demographics"][:10]:
            pct = round(row['count'] * 100 / total, 1)
            sections.append(f"- {row['persona']} ({row['gender']}): {pct}% ({row['count']} mentions)")
        sections.append("")
    
    if "feature_requests" in bq_data and bq_data["feature_requests"]:
        sections.append("## Feature Requests (R&D Signals)")
        for row in bq_data["feature_requests"]:
            sections.append(f"- \"{row['feature']}\": {row['mentions']} mentions")
        sections.append("")
    
    if "brand_comparison" in bq_data and bq_data["brand_comparison"]:
        sections.append("## Brand Comparison (Market Overview)")
        for i, row in enumerate(bq_data["brand_comparison"], 1):
            marker = "👑" if i == 1 else f"{i}."
            sections.append(f"{marker} {row['brand']}: {row['satisfaction']}% satisfaction (👍 {row['positive']} / 👎 {row['negative']})")
        sections.append("")
    
    return "\n".join(sections)

def get_system_prompt() -> str:
    vehicle_label = "Car" if VEHICLE_TYPE == "car" else "Bike"
    buyer_label = "Buyer" if VEHICLE_TYPE == "car" else "Rider"
    
    return f"""You are SmaartAnalyst, an automotive decision intelligence assistant for {vehicle_label}s.

=== CRITICAL: USE PROVIDED DATA EXACTLY ===
I am providing you with EXACT data from our database. 
DO NOT query the database yourself.
DO NOT modify, round differently, or invent any numbers.
USE THE EXACT PERCENTAGES AND COUNTS PROVIDED BELOW.
If data is not provided, say "data not available" — do NOT make up numbers.

=== WHO YOU SERVE ===
{vehicle_label} brand teams: Brand Manager, Product Planning, R&D, Marketing, Sales, Service

=== RESPONSE FORMAT ===

📊 **Insight**: [2-3 sentences using the EXACT counts/ratios from the data provided]

👥 **{buyer_label} Mix**: [Use EXACT persona percentages from data]

🎯 **Actions by Team**:

👔 Brand Manager: [positioning based on data strengths]

📢 Marketing: 
   ✓ PROMOTE: [top positive aspects from data]
   ✗ ADDRESS: [aspects needing attention from data]

🔬 R&D / Product: [feature requests from data]
🔧 Service: [if Ownership issues in data]

Include 3-4 most relevant teams only.

=== RULES ===
1. USE EXACT NUMBERS from data — no rounding, no inventing
2. Positive Ratio = positive / (positive + negative) — use this for comparisons
3. Be direct — max 250 words
4. If data not provided, say "data not available" """

def get_data_chat_client():
    """Get Gemini Data Analytics chat client"""
    try:
        from google.cloud import geminidataanalytics_v1alpha as gda
        from google.api_core import client_options
        
        gcp_creds = os.environ.get("GCP_CREDENTIALS_JSON", "")
        if not gcp_creds:
            return None
        
        gcp_creds = gcp_creds.strip().strip('"').strip("'")
        
        try:
            if gcp_creds.startswith("{"):
                creds_dict = json.loads(gcp_creds)
            else:
                padding = 4 - len(gcp_creds) % 4
                if padding != 4:
                    gcp_creds += "=" * padding
                creds_dict = json.loads(base64.b64decode(gcp_creds).decode('utf-8'))
            
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
            return gda.DataChatServiceClient(credentials=credentials, client_options=client_options.ClientOptions())
        except:
            return gda.DataChatServiceClient()
    except Exception as e:
        print(f"Data chat client error: {e}")
        return None

@app.post("/api/chat")
async def chat(request: Request, chat_request: ChatRequest):
    """Chat with SmaartAnalyst - Uses CACHED data"""
    try:
        from google.cloud import geminidataanalytics_v1alpha as gda
        
        user_message = chat_request.message
        context_brand = chat_request.context.get("brand") if chat_request.context else None
        
        print(f"[CHAT] Request: message={user_message[:50]}..., context_brand={context_brand}")
        
        # Step 1: Parse intent
        intent = detect_intent(user_message)
        
        if not intent["brand"] and context_brand:
            intent["brand"] = context_brand
        
        # Step 2: Get data FROM CACHE (instant!)
        bq_data = gather_context_data_cached(intent)
        
        # Step 3: Format data for agent
        data_context = format_data_for_llm(bq_data, intent)
        
        print(f"[CHAT] Data fetched from CACHE for {intent.get('brand', 'no brand')}")
        
        # Step 4: Send to Data Agent
        cc = get_data_chat_client()
        if not cc:
            print("[CHAT] Data chat client unavailable")
            return {
                "response": f"📊 **{intent.get('brand', 'Brand')} Analysis**\n\n{data_context}\n\n_Chat service unavailable._",
                "data_used": {"detected_brand": intent.get("brand")}
            }
        
        print("[CHAT] Data chat client initialized")
        
        conv_id = f"smaart-auto-{uuid.uuid4().hex[:8]}"
        
        system_prompt = get_system_prompt()
        enhanced_prompt = f"""{system_prompt}

{data_context}

=== USER QUERY ===
{user_message}

Remember: Use the EXACT numbers and phrases from the data above. Do NOT query the database or invent any numbers."""
        
        print(f"[CHAT] Prompt length: {len(enhanced_prompt)} chars")
        
        parent = f"projects/{PROJECT}/locations/{LOCATION}"
        agent = f"{parent}/dataAgents/{AGENT_ID}"
        conv_path = cc.conversation_path(PROJECT, LOCATION, conv_id)
        
        print(f"[CHAT] Agent: {agent}")
        
        try:
            cc.get_conversation(name=conv_path)
            print("[CHAT] Existing conversation found")
        except Exception as conv_err:
            print(f"[CHAT] Creating new conversation")
            cc.create_conversation(request=gda.CreateConversationRequest(
                parent=parent,
                conversation_id=conv_id,
                conversation=gda.Conversation(agents=[agent])
            ))
        
        print("[CHAT] Sending to agent...")
        stream = cc.chat(request={
            "parent": parent,
            "conversation_reference": {
                "conversation": conv_path,
                "data_agent_context": {"data_agent": agent}
            },
            "messages": [{"user_message": {"text": enhanced_prompt}}]
        })
        
        response_text = ""
        chunk_count = 0
        for chunk in stream:
            chunk_count += 1
            
            if hasattr(chunk, 'system_message') and hasattr(chunk.system_message, 'text'):
                for p in chunk.system_message.text.parts:
                    part_text = str(p)
                    if part_text.startswith('📊') or part_text.startswith('🎯') or part_text.startswith('👔') or part_text.startswith('📢') or part_text.startswith('🏎') or part_text.startswith('🛋') or part_text.startswith('🛡') or part_text.startswith('⚙') or part_text.startswith('👥') or part_text.startswith('🔬') or part_text.startswith('🔧') or part_text.startswith('💼') or part_text.startswith('✓') or part_text.startswith('✗') or '**' in part_text:
                        response_text += part_text + "\n"
            
            if hasattr(chunk, 'agent_message') and hasattr(chunk.agent_message, 'text'):
                for p in chunk.agent_message.text.parts:
                    response_text += str(p)
            elif hasattr(chunk, 'message') and hasattr(chunk.message, 'content'):
                for p in chunk.message.content.parts:
                    response_text += p.text if hasattr(p, 'text') else str(p)
        
        print(f"[CHAT] Total chunks: {chunk_count}, Response length: {len(response_text)}")
        
        if response_text:
            response_text = response_text.replace('💭 ', '')
        
        return {
            "response": response_text or "No response received.",
            "data_used": {
                "detected_brand": intent.get("brand"),
                "analysis_type": intent.get("analysis_type")
            }
        }
    
    except Exception as e:
        print(f"[CHAT] Error: {e}")
        traceback.print_exc()
        return {"response": f"Error: {str(e)}", "data_used": None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
