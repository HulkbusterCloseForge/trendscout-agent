from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import AutomationConfig
from . import google_auth
from .google_resources import create_trendcut_google_resources, drive_folder_url, sheet_url
from .llm import llm_status
from .runner import TrendCutRunner
from .store import JsonStore

ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = ROOT / "static"
DATA_DIR = Path(os.environ.get("TRENDCUT_DATA_DIR", ROOT / "data"))

store = JsonStore(DATA_DIR)
runner = TrendCutRunner(store)
app = FastAPI(title="TrendScout Agent", version="0.1.0")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ConfigPayload(BaseModel):
    config: dict


@app.get("/", response_class=HTMLResponse)
def index():
    html = (STATIC_DIR / "index.html").read_text() if (STATIC_DIR / "index.html").exists() else "<h1>TrendScout Agent</h1>"
    return HTMLResponse(html)


@app.get("/api/config")
def get_config():
    return store.load_config().to_dict()


@app.post("/api/config")
def save_config(payload: ConfigPayload):
    try:
        cfg = AutomationConfig.from_dict(payload.config)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store.save_config(cfg)
    return cfg.to_dict()






@app.get("/api/llm/status")
def get_llm_status():
    return llm_status()


@app.get("/api/apify/status")
def apify_status():
    return {
        "token_configured": bool(os.environ.get("APIFY_API_TOKEN")),
        "actor_id": os.environ.get("APIFY_TIKTOK_ACTOR_ID") or store.load_config().apify_actor_id,
        "results_limit": int(os.environ.get("APIFY_RESULTS_LIMIT", str(store.load_config().apify_results_limit))),
        "offline_dataset_configured": bool(os.environ.get("APIFY_TIKTOK_ITEMS_JSON")),
    }


@app.post("/api/demo/live-apify")
async def live_apify_demo():
    if not os.environ.get("APIFY_API_TOKEN") and not os.environ.get("APIFY_TIKTOK_ITEMS_JSON"):
        raise HTTPException(status_code=400, detail="Set APIFY_API_TOKEN or APIFY_TIKTOK_ITEMS_JSON before running live Apify demo")
    cfg = store.load_config()
    cfg.sources = [__import__("trendcut_agent.config", fromlist=["SourceType"]).SourceType.APIFY_TIKTOK]
    cfg.apify_actor_id = cfg.apify_actor_id or "clockworks/tiktok-scraper"
    cfg.apify_results_limit = cfg.apify_results_limit or 5
    if not cfg.interest_prompt:
        cfg.interest_prompt = "AI real estate tools"
    store.save_config(cfg)
    return await runner.run_once()

@app.get("/api/google/status")
def google_status():
    status = google_auth.status(DATA_DIR)
    cfg = store.load_config()
    status.update({
        "drive_folder_id": cfg.google_drive_folder_id,
        "drive_folder_url": drive_folder_url(cfg.google_drive_folder_id),
        "sheet_id": cfg.google_sheet_id,
        "sheet_url": sheet_url(cfg.google_sheet_id),
        "delivery_ready": bool(status.get("token_configured") and cfg.google_drive_folder_id and cfg.google_sheet_id),
    })
    return status


@app.get("/api/google/auth-url")
def google_auth_url():
    try:
        return {"auth_url": google_auth.auth_url(), "redirect_uri": google_auth.REDIRECT_URI}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class GoogleCodePayload(BaseModel):
    code: str


@app.post("/api/google/exchange-code")
def google_exchange_code(payload: GoogleCodePayload):
    try:
        return google_auth.exchange_code(payload.code, DATA_DIR)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/google/create-resources")
def google_create_resources():
    try:
        resources = create_trendcut_google_resources()
        cfg = store.load_config()
        cfg.google_drive_folder_id = resources["folder_id"]
        cfg.google_sheet_id = resources["sheet_id"]
        store.save_config(cfg)
        return resources
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/google/callback", response_class=HTMLResponse)
def google_callback(code: str = ""):
    if not code:
        return HTMLResponse("<h1>Missing Google OAuth code</h1>", status_code=400)
    try:
        result = google_auth.exchange_code(code, DATA_DIR)
        return HTMLResponse(f"<h1>Google connected</h1><p>Token saved to {result['token_path']}</p><p>You can close this tab and return to TrendScout.</p>")
    except Exception as exc:
        return HTMLResponse(f"<h1>Google OAuth failed</h1><pre>{exc}</pre>", status_code=400)

@app.get("/api/status")
def status():
    return runner.status()


@app.get("/api/history")
def history():
    return store.load_history()


@app.post("/api/start")
async def start():
    await runner.start()
    return runner.status()


@app.post("/api/stop")
async def stop():
    await runner.stop()
    return runner.status()


@app.post("/api/run-now")
async def run_now():
    return await runner.run_once()


@app.post("/api/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    cfg = store.load_config()
    audio_dir = Path(cfg.audio_library)
    audio_dir.mkdir(parents=True, exist_ok=True)
    target = audio_dir / file.filename
    target.write_bytes(await file.read())
    cfg.audio_path = str(target)
    store.save_config(cfg)
    return {"audio_path": str(target)}


@app.get("/api/local-sources")
def local_sources():
    cfg = store.load_config()
    folder = Path(cfg.local_inbox)
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for path in sorted(folder.glob("*")):
        if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".m4v", ".webm", ".mkv"}:
            files.append({"filename": path.name, "size_bytes": path.stat().st_size, "path": str(path)})
    return {"folder": str(folder), "files": files}
