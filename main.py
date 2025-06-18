from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from io import StringIO
from datetime import datetime
import subprocess
import json
from pathlib import Path
import asyncio
from auth import auth_router
from auth.database import Database
import os

app = FastAPI()

# ✅ Allow frontend (Vite) to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173",  # for local dev
        "https://trading-frontend-gamma.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Include auth routes
app.include_router(auth_router, prefix="/api")

@app.on_event("startup")
async def startup_db_client():
    await Database.connect_db()

@app.on_event("shutdown")
async def shutdown_db_client():
    await Database.close_db()

@app.post("/upload-and-process")
async def upload_and_process(
    file: UploadFile = File(...),
    script: str = Form(...),
    timeframe: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...)
):
    # Clear trigger_data.json at the start of a new upload
    data_path = Path(__file__).parent.parent / "backend/trigger_data.json"
    with open(data_path, "w") as f:
        json.dump([], f)

    print("📥 Received:")
    print("script:", script)
    print("timeframe:", timeframe)
    print("start_time:", start_time)
    print("end_time:", end_time)

    contents = await file.read()
    df = pd.read_csv(StringIO(contents.decode()), dtype=str)

    # ✅ Remove timezone info (like +10:00) and parse as normal datetime
    df['time'] = pd.to_datetime(
        df['time'].str.replace(r'\+.*', '', regex=True),
        errors='coerce'
    )

    # ✅ Convert OHLC to float
    for col in ['open', 'close', 'high', 'low']:
        if col in df.columns:
            df[col] = df[col].astype(float)

    df['Volume'] = df['Volume'].astype(float)

    try:
        print("🧪 Attempting to parse:")
        print("  Start:", start_time)
        print("  End  :", end_time)

        start = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        end = datetime.strptime(end_time, "%Y-%m-%d %H:%M")

        print("✅ Parsed start:", start)
        print("✅ Parsed end  :", end)

        print("📊 Filtering DataFrame...")
        print("  DF time min:", df['time'].min())
        print("  DF time max:", df['time'].max())

        df_filtered = df[(df['time'] >= start) & (df['time'] <= end)]

        if df_filtered.empty:
            print("🚨 No data in the given time range.")
            return {
                "symbol": script,
                "timeframe": timeframe,
                "volume_vs_open": [],
                "volume_vs_close": [],
                "volume_vs_high": [],
                "volume_vs_low": [],
                "message": "No data found in selected time range."
            }

    except Exception as e:
        print("❌ Time parsing/filtering failed:", e)
        raise HTTPException(status_code=400, detail=f"Time parsing error: {str(e)}")

    # ✅ Sorted by price column, but keeps first timestamp for TradingView trigger
    def group_volume(col):
        if col not in df_filtered.columns:
            return []

        grouped = df_filtered.groupby(col).agg({
            'Volume': 'sum',
            'time': 'first'  # ✅ Keep first time for each price
        }).reset_index()

        grouped = grouped.sort_values(by=col, ascending=True)
        grouped['time'] = pd.to_datetime(grouped['time'], errors='coerce')
        grouped['time'] = grouped['time'].astype(str)

        return grouped.to_dict(orient='records')

    return {
        "symbol": script,
        "timeframe": timeframe,
        "volume_vs_open": group_volume('open'),
        "volume_vs_close": group_volume('close'),
        "volume_vs_high": group_volume('high'),
        "volume_vs_low": group_volume('low')
    }

@app.post("/trigger-tradingview")
async def trigger_tradingview(request: Request):
    data = await request.json()

    if data.get("source") != "click":
        return {"status": "ignored", "message": "Blocked non-click trigger"}

    print("📅 🔥 TRIGGER HIT from source: click")
    print("📦 Trigger data received:", json.dumps(data, indent=2))

    # Save trigger data to JSON file
    data_path = Path(__file__).parent.parent / "backend/trigger_data.json"
    with open(data_path, "w") as f:
        json.dump(data, f, indent=2)

    await asyncio.sleep(1)  # tiny delay before launching script

    # ✅ Launch script using venv python
    try:
        script_path = Path(__file__).parent / "launch_tradingview.py"
        subprocess.Popen([r"C:\Users\HP\tradingview\backend\env\Scripts\python.exe", str(script_path)])
        return {"status": "success", "message": "TradingView script triggered"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/append-trigger")
async def append_trigger(request: Request):
    data = await request.json()
    data_path = Path(__file__).parent.parent / "backend/trigger_data.json"
    # Load existing triggers or start a new list
    if os.path.exists(data_path):
        with open(data_path, "r") as f:
            try:
                triggers = json.load(f)
                if not isinstance(triggers, list):
                    triggers = [triggers]
            except Exception:
                triggers = []
    else:
        triggers = []
    # Append new trigger
    triggers.append(data)
    with open(data_path, "w") as f:
        json.dump(triggers, f, indent=2)
    return {"status": "ok", "message": "Trigger appended."}