from pathlib import Path

from fastapi.testclient import TestClient

import trendcut_agent.app as app_module
from trendcut_agent.config import AutomationConfig, SourceType
from trendcut_agent.runner import TrendCutRunner
from trendcut_agent.store import JsonStore


def test_config_endpoint_roundtrip(tmp_path, monkeypatch):
    store = JsonStore(tmp_path / "data")
    runner = TrendCutRunner(store)
    monkeypatch.setattr(app_module, "store", store)
    monkeypatch.setattr(app_module, "runner", runner)
    client = TestClient(app_module.app)

    cfg = AutomationConfig(run_name="API Test", interest_prompt="AI real estate", sources=[SourceType.LOCAL_FOLDER]).to_dict()
    response = client.post("/api/config", json={"config": cfg})
    assert response.status_code == 200
    assert response.json()["run_name"] == "API Test"
    assert client.get("/api/config").json()["interest_prompt"] == "AI real estate"


def test_local_sources_endpoint(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "clip.mp4").write_bytes(b"x")
    store = JsonStore(tmp_path / "data")
    store.save_config(AutomationConfig(local_inbox=str(inbox)))
    monkeypatch.setattr(app_module, "store", store)
    monkeypatch.setattr(app_module, "runner", TrendCutRunner(store))
    client = TestClient(app_module.app)

    data = client.get("/api/local-sources").json()
    assert data["files"][0]["filename"] == "clip.mp4"


def test_google_status_endpoint(tmp_path, monkeypatch):
    store = JsonStore(tmp_path / "data")
    store.save_config(AutomationConfig(google_drive_folder_id="folder123", google_sheet_id="sheet123"))
    monkeypatch.setattr(app_module, "store", store)
    monkeypatch.setattr(app_module, "runner", TrendCutRunner(store))
    monkeypatch.setattr(app_module, "DATA_DIR", tmp_path / "data")
    client = TestClient(app_module.app)
    response = client.get("/api/google/status")
    assert response.status_code == 200
    data = response.json()
    assert "redirect_uri" in data
    assert data["drive_folder_url"].endswith("folder123")
    assert data["sheet_url"].endswith("sheet123")


def test_apify_status_endpoint(tmp_path, monkeypatch):
    store = JsonStore(tmp_path / "data")
    monkeypatch.setattr(app_module, "store", store)
    monkeypatch.setattr(app_module, "runner", TrendCutRunner(store))
    client = TestClient(app_module.app)
    response = client.get("/api/apify/status")
    assert response.status_code == 200
    assert response.json()["actor_id"]


def test_llm_status_endpoint(tmp_path, monkeypatch):
    store = JsonStore(tmp_path / "data")
    monkeypatch.setattr(app_module, "store", store)
    monkeypatch.setattr(app_module, "runner", TrendCutRunner(store))
    monkeypatch.delenv("NEMOTRON_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client = TestClient(app_module.app)
    response = client.get("/api/llm/status")
    assert response.status_code == 200
    assert response.json()["provider"] == "nemotron"
