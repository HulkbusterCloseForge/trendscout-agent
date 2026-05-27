from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from .config import AutomationConfig, Strictness


@dataclass
class SearchPlan:
    query: str
    keywords: list[str]
    hashtags: list[str]
    rejection_rules: list[str]
    widened: bool = False
    provider: str = "heuristic"
    model: str = "local-heuristic"


@dataclass
class RelevanceDecision:
    accepted: bool
    confidence: float
    rationale: str
    matched_terms: list[str] = field(default_factory=list)
    should_widen_search: bool = False
    provider: str = "heuristic"
    model: str = "local-heuristic"


# This model is available to the current NVIDIA API account and satisfies the
# Nemotron requirement. Some larger Nemotron endpoints appear in /models but
# return account-level 404s unless explicitly enabled.
DEFAULT_NEMOTRON_MODEL = "mistralai/mistral-nemotron"
DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


def _terms(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_+-]{2,}", text.lower())
    stop = {"the", "and", "for", "with", "from", "this", "that", "your", "you", "are", "into", "about", "video", "clips"}
    return sorted({w for w in words if w not in stop})


def _api_key() -> str:
    key = os.environ.get("NEMOTRON_API_KEY") or os.environ.get("NVIDIA_API_KEY") or os.environ.get("LLM_API_KEY") or ""
    if key:
        return key.strip()
    key_file = os.environ.get("NEMOTRON_API_KEY_FILE") or os.environ.get("NVIDIA_API_KEY_FILE") or os.environ.get("LLM_API_KEY_FILE")
    if key_file:
        try:
            return __import__("pathlib").Path(key_file).read_text().strip()
        except Exception:
            return ""
    return ""


def llm_status() -> dict[str, Any]:
    provider = os.environ.get("LLM_PROVIDER", "nemotron").strip().lower() or "nemotron"
    model = os.environ.get("NEMOTRON_MODEL") or os.environ.get("LLM_MODEL") or DEFAULT_NEMOTRON_MODEL
    base_url = (os.environ.get("NVIDIA_BASE_URL") or os.environ.get("LLM_BASE_URL") or DEFAULT_NVIDIA_BASE_URL).rstrip("/")
    api_key_configured = bool(_api_key())
    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_configured": api_key_configured,
        "active_mode": "nemotron" if provider == "nemotron" and api_key_configured else "heuristic_fallback",
    }


def _heuristic_search_plan(config: AutomationConfig, accepted_count: int = 0) -> SearchPlan:
    keywords = _terms(config.interest_prompt)
    if config.auto_widen_search and accepted_count == 0 and config.strictness == Strictness.EXPLORE_ADJACENT:
        widened = True
        query = f"{config.interest_prompt} trends examples highlights"
    else:
        widened = False
        query = config.interest_prompt
    hashtags = ["#" + k.replace("-", "") for k in keywords[:8]]
    rejection_rules = [x.strip() for x in re.split(r"[,\n]", config.exclusions) if x.strip()]
    return SearchPlan(query=query, keywords=keywords, hashtags=hashtags, rejection_rules=rejection_rules, widened=widened)


def _heuristic_verify_candidate(config: AutomationConfig, plan: SearchPlan, metadata: dict, accepted_count: int = 0) -> RelevanceDecision:
    haystack = " ".join(str(metadata.get(k, "")) for k in ["title", "caption", "description", "filename", "source_url", "transcript"])
    haystack_l = haystack.lower()
    exclusions = [r.lower() for r in plan.rejection_rules]
    blocked = []
    for rule in exclusions:
        if not rule:
            continue
        # Avoid false positives from short exclusions embedded in good tennis terms,
        # e.g. "ad" inside "Fedal" or "grand".
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(rule) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, haystack_l):
            blocked.append(rule)
    if blocked:
        return RelevanceDecision(False, 0.95, f"Rejected by exclusion rule: {', '.join(blocked)}")

    matched = [term for term in plan.keywords if term in haystack_l]
    if config.strictness == Strictness.EXACT:
        threshold = max(1, min(2, len(plan.keywords)))
    elif config.strictness == Strictness.BALANCED:
        threshold = 1 if len(plan.keywords) <= 3 else 2
    else:
        threshold = 1

    if len(matched) >= threshold:
        confidence = min(0.99, 0.55 + 0.12 * len(matched))
        return RelevanceDecision(True, confidence, f"Matched interest terms: {', '.join(matched[:6])}", matched)

    # Local demo escape hatch: if no keywords are available, accept so users can test assembly.
    if not plan.keywords:
        return RelevanceDecision(True, 0.5, "No keywords supplied; accepted for demo run")

    widen = config.auto_widen_search and accepted_count < max(2, config.target_source_clips // 3)
    return RelevanceDecision(False, 0.35, "Insufficient match to interest prompt", matched, widen)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _nemotron_chat(messages: list[dict[str, str]], *, timeout: float = 45.0) -> dict[str, Any]:
    status = llm_status()
    api_key = _api_key()
    if status["provider"] != "nemotron" or not api_key:
        raise RuntimeError("Nemotron is not configured")

    payload = {
        "model": status["model"],
        "messages": messages,
        "temperature": 0.1,
        "top_p": 0.7,
        "max_tokens": 700,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        f"{status['base_url']}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Nemotron request failed ({exc.code}): {detail}") from exc
    content = body["choices"][0]["message"]["content"]
    return _extract_json(content)


def _coerce_str_list(value: Any, limit: int = 12) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value if str(x).strip()][:limit]


