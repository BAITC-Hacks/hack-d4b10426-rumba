"""Small JSON API and static frontend server; no external web framework required."""
from __future__ import annotations

import json
import os
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .engine import Dataset
from .recommend import recommendations

ROOT = Path(__file__).resolve().parent.parent


class App:
    def __init__(self, data_dir: str | Path = ROOT / "data", state_file: str | Path = ROOT / "state" / "changes.json"):
        self.dataset = Dataset(data_dir)
        self.state_file = Path(state_file)
        self.lock = threading.RLock()
        self.state = {"profiles": [], "completions": []}
        if self.state_file.exists():
            self.state = json.loads(self.state_file.read_text(encoding="utf-8"))
            for item in self.state["profiles"]:
                self.dataset.add_profile(item["employee"], item.get("history", []))
            for item in self.state["completions"]:
                self.dataset.history.append(item)
                self.dataset.history_by_employee[item["employee_id"]].append(item)

    def save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_file.with_suffix(".tmp")
        temp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.state_file)

    def profile(self, employee_id: str) -> dict:
        employee = self.dataset.employees[employee_id]
        return {**employee, "current_skills": self.dataset.current_skills(employee_id),
                "participation": self.dataset.participation(employee_id)}

    def overview(self) -> dict:
        gap_counts = Counter()
        grade_counts = Counter()
        skill_sums = Counter()
        skill_counts = Counter()
        no_recommendation = 0
        for employee_id, employee in self.dataset.employees.items():
            trajectory = self.dataset.trajectory(employee_id)
            grade_counts[employee["grade"]] += 1
            for gap in trajectory["skill_gaps"]:
                gap_counts[gap["skill_id"]] += 1
            for skill, level in trajectory["current_skills"].items():
                skill_sums[skill] += level
                skill_counts[skill] += 1
            if not self.dataset.candidates(employee_id):
                no_recommendation += 1
        participation = {}
        for event_id, event in self.dataset.events.items():
            rows = [x for x in self.dataset.history if x["event_id"] == event_id]
            participation[event_id] = {"title": event["title"], "participations": len(rows),
                                       "completed": sum(x["status"] == "completed" for x in rows)}
        return {"employee_count": len(self.dataset.employees), "grade_counts": grade_counts,
                "common_skill_gaps": [{"skill_id": skill, "name": self.dataset.skills[skill]["name"], "employees": count}
                                      for skill, count in gap_counts.most_common()],
                "employees_without_recommendation": no_recommendation,
                "average_skill_levels": {skill: round(skill_sums[skill] / count, 2) for skill, count in skill_counts.items()},
                "activity_participation": participation}

    def complete(self, employee_id: str, event_id: str) -> dict:
        with self.lock:
            result = self.dataset.complete(employee_id, event_id)
            self.state["completions"].append(result["record"])
            self.save()
            result["recommendations"] = recommendations(self.dataset, employee_id, use_ai=False)
            return result

    def add_profile(self, employee: dict, history: list[dict]) -> dict:
        with self.lock:
            self.dataset.add_profile(employee, history)
            self.state["profiles"].append({"employee": employee, "history": history})
            self.save()
            return self.profile(employee["employee_id"])


def handler_for(app: App):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, code: int, value: dict | list) -> None:
            body = json.dumps(value, ensure_ascii=False, default=dict).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.reply(200, {})

        def do_GET(self):
            path = unquote(urlparse(self.path).path)
            if path == "/" or path == "/index.html":
                body = (ROOT / "web" / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            try:
                if path == "/api/health":
                    return self.reply(200, {"status": "ok", "as_of_date": app.dataset.as_of_date})
                if path == "/api/hr/overview":
                    return self.reply(200, app.overview())
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[:2] == ["api", "employees"]:
                    employee_id, view = parts[2:]
                    if view == "profile":
                        return self.reply(200, app.profile(employee_id))
                    if view == "trajectory":
                        return self.reply(200, app.dataset.trajectory(employee_id))
                    if view == "recommendations":
                        return self.reply(200, recommendations(app.dataset, employee_id))
                self.reply(404, {"error": "not found"})
            except KeyError:
                self.reply(404, {"error": "unknown employee or event"})
            except Exception as exc:
                self.reply(400, {"error": str(exc)})

        def do_POST(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size > 2_000_000:
                    return self.reply(413, {"error": "request too large"})
                body = json.loads(self.rfile.read(size))
                path = urlparse(self.path).path
                if path == "/api/profiles":
                    return self.reply(201, app.add_profile(body["employee"], body.get("history", [])))
                if path == "/api/activity/simulate":
                    return self.reply(200, app.dataset.simulate(body["employee_id"], body["event_id"]))
                if path == "/api/activity/complete":
                    return self.reply(200, app.complete(body["employee_id"], body["event_id"]))
                self.reply(404, {"error": "not found"})
            except KeyError:
                self.reply(404, {"error": "unknown employee or event"})
            except (ValueError, TypeError) as exc:
                self.reply(400, {"error": str(exc)})

    return Handler


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), handler_for(App()))
    print(f"Career Quest: http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
