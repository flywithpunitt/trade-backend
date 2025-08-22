from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from io import StringIO
from datetime import datetime
import subprocess
import json
import sys
from pathlib import Path
import asyncio
from auth import auth_router
from auth.database import Database

app = FastAPI()

# ✅ Allow frontend (Vite) to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173",
          "*",
      # for local dev
        "https://newfrontend-kohl.vercel.app"],
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
    contents = await file.read()
    df = pd.read_csv(StringIO(contents.decode()), dtype=str)

    df['time'] = pd.to_datetime(
        df['time'].str.replace(r'\+.*', '', regex=True), errors='coerce')

    for col in ['open', 'close', 'high', 'low']:
        if col in df.columns:
            df[col] = df[col].astype(float)

    df['Volume'] = df['Volume'].astype(float)

    try:
        start = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        end = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
        df_filtered = df[(df['time'] >= start) & (df['time'] <= end)]

        if df_filtered.empty:
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
        raise HTTPException(status_code=400, detail=f"Time parsing error: {str(e)}")

    df_filtered = df_filtered.copy()

    def group_volume(col):
        if col not in df_filtered.columns:
            return []

        grouped = df_filtered.groupby(col).agg({
            'Volume': 'sum',
            'time': 'first'
        }).reset_index()

        grouped['time'] = pd.to_datetime(grouped['time'], errors='coerce')
        grouped['time'] = grouped['time'].astype(str)

        # Sort using Excel-like logic
        def sort_excel_style(values):
            def precision_bucket(val, threshold=6):
                val_str = f"{val:.20f}".rstrip('0')
                return len(val_str.split('.')[-1]) <= threshold

            clean = [v for v in values if precision_bucket(v)]
            long = [v for v in values if not precision_bucket(v)]
            return sorted(clean) + sorted(long)

        sorted_prices = sort_excel_style(grouped[col].tolist())
        grouped[col] = pd.Categorical(grouped[col], categories=sorted_prices, ordered=True)
        grouped = grouped.sort_values(by=col)

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

    # Save trigger data to JSON file (APPEND mode)
    data_path = Path(__file__).parent / "trigger_data.json"
    try:
        # Read existing data if file exists
        existing_data = []
        if data_path.exists():
            try:
                with open(data_path, "r") as f:
                    existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    existing_data = [existing_data]  # Convert single object to list
            except json.JSONDecodeError:
                existing_data = []  # If file is corrupted, start fresh
        
        # Add timestamp to the click data
        click_data = {
            **data,
            "clicked_at": datetime.now().isoformat(),
            "click_id": len(existing_data) + 1
        }
        
        # Append new click data
        existing_data.append(click_data)
        
        # Save back to file
        with open(data_path, "w") as f:
            json.dump(existing_data, f, indent=2)
        
        print(f"✅ Bar click #{click_data['click_id']} saved to: {data_path}")
        print(f"📊 Total clicks saved: {len(existing_data)}")
        
    except Exception as e:
        print(f"❌ Error saving data: {e}")
        return {"status": "error", "message": f"Failed to save data: {str(e)}"}

    await asyncio.sleep(1)  # tiny delay before launching script

    # ✅ Launch script using current environment's python
    try:
        script_path = Path(__file__).parent / "launch_tradingview.py"
        if script_path.exists():
            # Use the current environment's python
            subprocess.Popen([sys.executable, str(script_path)])
            print(f"✅ TradingView script launched: {script_path}")
            return {"status": "success", "message": "TradingView script triggered"}
        else:
            print(f"⚠️ Script not found: {script_path}")
            return {"status": "warning", "message": "TradingView script not found"}
    except Exception as e:
        print(f"❌ Error launching script: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/clear-trigger-data")
async def clear_trigger_data():
    """Clear all saved bar click data when generating new chart"""
    data_path = Path(__file__).parent / "trigger_data.json"
    try:
        # Clear the file by writing empty array
        with open(data_path, "w") as f:
            json.dump([], f, indent=2)
        print("🧹 Trigger data cleared - ready for new chart generation")
        return {"status": "success", "message": "Trigger data cleared"}
    except Exception as e:
        print(f"❌ Error clearing data: {e}")
        return {"status": "error", "message": f"Failed to clear data: {str(e)}"}


@app.get("/get-trigger-data-count")
async def get_trigger_data_count():
    """Get the count of saved bar clicks"""
    data_path = Path(__file__).parent / "trigger_data.json"
    try:
        if data_path.exists():
            with open(data_path, "r") as f:
                data = json.load(f)
                count = len(data) if isinstance(data, list) else 1
                return {"count": count}
        return {"count": 0}
    except Exception as e:
        print(f"❌ Error reading data count: {e}")
        return {"count": 0}


@app.get("/get-trigger-data")
async def get_trigger_data():
    """Get all saved bar click data"""
    data_path = Path(__file__).parent / "trigger_data.json"
    try:
        if data_path.exists():
            with open(data_path, "r") as f:
                data = json.load(f)
                return {"data": data if isinstance(data, list) else [data]}
        return {"data": []}
    except Exception as e:
        print(f"❌ Error reading trigger data: {e}")
        return {"data": []}
