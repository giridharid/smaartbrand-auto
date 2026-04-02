"""
Minimal test version - just to verify basic functionality
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="Smaartbrand Test")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return HTMLResponse(content="<h1>Smaartbrand Test - OK</h1>")

@app.get("/health")
async def health():
    return {"status": "healthy"}

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
        "aspect_icons": {"Performance": "🏎️", "Comfort": "🛋️", "Safety": "🛡️"}
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
