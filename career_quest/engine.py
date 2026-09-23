"""Dataset-backed grade, gap, eligibility and activity calculations."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

GRADES = ("Junior", "Middle", "Senior", "Lead")
MISSED = {"dropped", "no_show"}
DECLINED = {"declined"}
RECURRING = {"EV_036"}  # Explicit exception in the starter README.


class Dataset:
    def __init__(self, directory: str | Path):
        directory = Path(directory)
        skill_data = json.loads((directory / "skills.json").read_text(encoding="utf-8-sig"))
        employee_data = json.loads((directory / "employees.json").read_text(encoding="utf-8-sig"))
        event_data = json.loads((directory / "events.json").read_text(encoding="utf-8-sig"))
        self.as_of_date = skill_data["meta"]["as_of_date"]
        self.skills = {x["skill_id"]: x for x in skill_data["skills"]}
        self.profiles = {(x["role"], x["grade"]): x for x in skill_data["role_profiles"]}
        self.events = {x["event_id"]: x for x in event_data["events"]}
        self.employees = {x["employee_id"]: x for x in employee_data["employees"]}
        with (directory / "activity_history.csv").open(encoding="utf-8-sig", newline="") as f:
            self.history = list(csv.DictReader(f))
        self.history_by_employee = defaultdict(list)
        for row in self.history:
            self.history_by_employee[row["employee_id"]].append(row)

    def add_profile(self, employee: dict, history: list[dict] | None = None) -> None:
        employee_id = employee["employee_id"]
        if employee_id in self.employees:
            raise ValueError("employee_id already exists")
        if (employee["role"], employee["grade"]) not in self.profiles:
            raise ValueError("unknown role or grade")
        if any(skill not in self.skills or not 0 <= level <= 5 for skill, level in employee["skills"].items()):
            raise ValueError("invalid employee skills")
        rows = history or []
        if any(row["employee_id"] != employee_id or row["event_id"] not in self.events for row in rows):
            raise ValueError("invalid history reference")
        self.employees[employee_id] = deepcopy(employee)
        self.history.extend(deepcopy(rows))
        self.history_by_employee[employee_id].extend(deepcopy(rows))

    def current_skills(self, employee_id: str) -> dict[str, int]:
        employee = self.employees[employee_id]
        levels = dict(employee["skills"])
        for row in sorted(self.history_by_employee[employee_id], key=lambda r: (r["date"], r["record_id"])):
            if row["status"] == "completed" and (row["date"] > employee["last_review_date"] or row["record_id"].startswith("R_LOCAL_")):
                levels = apply_effects(levels, self.events[row["event_id"]])
        return levels

    def trajectory(self, employee_id: str, levels: dict[str, int] | None = None) -> dict:
        employee = self.employees[employee_id]
        levels = self.current_skills(employee_id) if levels is None else levels
        grade = employee["grade"]
        next_grade = GRADES[GRADES.index(grade) + 1] if grade in GRADES[:-1] else None
        profile = self.profiles.get((employee["role"], next_grade)) if next_grade else None
        requirements = profile["required_skills"] if profile else {}
        critical = set(profile["critical_skills"]) if profile else set()
        gaps = [
            {"skill_id": skill, "name": self.skills[skill]["name"], "current": levels.get(skill, 0),
             "required": minimum, "gap": max(0, minimum - levels.get(skill, 0)), "critical": skill in critical}
            for skill, minimum in requirements.items()
        ]
        gap_units = sum(x["gap"] for x in gaps)
        total_units = sum(requirements.values())
        readiness = round(100 * (total_units - gap_units) / total_units, 1) if total_units else None
        return {
            "employee_id": employee_id, "current_grade": grade, "next_grade": next_grade,
            "current_skills": levels, "next_grade_requirements": requirements,
            "critical_skills": sorted(critical), "skill_gaps": [x for x in gaps if x["gap"]],
            "critical_gaps": [x for x in gaps if x["gap"] and x["critical"]],
            "readiness_pct": readiness, "requirements_met": sum(not x["gap"] for x in gaps),
            "requirements_total": len(gaps), "promotion_skills_ready": not any(x["gap"] and x["critical"] for x in gaps),
        }

    def participation(self, employee_id: str) -> dict:
        rows = self.history_by_employee[employee_id]
        return {"completed": [x for x in rows if x["status"] == "completed"],
                "missed": [x for x in rows if x["status"] in MISSED],
                "declined": [x for x in rows if x["status"] in DECLINED],
                "in_progress": [x for x in rows if x["status"] == "in_progress"]}

    def eligible(self, employee_id: str, event: dict, levels: dict[str, int] | None = None) -> bool:
        employee = self.employees[employee_id]
        levels = self.current_skills(employee_id) if levels is None else levels
        if event["mandatory"] or employee["role"] not in event["target_roles"] or employee["grade"] not in event["target_grades"]:
            return False
        if any(levels.get(skill, 0) < minimum for skill, minimum in event["prerequisites"].items()):
            return False
        if event["format"] != "self_paced" and not any(d >= self.as_of_date for d in event["upcoming_sessions"]):
            return False
        rows = self.history_by_employee[employee_id]
        if event["event_id"] not in RECURRING and any(x["event_id"] == event["event_id"] and x["status"] == "completed" for x in rows):
            return False
        if any(x["event_id"] == event["event_id"] and x["status"] == "in_progress" for x in rows):
            return False
        return True

    def candidates(self, employee_id: str) -> list[dict]:
        before = self.trajectory(employee_id)
        if before["next_grade"] is None:
            return []
        levels = before["current_skills"]
        requirements = before["next_grade_requirements"]
        critical = set(before["critical_skills"])
        rows = self.history_by_employee[employee_id]
        result = []
        for event in self.events.values():
            if not self.eligible(employee_id, event, levels):
                continue
            after_levels = apply_effects(levels, event)
            effects = []
            for effect in event["develops_skills"]:
                skill = effect["skill_id"]
                delta = after_levels.get(skill, 0) - levels.get(skill, 0)
                if delta <= 0:
                    continue
                minimum = requirements.get(skill, 0)
                useful = min(delta, max(0, minimum - levels.get(skill, 0)))
                effects.append({"skill_id": skill, "current": levels.get(skill, 0), "after": after_levels[skill],
                                "gain": effect["gain"], "max_level": effect["max_level"],
                                "requirement": minimum or None, "gap_closed": useful, "critical": skill in critical})
            helped = [x for x in effects if x["gap_closed"] > 0]
            if not helped:
                continue
            related = [x for x in rows if x["event_id"] in self.events and
                       (x["event_id"] == event["event_id"] or self.events[x["event_id"]]["type"] == event["type"] or
                        bool({y["skill_id"] for y in self.events[x["event_id"]]["develops_skills"]} &
                             {y["skill_id"] for y in event["develops_skills"]}))]
            history = {"similar_completed": sum(x["status"] == "completed" for x in related),
                       "similar_missed": sum(x["status"] in MISSED for x in related),
                       "similar_declined": sum(x["status"] in DECLINED for x in related)}
            critical_units = sum(x["gap_closed"] for x in helped if x["critical"])
            gap_units = sum(x["gap_closed"] for x in helped)
            score = round(10 * critical_units + 3 * gap_units + 2 * len(helped) -
                          1.5 * history["similar_missed"] - 2 * history["similar_declined"] +
                          min(2, history["similar_completed"]) - 0.02 * event["duration_hours"], 2)
            result.append({"event_id": event["event_id"], "title": event["title"], "type": event["type"],
                           "format": event["format"], "duration_hours": event["duration_hours"],
                           "eligible": True, "grade_relevance": True, "requirement_relevance": True,
                           "effects": effects, "requirements_helped": len(helped),
                           "critical_gap_units_closed": critical_units, "gap_units_closed": gap_units,
                           "history": history, "readiness_before": before["readiness_pct"],
                           "readiness_after": self.trajectory(employee_id, after_levels)["readiness_pct"],
                           "score": score})
        return sorted(result, key=lambda x: (-x["score"], x["event_id"]))

    def simulate(self, employee_id: str, event_id: str) -> dict:
        event = self.events[event_id]
        before = self.trajectory(employee_id)
        if not self.eligible(employee_id, event, before["current_skills"]):
            raise ValueError("event is not eligible")
        after = self.trajectory(employee_id, apply_effects(before["current_skills"], event))
        return {"event_id": event_id, "before": before, "after": after,
                "skill_changes": [dict(skill_id=x["skill_id"], before=before["current_skills"].get(x["skill_id"], 0),
                                       after=after["current_skills"].get(x["skill_id"], 0))
                                  for x in event["develops_skills"]]}

    def complete(self, employee_id: str, event_id: str) -> dict:
        simulation = self.simulate(employee_id, event_id)
        record = {"record_id": f"R_LOCAL_{len(self.history) + 1}", "employee_id": employee_id,
                  "event_id": event_id, "date": self.as_of_date, "due_date": "", "status": "completed",
                  "completion_pct": "100", "score": "", "feedback_rating": "", "assigned_by": "self"}
        self.history.append(record)
        self.history_by_employee[employee_id].append(record)
        return {"record": record, "trajectory": self.trajectory(employee_id), "simulation": simulation}


def apply_effects(levels: dict[str, int], event: dict) -> dict[str, int]:
    updated = dict(levels)
    for effect in event["develops_skills"]:
        skill = effect["skill_id"]
        current = updated.get(skill, 0)
        updated[skill] = max(current, min(current + effect["gain"], effect["max_level"]))
    return updated
