"""Canonical single-employee execution state and append-only factual trace."""
from __future__ import annotations

from uuid import uuid4

from .workflow import GOAL, closed, legal_candidates, plan


def trace(workflow, phase, node, reason_code, facts=None):
    workflow["trace"].append({"seq": len(workflow["trace"]) + 1, "phase": phase,
                              "workflow_version": workflow["version"], "node": node,
                              "reason_code": reason_code, "evidence": facts or {}})


def current_activity(workflow):
    return next((n for n in workflow["nodes"] if n["type"] == "ACTIVITY" and n["status"] == "CURRENT"), None)


def _install_plan(dataset, workflow, reason):
    employee_id = workflow["employee_id"]
    workflow["state"] = "PLANNING"
    trace(workflow, "PLAN", None, reason, {"remaining_gaps": len(dataset.trajectory(employee_id)["skill_gaps"])})
    nodes, projected, source = plan(dataset, employee_id, workflow["horizon"])
    workflow["state"] = "VERIFYING"
    trace(workflow, "VERIFY", None, "COMPILED", {"activity_count": sum(n["type"] == "ACTIVITY" for n in nodes), "source": source})
    workflow["nodes"].extend(nodes)
    workflow["source"] = source
    workflow["projected_readiness_pct"] = projected["readiness_pct"]
    if closed(dataset.trajectory(employee_id)):
        workflow["state"] = "DONE"
        trace(workflow, "DONE", None, "REQUIREMENTS_MET", {"readiness_pct": dataset.trajectory(employee_id)["readiness_pct"]})
    elif nodes:
        workflow["state"] = "WAITING_USER"
        trace(workflow, "READY", nodes[0]["event_id"], "AWAITING_CONFIRMATION", {"expected_readiness_pct": nodes[0]["readiness_after"]})
    else:
        workflow["state"] = "BLOCKED"
        trace(workflow, "BLOCKED", None, "NO_LEGAL_CANDIDATE", {"remaining_gaps": len(dataset.trajectory(employee_id)["skill_gaps"])})


def create(dataset, employee_id, goal, horizon):
    if employee_id not in dataset.employees:
        raise KeyError(employee_id)
    if goal != {"type": GOAL} or type(horizon) is not int or not 1 <= horizon <= 3:
        raise ValueError("unsupported goal or horizon")
    trajectory = dataset.trajectory(employee_id)
    if trajectory["next_grade"] is None:
        raise ValueError("employee has no next grade")
    workflow = {"id": str(uuid4()), "employee_id": employee_id, "goal": goal, "horizon": horizon,
                "target_grade": trajectory["next_grade"], "state": "PLANNING", "version": 1,
                "nodes": [], "trace": [], "observations": [], "replan_diff": None,
                "observed_readiness_pct": trajectory["readiness_pct"], "projected_readiness_pct": trajectory["readiness_pct"], "source": None}
    _install_plan(dataset, workflow, "GOAL_CREATED")
    return workflow


def view(dataset, workflow):
    from copy import deepcopy
    result = deepcopy(workflow)
    result["observed_readiness_pct"] = dataset.trajectory(workflow["employee_id"])["readiness_pct"]
    return result


def _replan(dataset, workflow, reason):
    old = [n["event_id"] for n in workflow["nodes"] if n["type"] == "ACTIVITY" and n["status"] in {"CURRENT", "TENTATIVE"}]
    for node in workflow["nodes"]:
        if node["status"] in {"CURRENT", "TENTATIVE", "PENDING", "FORECAST"}:
            node["status"] = "DIRTY"
    workflow["state"] = "NEEDS_REPLAN"
    trace(workflow, "REPLAN", None, reason, {"removed": old})
    workflow["version"] += 1
    _install_plan(dataset, workflow, "REPLAN")
    added = [n["event_id"] for n in workflow["nodes"] if n["type"] == "ACTIVITY" and n["status"] in {"CURRENT", "TENTATIVE"}]
    workflow["replan_diff"] = {"removed": old, "added": added, "reason": reason}


def replan(dataset, workflow):
    if workflow["state"] == "DONE":
        raise ValueError("workflow is complete")
    _replan(dataset, workflow, "USER_REQUEST")
    return view(dataset, workflow)


def observe_completion(dataset, workflow, result, planned_event_id=None):
    employee_id = workflow["employee_id"]
    current = current_activity(workflow)
    event_id = result["record"]["event_id"]
    before = result["simulation"]["before"]
    actual = dataset.trajectory(employee_id)  # fresh committed domain state
    expected = current["expected"] if current and event_id == current["event_id"] else None
    actual_changes = [{"skill_id": k, "before": v, "after": actual["current_skills"].get(k, 0)} for k, v in before["current_skills"].items() if actual["current_skills"].get(k, 0) != v]
    matched = expected is not None and all(actual["current_skills"].get(x["skill_id"], 0) == x["after"] for x in expected)
    observation = {"event_id": event_id, "record_id": result["record"]["record_id"], "expected_match": matched,
                   "readiness_before": before["readiness_pct"], "readiness_actual": actual["readiness_pct"],
                   "skill_changes": actual_changes, "remaining_gaps": actual["skill_gaps"]}
    workflow["observations"].append(observation)
    trace(workflow, "OBSERVE", event_id, "COMMITTED_ACTIVITY", {"record_id": observation["record_id"], "readiness_pct": actual["readiness_pct"]})
    if current and event_id == current["event_id"]:
        current["status"] = "COMPLETED"
        check = next(n for n in workflow["nodes"] if n["type"] == "CHECK" and n["step"] == current["step"] and n["status"] == "PENDING")
        check["status"] = "COMPLETED"
        trace(workflow, "CHECK", event_id, "EXPECTED_MATCH" if matched else "EXPECTED_MISMATCH", {"expected_match": matched})
        reassess = next(n for n in workflow["nodes"] if n["type"] == "REASSESS" and n["step"] == current["step"] and n["status"] == "PENDING")
        reassess["status"] = "COMPLETED"
    else:
        trace(workflow, "CHECK", event_id, "EXTERNAL_COMPLETION", {"planned_event_id": current["event_id"] if current else None})
    trace(workflow, "REASSESS", event_id, "GAPS_RECOMPUTED", {"remaining_gaps": len(actual["skill_gaps"])})
    workflow["observed_readiness_pct"] = actual["readiness_pct"]
    if closed(actual):
        for node in workflow["nodes"]:
            if node["status"] in {"CURRENT", "TENTATIVE", "PENDING", "FORECAST"}:
                node["status"] = "DIRTY"
        workflow["state"] = "DONE"
        workflow["projected_readiness_pct"] = actual["readiness_pct"]
        trace(workflow, "DONE", None, "REQUIREMENTS_MET", {"readiness_pct": actual["readiness_pct"]})
        return
    future = [n for n in workflow["nodes"] if n["type"] == "ACTIVITY" and n["status"] == "TENTATIVE"]
    next_node = future[0] if future else None
    legal = {c["event_id"] for c in legal_candidates(dataset, employee_id)}
    if not matched or not next_node or next_node["event_id"] not in legal:
        _replan(dataset, workflow, "TAIL_STALE" if next_node and next_node["event_id"] not in legal else "OBSERVATION_CHANGED")
    else:
        next_node["status"] = "CURRENT"
        workflow["state"] = "WAITING_USER"
        trace(workflow, "NEXT", next_node["event_id"], "NEXT_VERIFIED", {"eligible": True})
        trace(workflow, "READY", next_node["event_id"], "AWAITING_CONFIRMATION", {"expected_readiness_pct": next_node["readiness_after"]})
