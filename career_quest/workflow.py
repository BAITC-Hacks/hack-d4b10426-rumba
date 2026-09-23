"""Small, verified next-grade workflow compiler and bounded proposal planner."""
from __future__ import annotations

import json
import os
import queue
import threading

from . import recommend

GOAL = "NEXT_GRADE_READINESS"
FACTORS = recommend.FACTOR_KEYS


def closed(trajectory):
    return trajectory["next_grade"] is not None and not trajectory["skill_gaps"]


def legal_candidates(dataset, employee_id):
    trajectory = dataset.trajectory(employee_id)
    candidates = dataset.candidates(employee_id)
    if trajectory["critical_gaps"] and any(c["critical_gap_units_closed"] for c in candidates):
        candidates = [c for c in candidates if c["critical_gap_units_closed"]]
    return candidates


def _project(dataset, employee_id, event_id):
    # Dataset.complete is the existing domain simulator/transition. Only a copy is changed.
    dataset.complete(employee_id, event_id)


def compile_proposal(dataset, employee_id, proposal, horizon):
    if not isinstance(proposal, dict) or set(proposal) != {"schema_version", "steps"} or proposal["schema_version"] != 1:
        raise ValueError("invalid proposal schema")
    steps = proposal["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= horizon:
        raise ValueError("invalid step count")
    from copy import deepcopy
    projected = deepcopy(dataset)
    nodes = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or set(step) != {"event_id", "factors"}:
            raise ValueError("step may contain only event_id and factors")
        event_id, factors = step["event_id"], step["factors"]
        if not isinstance(event_id, str) or event_id not in projected.events:
            raise ValueError("unknown event")
        if not isinstance(factors, list) or len(factors) < 2 or len(set(factors)) != len(factors) or any(f not in FACTORS for f in factors):
            raise ValueError("invalid evidence factors")
        before = projected.trajectory(employee_id)
        if not before["next_grade"] or not before["next_grade_requirements"]:
            raise ValueError("missing target requirements")
        event = projected.events[event_id]
        if not event["develops_skills"] or any(e["skill_id"] not in projected.skills or type(e["gain"]) is not int or e["gain"] <= 0 or type(e["max_level"]) is not int or not 0 <= e["max_level"] <= 5 for e in event["develops_skills"]):
            raise ValueError("invalid dataset effects")
        candidates = {c["event_id"]: c for c in legal_candidates(projected, employee_id)}
        if event_id not in candidates:
            raise ValueError("ineligible, noncritical or marginally useless event")
        simulation = projected.simulate(employee_id, event_id)
        candidate = candidates[event_id]
        nodes.extend([
            {"type": "ACTIVITY", "step": index + 1, "event_id": event_id, "title": event["title"], "factors": factors,
             "expected": simulation["skill_changes"], "readiness_before": before["readiness_pct"],
             "readiness_after": simulation["after"]["readiness_pct"], "gap_units_closed": candidate["gap_units_closed"],
             "critical_gap_units_closed": candidate["critical_gap_units_closed"], "status": "CURRENT" if index == 0 else "TENTATIVE"},
            {"type": "CHECK", "step": index + 1, "status": "PENDING"},
            {"type": "REASSESS", "step": index + 1, "status": "PENDING"},
        ])
        _project(projected, employee_id, event_id)
        if closed(projected.trajectory(employee_id)):
            if index != len(steps) - 1:
                raise ValueError("unnecessary future step")
            nodes.append({"type": "COMPLETE", "status": "FORECAST"})
    return nodes, projected.trajectory(employee_id)


def deterministic_proposal(dataset, employee_id, horizon):
    from copy import deepcopy
    projected = deepcopy(dataset)
    steps = []
    for _ in range(horizon):
        candidates = legal_candidates(projected, employee_id)
        if not candidates:
            break
        chosen = candidates[0]
        steps.append({"event_id": chosen["event_id"], "factors": ["critical", "gap", "gain"] if chosen["critical_gap_units_closed"] else ["gap", "coverage", "gain"]})
        _project(projected, employee_id, chosen["event_id"])
        if closed(projected.trajectory(employee_id)):
            break
    return {"schema_version": 1, "steps": steps}


def _model_proposal(dataset, employee_id, horizon):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    trajectory = dataset.trajectory(employee_id)
    candidates = legal_candidates(dataset, employee_id)[:12]
    evidence = [{k: c[k] for k in ("event_id", "effects", "critical_gap_units_closed", "gap_units_closed", "readiness_before", "readiness_after", "history", "score")} for c in candidates]
    schema = {"name": "career_workflow_proposal", "strict": True, "schema": {"type": "object", "properties": {"schema_version": {"type": "integer", "enum": [1]}, "steps": {"type": "array", "minItems": 1, "maxItems": horizon, "items": {"type": "object", "properties": {"event_id": {"type": "string"}, "factors": {"type": "array", "minItems": 2, "items": {"type": "string", "enum": sorted(FACTORS)}},}, "required": ["event_id", "factors"], "additionalProperties": False}}}, "required": ["schema_version", "steps"], "additionalProperties": False}}
    body = {"model": os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"), "temperature": 0,
            "response_format": {"type": "json_schema", "json_schema": schema},
            "messages": [{"role": "system", "content": "Propose 1-3 event IDs and evidence factor keys for next-grade readiness. Critical gaps first. Return only the specified JSON. Future steps are tentative. Never claim employee state, effects, skills, tools, completion or status."},
                         {"role": "user", "content": json.dumps({"goal": {"type": GOAL}, "obligations": trajectory["skill_gaps"], "legal_candidate_transitions": evidence}, separators=(",", ":"))}]}
    req = recommend.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with recommend.urlopen(req, timeout=8) as response:
        return json.loads(json.load(response)["choices"][0]["message"]["content"])


def plan(dataset, employee_id, horizon, use_ai=True):
    if closed(dataset.trajectory(employee_id)):
        return [], dataset.trajectory(employee_id), "deterministic"
    if use_ai and os.environ.get("OPENAI_API_KEY") and recommend._model_slot.acquire(blocking=False):
        result = queue.Queue(maxsize=1)
        def call():
            try:
                result.put_nowait(_model_proposal(dataset, employee_id, horizon))
            except Exception:
                pass
            finally:
                recommend._model_slot.release()
        threading.Thread(target=call, daemon=True, name="career-workflow-ai").start()
        try:
            proposal = result.get(timeout=recommend.AI_DEADLINE_SECONDS)
            nodes, projected = compile_proposal(dataset, employee_id, proposal, horizon)
            return nodes, projected, "openai_verified"
        except (queue.Empty, ValueError):
            pass
    proposal = deterministic_proposal(dataset, employee_id, horizon)
    if not proposal["steps"]:
        return [], dataset.trajectory(employee_id), "deterministic"
    nodes, projected = compile_proposal(dataset, employee_id, proposal, horizon)
    return nodes, projected, "deterministic"