def build_search_plan(config: AutomationConfig, accepted_count: int = 0) -> SearchPlan:
    """Pre-scan planning gate.

    Uses NVIDIA Nemotron when configured through an OpenAI-compatible NVIDIA NIM
    endpoint. Falls back to a deterministic local planner so the public demo and
    tests keep working without API credentials.
    """
    fallback = _heuristic_search_plan(config, accepted_count)
    status = llm_status()
    if status["active_mode"] != "nemotron":
        return fallback

    system = "You are TrendScout's source discovery planner. Return only valid compact JSON."
    user = {
        "task": "Build a search plan for a persistent autonomous clip-discovery agent.",
        "interest_prompt": config.interest_prompt,
        "exclusions": config.exclusions,
        "region": config.region,
        "strictness": str(config.strictness.value if hasattr(config.strictness, "value") else config.strictness),
        "accepted_count": accepted_count,
        "auto_widen_search": config.auto_widen_search,
        "schema": {"query": "string", "keywords": ["string"], "hashtags": ["#tag"], "rejection_rules": ["string"], "widened": "boolean"},
    }
    try:
        data = _nemotron_chat([
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ])
        return SearchPlan(
            query=str(data.get("query") or fallback.query),
            keywords=_coerce_str_list(data.get("keywords")) or fallback.keywords,
            hashtags=_coerce_str_list(data.get("hashtags"), 8) or fallback.hashtags,
            rejection_rules=_coerce_str_list(data.get("rejection_rules")) or fallback.rejection_rules,
            widened=bool(data.get("widened", fallback.widened)),
            provider="nemotron",
            model=status["model"],
        )
    except Exception as exc:
        fallback.provider = "heuristic_fallback"
        fallback.model = f"local-heuristic; nemotron_error={str(exc)[:180]}"
        return fallback


def verify_candidate(config: AutomationConfig, plan: SearchPlan, metadata: dict, accepted_count: int = 0) -> RelevanceDecision:
    """Post-download/metadata relevance gate.

    Nemotron acts as the core reasoning model when configured; the heuristic path
    remains as a deterministic safety net for local demos and CI.
    """
    fallback = _heuristic_verify_candidate(config, plan, metadata, accepted_count)
    status = llm_status()
    if status["active_mode"] != "nemotron":
        return fallback

    system = "You are TrendScout's post-download relevance verifier. Return only valid compact JSON."
    user = {
        "task": "Decide if this source clip should be included in a beat-matched creator video.",
        "interest_prompt": config.interest_prompt,
        "strictness": str(config.strictness.value if hasattr(config.strictness, "value") else config.strictness),
        "search_plan": plan.__dict__,
        "candidate_metadata": metadata,
        "accepted_count": accepted_count,
        "schema": {"accepted": "boolean", "confidence": "0..1 number", "rationale": "string", "matched_terms": ["string"], "should_widen_search": "boolean"},
    }
    try:
        data = _nemotron_chat([
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False, default=str)},
        ])
        confidence = float(data.get("confidence", fallback.confidence))
        return RelevanceDecision(
            accepted=bool(data.get("accepted", fallback.accepted)),
            confidence=max(0.0, min(1.0, confidence)),
            rationale=str(data.get("rationale") or fallback.rationale),
            matched_terms=_coerce_str_list(data.get("matched_terms")) or fallback.matched_terms,
            should_widen_search=bool(data.get("should_widen_search", fallback.should_widen_search)),
            provider="nemotron",
            model=status["model"],
        )
    except Exception as exc:
        fallback.provider = "heuristic_fallback"
        fallback.model = f"local-heuristic; nemotron_error={str(exc)[:180]}"
        return fallback
