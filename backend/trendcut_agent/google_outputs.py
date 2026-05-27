from __future__ import annotations

import csv
import json
import mimetypes
import os
import shutil
import urllib.parse
import urllib.request

from .google_auth import refresh_token_if_needed, token_path
from datetime import datetime, timezone
from pathlib import Path


def _load_google_access_token(output_dir: Path | None = None) -> str | None:
    if os.environ.get("GOOGLE_ACCESS_TOKEN"):
        return os.environ["GOOGLE_ACCESS_TOKEN"]

    candidate_paths = [token_path()]
    if output_dir:
        root = output_dir.parent
        candidate_paths.extend([
            token_path(root / "data"),
            token_path(root),
        ])

    for path in candidate_paths:
        try:
            access = refresh_token_if_needed(path)
            if access:
                return access
        except Exception:
            continue

    configured = os.environ.get("GOOGLE_TOKEN_JSON")
    if configured and Path(configured).exists():
        try:
            data = json.loads(Path(configured).read_text())
            return data.get("access_token")
        except Exception:
            return None
    return None


def _request_json(url: str, method: str = "GET", headers: dict | None = None, body: bytes | None = None) -> dict:
    req = urllib.request.Request(url, method=method, headers=headers or {}, data=body)
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def upload_to_google_drive(video_path: Path, folder_id: str, access_token: str) -> dict:
    boundary = "trendscout_boundary_2026"
    metadata = {"name": video_path.name}
    if folder_id:
        metadata["parents"] = [folder_id]
    mime = mimetypes.guess_type(video_path.name)[0] or "video/mp4"
    body = b"\r\n".join([
        f"--{boundary}".encode(),
        b"Content-Type: application/json; charset=UTF-8\r\n",
        json.dumps(metadata).encode(),
        f"--{boundary}".encode(),
        f"Content-Type: {mime}\r\n".encode(),
        video_path.read_bytes(),
        f"--{boundary}--".encode(),
    ])
    url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink,webContentLink"
    return _request_json(url, "POST", {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": f"multipart/related; boundary={boundary}",
    }, body)


def append_google_sheet(sheet_id: str, row: dict, access_token: str, sheet_range: str = "Runs!A1") -> dict:
    values = [[
        row.get("timestamp", ""),
        row.get("run_id", ""),
        row.get("run_name", ""),
        row.get("interest", ""),
        row.get("beat_density", ""),
        row.get("accepted_count", ""),
        row.get("rejected_count", ""),
        row.get("output_url", ""),
        row.get("warnings", ""),
    ]]
    encoded_range = urllib.parse.quote(sheet_range, safe="!")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{encoded_range}:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
    return _request_json(url, "POST", {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }, json.dumps({"values": values}).encode())


def _make_row(video_url: str, run_record: dict) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_record.get("run_id"),
        "run_name": run_record.get("config", {}).get("run_name"),
        "interest": run_record.get("config", {}).get("interest_prompt"),
        "beat_density": run_record.get("config", {}).get("beat_density"),
        "accepted_count": len(run_record.get("accepted", [])),
        "rejected_count": len(run_record.get("rejected", [])),
        "output_url": video_url,
        "rationale_json": json.dumps(run_record.get("accepted", [])[:10]),
        "warnings": "; ".join(run_record.get("warnings", [])),
    }


def deliver_outputs(video_path: Path, run_record: dict, output_dir: Path) -> dict:
    """Deliver output to Google Drive/Sheets when configured, else local mocks.

    Public MVP keeps Google auth simple: provide GOOGLE_ACCESS_TOKEN or a
    GOOGLE_TOKEN_JSON containing an `access_token`. If unavailable, local mock
    delivery preserves the same UX for hackathon demos.
    """
    cfg = run_record.get("config", {})
    access_token = _load_google_access_token(output_dir)
    drive_folder = cfg.get("google_drive_folder_id") or os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
    sheet_id = cfg.get("google_sheet_id") or os.environ.get("GOOGLE_SHEET_ID", "")

    if access_token and (drive_folder or sheet_id):
        delivery: dict = {"mode": "google"}
        video_url = video_path.as_posix()
        if drive_folder:
            drive_result = upload_to_google_drive(video_path, drive_folder, access_token)
            delivery["drive"] = drive_result
            video_url = drive_result.get("webViewLink") or drive_result.get("webContentLink") or video_url
        row = _make_row(video_url, run_record)
        if sheet_id:
            delivery["sheet"] = append_google_sheet(sheet_id, row, access_token)
        delivery["drive_url"] = video_url
        delivery["sheet_url"] = f"https://docs.google.com/spreadsheets/d/{sheet_id}" if sheet_id else ""
        return delivery

    drive_dir = output_dir / "drive_mock"
    drive_dir.mkdir(parents=True, exist_ok=True)
    delivered_video = drive_dir / video_path.name
    shutil.copy2(video_path, delivered_video)

    sheet_path = output_dir / "trendscout_sheet_mock.csv"
    row = _make_row(delivered_video.as_posix(), run_record)
    write_header = not sheet_path.exists()
    with sheet_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    return {"drive_url": delivered_video.as_posix(), "sheet_url": sheet_path.as_posix(), "mode": "local_mock"}
