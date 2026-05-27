from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]
REDIRECT_URI = "http://127.0.0.1:8765/api/google/callback"


def token_path(default_root: Path | None = None) -> Path:
    configured = os.environ.get("GOOGLE_TOKEN_JSON")
    if configured:
        return Path(configured)
    root = default_root or Path("data")
    return root / "google-token.json"


def client_secret_path() -> Path | None:
    configured = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET_JSON")
    if configured and Path(configured).exists():
        return Path(configured)
    fallback = Path("secrets/google-oauth-client.json")
    return fallback if fallback.exists() else None


def load_client() -> dict:
    path = client_secret_path()
    if not path:
        raise FileNotFoundError("Google OAuth client secret JSON not found")
    data = json.loads(path.read_text())
    return data.get("installed") or data.get("web") or data


def auth_url() -> str:
    client = load_client()
    params = {
        "client_id": client["client_id"],
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)


def exchange_code(code: str, data_root: Path | None = None) -> dict:
    client = load_client()
    body = urllib.parse.urlencode({
        "code": code,
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"}, data=body)
    with urllib.request.urlopen(req, timeout=60) as resp:
        token = json.loads(resp.read().decode())
    token["created_at"] = int(time.time())
    path = token_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(token, indent=2))
    return {"ok": True, "token_path": str(path), "has_refresh_token": bool(token.get("refresh_token"))}


def refresh_token_if_needed(path: Path) -> str | None:
    if not path.exists():
        return None
    token = json.loads(path.read_text())
    access = token.get("access_token")
    expires_in = int(token.get("expires_in") or 0)
    created_at = int(token.get("created_at") or 0)
    if access and (not expires_in or time.time() < created_at + expires_in - 120):
        return access
    refresh = token.get("refresh_token")
    if not refresh:
        return access
    client = load_client()
    body = urllib.parse.urlencode({
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "refresh_token": refresh,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"}, data=body)
    with urllib.request.urlopen(req, timeout=60) as resp:
        fresh = json.loads(resp.read().decode())
    token.update(fresh)
    token["created_at"] = int(time.time())
    path.write_text(json.dumps(token, indent=2))
    return token.get("access_token")


def status(data_root: Path | None = None) -> dict:
    cpath = client_secret_path()
    tpath = token_path(data_root)
    token = {}
    if tpath.exists():
        try:
            token = json.loads(tpath.read_text())
        except Exception:
            token = {}
    return {
        "client_secret_configured": bool(cpath),
        "client_secret_path": str(cpath) if cpath else "",
        "token_configured": tpath.exists(),
        "token_path": str(tpath),
        "has_refresh_token": bool(token.get("refresh_token")),
        "scopes": SCOPES,
        "redirect_uri": REDIRECT_URI,
    }
