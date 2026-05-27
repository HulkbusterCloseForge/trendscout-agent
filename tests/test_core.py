import asyncio
from pathlib import Path

from trendcut_agent.config import AutomationConfig
from trendcut_agent.llm import build_search_plan, llm_status, verify_candidate
from trendcut_agent.google_outputs import _load_google_access_token
from trendcut_agent.runner import TrendCutRunner
from trendcut_agent.sources import audio_fingerprint, extract_apify_tiktok_mp4, list_local_sources
from trendcut_agent.store import JsonStore


def test_config_roundtrip():
    cfg = AutomationConfig(beat_density=4, sources=[])
    data = cfg.to_dict()
    assert AutomationConfig.from_dict(data).beat_density == 4


def test_pre_and_post_relevance_gates():
    cfg = AutomationConfig(interest_prompt="AI real estate tools", exclusions="crypto", strictness="balanced")
    plan = build_search_plan(cfg)
    good = verify_candidate(cfg, plan, {"caption": "New AI tools for real estate agents"})
    bad = verify_candidate(cfg, plan, {"caption": "crypto trading clip"})
    assert good.accepted
    assert not bad.accepted


def test_llm_status_defaults_to_nemotron_fallback(monkeypatch):
    monkeypatch.delenv("NEMOTRON_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("NEMOTRON_API_KEY_FILE", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY_FILE", raising=False)
    monkeypatch.delenv("LLM_API_KEY_FILE", raising=False)
    status = llm_status()
    assert status["provider"] == "nemotron"
    assert "nemotron" in status["model"].lower()
    assert status["active_mode"] == "heuristic_fallback"


def test_nemotron_adapter_shapes_plan_and_decision(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nemotron")
    monkeypatch.setenv("NEMOTRON_API_KEY", "test-key")

    responses = iter([
        {"query": "AI real estate tools", "keywords": ["ai", "real estate"], "hashtags": ["#ai"], "rejection_rules": ["crypto"], "widened": False},
        {"accepted": True, "confidence": 0.91, "rationale": "Nemotron matched the niche", "matched_terms": ["ai"], "should_widen_search": False},
    ])
    monkeypatch.setattr("trendcut_agent.llm._nemotron_chat", lambda *args, **kwargs: next(responses))

    cfg = AutomationConfig(interest_prompt="AI real estate tools", exclusions="crypto")
    plan = build_search_plan(cfg)
    decision = verify_candidate(cfg, plan, {"caption": "AI lead gen for real estate agents"})
    assert plan.provider == "nemotron"
    assert decision.provider == "nemotron"
    assert decision.accepted


def test_apify_direct_mp4_extraction():
    assert extract_apify_tiktok_mp4({"videoMeta": {"downloadAddr": "a.mp4"}}) == "a.mp4"
    assert extract_apify_tiktok_mp4({"mediaUrls": ["b.mp4"]}) == "b.mp4"


def test_local_source_listing(tmp_path: Path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "b.txt").write_text("no")
    assert [p.name for p in list_local_sources(tmp_path)] == ["a.mp4"]


def test_audio_fingerprint_fallback(tmp_path: Path):
    p = tmp_path / "fake.mp4"
    p.write_bytes(b"not a real video")
    assert len(audio_fingerprint(p)) == 64


def test_google_token_lookup_uses_project_data_dir(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    token_dir = tmp_path / "data"
    token_dir.mkdir()
    (token_dir / "google-token.json").write_text('{"access_token":"test-access","expires_in":3600,"created_at":9999999999}')
    assert _load_google_access_token(tmp_path / "output") == "test-access"


def test_runner_records_discovery_errors(tmp_path: Path, monkeypatch):
    store = JsonStore(tmp_path / "data")
    cfg = AutomationConfig(output_dir=str(tmp_path / "output"), local_inbox=str(tmp_path / "inbox"), audio_library=str(tmp_path / "audio"))
    store.save_config(cfg)

    def boom(*args, **kwargs):
        raise RuntimeError("Apify actor request failed (403): Monthly usage hard limit exceeded")

    monkeypatch.setattr("trendcut_agent.runner.discover_candidates", boom)
    result = asyncio.run(TrendCutRunner(store).run_once())
    assert result["status"] == "failed"
    assert "Monthly usage hard limit exceeded" in result["error"]
