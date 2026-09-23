"""Bounded model reranking with deterministic verification and fallback."""
from __future__ import annotations

import json
import os
import queue
import threading
import time
from urllib.request import Request, urlopen

from .engine import Dataset

FACTOR_KEYS = {"grade", "requirement", "gap", "critical", "gain", "max_level", "history", "coverage", "eligibility"}
AI_DEADLINE_SECONDS = 9.0
_model_slot = threading.BoundedSemaphore(1)


def factor_evidence(candidate: dict) -> dict[str, str]:
    helped = [x for x in candidate["effects"] if x["gap_closed"]]
    named = ", ".join(f"{x['skill_id']} +{x['gap_closed']}" for x in helped)
    h = candidate["history"]
    return {
        "grade": "Event targets the employee's current grade.",
        "requirement": f"It develops next-grade requirements: {named}.",
        "gap": f"It closes {candidate['gap_units_closed']} current requirement gap level(s).",
        "critical": f"It closes {candidate['critical_gap_units_closed']} critical gap level(s)." if candidate["critical_gap_units_closed"] else "No critical gap is closed.",
        "gain": "Dataset gain applies to the current skill levels.",
        "max_level": "The projected gain respects each event max_level.",
        "history": f"Similar participation: {h['similar_completed']} completed, {h['similar_missed']} missed, {h['similar_declined']} declined.",
        "coverage": f"It advances {candidate['requirements_helped']} next-grade requirement(s).",
        "eligibility": "Role, grade, prerequisites and session availability are satisfied.",
    }


def verify_proposals(dataset: Dataset, employee_id: str, proposals: list[dict], candidates: list[dict]) -> list[dict]:
    if not isinstance(proposals, list) or not 1 <= len(proposals) <= 3:
        raise ValueError("expected 1–3 proposals")
    lookup = {x["event_id"]: x for x in candidates}
    seen = set()
    verified = []
    for proposal in proposals:
        if not isinstance(proposal, dict):
            raise ValueError("proposal must be an object")
        event_id = proposal.get("event_id")
        if event_id not in dataset.events or event_id not in lookup or event_id in seen:
            raise ValueError(f"unknown, ineligible, useless or duplicate event_id: {event_id}")
        candidate = lookup[event_id]
        event = dataset.events[event_id]
        if not dataset.eligible(employee_id, event):
            raise ValueError("eligibility changed")
        for effect in candidate["effects"]:
            source = next((x for x in event["develops_skills"] if x["skill_id"] == effect["skill_id"]), None)
            if source is None or effect["skill_id"] not in dataset.skills or source["gain"] != effect["gain"] or source["max_level"] != effect["max_level"]:
                raise ValueError("effect does not match dataset")
            if effect["requirement"] is not None and dataset.trajectory(employee_id)["next_grade_requirements"].get(effect["skill_id"]) != effect["requirement"]:
                raise ValueError("requirement does not match dataset")
            if effect["after"] > max(effect["current"], effect["max_level"]):
                raise ValueError("max_level exceeded")
        factors = proposal.get("factors")
        if not isinstance(factors, list) or len(set(factors)) < 3 or any(x not in FACTOR_KEYS for x in factors):
            raise ValueError("at least three distinct supported factors required")
        # The model returns only evidence keys, never free-form factual claims.
        evidence = factor_evidence(candidate)
        explanation = " ".join(evidence[key] for key in dict.fromkeys(factors))
        verified.append({**candidate, "factors": factors, "explanation": explanation})
        seen.add(event_id)
    return verified


def _model_proposals(candidates: list[dict], error: str | None = None) -> list[dict]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    shortlist = []
    for c in candidates[:12]:
        shortlist.append({k: c[k] for k in ("event_id", "eligible", "grade_relevance", "requirement_relevance", "effects", "requirements_helped", "critical_gap_units_closed", "gap_units_closed", "history", "readiness_before", "readiness_after", "score")})
    schema = {"name": "career_recommendations", "strict": True, "schema": {"type": "object", "properties": {"recommendations": {"type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "object", "properties": {"event_id": {"type": "string"}, "factors": {"type": "array", "minItems": 3, "items": {"type": "string", "enum": sorted(FACTOR_KEYS)}}}, "required": ["event_id", "factors"], "additionalProperties": False}}}, "required": ["recommendations"], "additionalProperties": False}}
    body = {"model": os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"), "temperature": 0,
            "response_format": {"type": "json_schema", "json_schema": schema},
            "messages": [{"role": "system", "content": "Select 1–3 event IDs from the supplied structured evidence. Favor critical next-grade gaps, meaningful gain, coverage and participation history. Return only evidence factor keys. No facts or prose."},
                         {"role": "user", "content": json.dumps({"candidates": shortlist, "validation_error": error}, separators=(",", ":"))}]}
    req = Request("https://api.openai.com/v1/chat/completions", data=json.dumps(body).encode(),
                  headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urlopen(req, timeout=8) as response:
        result = json.load(response)
    return json.loads(result["choices"][0]["message"]["content"])["recommendations"]


def recommendations(dataset: Dataset, employee_id: str, use_ai: bool = True) -> dict:
    deadline = time.monotonic() + AI_DEADLINE_SECONDS
    candidates = dataset.candidates(employee_id)
    if not candidates:
        return {"source": "deterministic", "recommendations": [], "candidate_count": 0}
    if use_ai and os.environ.get("OPENAI_API_KEY") and time.monotonic() < deadline and _model_slot.acquire(blocking=False):
        result = queue.Queue(maxsize=1)

        def call_and_verify() -> None:
            try:
                proposals = _model_proposals(candidates)
                verified = verify_proposals(dataset, employee_id, proposals, candidates[:12])
                result.put_nowait(verified)
            except Exception:
                pass
            finally:
                _model_slot.release()

        try:
            threading.Thread(target=call_and_verify, daemon=True, name="career-quest-ai").start()
        except RuntimeError:
            _model_slot.release()
        else:
            try:
                verified = result.get(timeout=max(0, deadline - time.monotonic()))
                if time.monotonic() < deadline:
                    return {"source": "openai_verified", "recommendations": verified, "candidate_count": len(candidates)}
            except queue.Empty:
                pass
    proposals = [{"event_id": x["event_id"], "factors": ["grade", "requirement", "gap", "critical" if x["critical_gap_units_closed"] else "coverage", "gain", "history"]} for x in candidates[:3]]
    return {"source": "deterministic", "recommendations": verify_proposals(dataset, employee_id, proposals, candidates), "candidate_count": len(candidates)}
