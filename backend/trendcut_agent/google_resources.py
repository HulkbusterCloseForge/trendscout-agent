from __future__ import annotations

import json
import urllib.parse
import urllib.request

from .google_auth import refresh_token_if_needed, token_path


def drive_folder_url(folder_id: str) -> str:
    return f"https://drive.google.com/drive/folders/{folder_id}" if folder_id else ""


def sheet_url(sheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}" if sheet_id else ""


def _access_token() -> str:
    access = refresh_token_if_needed(token_path())
    if not access:
        raise RuntimeError("Google OAuth token missing; connect Google first")
    return access


def _request_json(url: str, method: str = "GET", access_token: str | None = None, body: dict | None = None) -> dict:
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def create_trendcut_google_resources(folder_name: str = "TrendScout Agent Outputs", sheet_name: str = "TrendScout Agent Runs") -> dict:
    """Create a Drive folder + Sheets audit log and initialize the Runs header."""
    access = _access_token()
    folder = _request_json(
        "https://www.googleapis.com/drive/v3/files?fields=id,name,webViewLink",
        "POST",
        access,
        {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"},
    )
    folder_id = folder["id"]

    sheet_file = _request_json(
        "https://www.googleapis.com/drive/v3/files?fields=id,name,webViewLink",
        "POST",
        access,
        {
            "name": sheet_name,
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "parents": [folder_id],
        },
    )
    sheet_id = sheet_file["id"]

    _request_json(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}:batchUpdate",
        "POST",
        access,
        {"requests": [{"updateSheetProperties": {"properties": {"sheetId": 0, "title": "Runs"}, "fields": "title"}}]},
    )
    encoded_range = urllib.parse.quote("Runs!A1:I1", safe="!")
    _request_json(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{encoded_range}?valueInputOption=USER_ENTERED",
        "PUT",
        access,
        {
            "values": [[
                "timestamp",
                "run_id",
                "run_name",
                "interest",
                "beat_density",
                "accepted_count",
                "rejected_count",
                "output_url",
                "warnings",
            ]]
        },
    )

    return {
        "folder_id": folder_id,
        "folder_url": folder.get("webViewLink") or drive_folder_url(folder_id),
        "sheet_id": sheet_id,
        "sheet_url": sheet_file.get("webViewLink") or sheet_url(sheet_id),
    }
