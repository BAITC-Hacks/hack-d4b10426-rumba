import json
import os
import tempfile
import threading
import unittest
from copy import deepcopy
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from career_quest.api import App, handler_for
from career_quest.engine import Dataset
from career_quest.workflow import compile_proposal, deterministic_proposal

DATA = Path(__file__).resolve().parents[1] / "data"


def wow_employee(dataset, employee_id="WOW"):
    employee = deepcopy(dataset.employees["E0005"])
    employee.update(employee_id=employee_id, full_name="Workflow Demo", manager_id=None,
                    skills=dict(dataset.profiles[("Backend Engineer", "Senior")]["required_skills"]),
                    last_review_date="2026-09-30")
    employee["skills"]["SK_SYSTEM_DESIGN"] = 3
    employee["skills"]["SK_PUBLIC_SPEAKING"] = 0
    return employee


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "changes.json"
        self.app = App(DATA, self.path)
        self.app.add_profile(wow_employee(self.app.dataset), [])

    def create(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            return self.app.create_workflow("WOW", {"type": "NEXT_GRADE_READINESS"}, 3)

    def test_planning_does_not_mutate_employee_and_demo_forecast(self):
        before = deepcopy(self.app.dataset.current_skills("WOW"))
        workflow = self.create()
        self.assertEqual(before, self.app.dataset.current_skills("WOW"))
        self.assertEqual(workflow["observed_readiness_pct"], 94)
        self.assertEqual(workflow["projected_readiness_pct"], 100)
        self.assertEqual([n["event_id"] for n in workflow["nodes"] if n["type"] == "ACTIVITY"], ["EV_007", "EV_036", "EV_036"])
        self.assertEqual([n["readiness_after"] for n in workflow["nodes"] if n["type"] == "ACTIVITY"], [96, 98, 100])
        self.assertEqual(len(self.app.dataset.history_by_employee["WOW"]), 0)

    def test_unknown_event_and_altered_effects_rejected(self):
        with self.assertRaises(ValueError):
            compile_proposal(self.app.dataset, "WOW", {"schema_version": 1, "steps": [{"event_id": "FAKE", "factors": ["gap", "gain"]}]}, 3)
        with self.assertRaises(ValueError):
            compile_proposal(self.app.dataset, "WOW", {"schema_version": 1, "steps": [{"event_id": "EV_007", "factors": ["gap", "gain"], "effects": [{"skill_id": "SK_SYSTEM_DESIGN", "after": 5}]}]}, 3)

    def test_critical_first_and_sequential_marginal_value(self):
        with self.assertRaises(ValueError):
            compile_proposal(self.app.dataset, "WOW", {"schema_version": 1, "steps": [{"event_id": "EV_036", "factors": ["gap", "gain"]}]}, 3)
        good = deterministic_proposal(self.app.dataset, "WOW", 3)
        self.assertEqual([x["event_id"] for x in good["steps"]], ["EV_007", "EV_036", "EV_036"])
        with self.assertRaises(ValueError):
            compile_proposal(self.app.dataset, "WOW", {"schema_version": 1, "steps": [{"event_id": "EV_007", "factors": ["gap", "gain"]}, {"event_id": "EV_007", "factors": ["gap", "gain"]}]}, 3)
        self.app.dataset.employees["WOW"]["skills"]["SK_PUBLIC_SPEAKING"] = 1
        with self.assertRaises(ValueError):
            compile_proposal(self.app.dataset, "WOW", good, 3)

    def test_confirmation_observation_done_and_persistence(self):
        workflow = self.create()
        before = self.app.dataset.current_skills("WOW")
        with self.assertRaises(ValueError):
            self.app.workflow_command(workflow["id"], {"action": "confirm_completion", "event_id": "EV_007"})
        self.assertEqual(self.app.dataset.current_skills("WOW"), before)
        for event_id in ["EV_007", "EV_036", "EV_036"]:
            workflow = self.app.workflow_command(workflow["id"], {"action": "confirm_completion", "confirmed": True, "event_id": event_id})
            self.assertEqual(workflow["observations"][-1]["event_id"], event_id)
        self.assertEqual(workflow["state"], "DONE")
        self.assertEqual(workflow["observed_readiness_pct"], 100)
        self.assertIn("DONE", [x["phase"] for x in workflow["trace"]])
        restored = App(DATA, self.path).workflow(workflow["id"])
        self.assertEqual(restored["state"], "DONE")
        self.assertEqual(len(restored["observations"]), 3)

    def test_alternative_completion_replans_and_preserves_trace(self):
        workflow = self.create()
        self.app.complete("WOW", "EV_006")
        updated = self.app.workflow(workflow["id"])
        self.assertEqual(updated["observed_readiness_pct"], 96)
        self.assertEqual(updated["observations"][-1]["event_id"], "EV_006")
        self.assertEqual(updated["state"], "WAITING_USER")
        self.assertEqual(updated["replan_diff"]["removed"], ["EV_007", "EV_036", "EV_036"])
        self.assertEqual(updated["replan_diff"]["added"], ["EV_036", "EV_036"])
        self.assertEqual([n["event_id"] for n in updated["nodes"] if n["type"] == "ACTIVITY" and n["status"] == "DIRTY"], ["EV_007", "EV_036", "EV_036"])
        self.assertEqual(updated["version"], 2)
        self.assertIn("REPLAN", [x["phase"] for x in updated["trace"]])
        for event_id in ["EV_036", "EV_036"]:
            updated = self.app.workflow_command(workflow["id"], {"action": "confirm_completion", "confirmed": True, "event_id": event_id})
        self.assertEqual(updated["state"], "DONE")
        self.assertEqual([x["event_id"] for x in updated["observations"]], ["EV_006", "EV_036", "EV_036"])

    def test_manual_replan_preserves_completed_prefix(self):
        workflow = self.create()
        workflow = self.app.workflow_command(workflow["id"], {"action": "confirm_completion", "confirmed": True, "event_id": "EV_007"})
        workflow = self.app.workflow_command(workflow["id"], {"action": "replan"})
        self.assertEqual([n["event_id"] for n in workflow["nodes"] if n["type"] == "ACTIVITY" and n["status"] == "COMPLETED"], ["EV_007"])
        self.assertEqual(workflow["observations"][0]["event_id"], "EV_007")
        self.assertEqual(workflow["version"], 2)

    def test_open_gaps_without_candidates_blocks(self):
        for event in self.app.dataset.events.values():
            event["mandatory"] = True
        workflow = self.create()
        self.assertEqual(workflow["state"], "BLOCKED")
        self.assertEqual(workflow["trace"][-1]["phase"], "BLOCKED")

    def test_no_key_and_ai_error_use_deterministic(self):
        self.assertEqual(self.create()["source"], "deterministic")
        other = wow_employee(self.app.dataset, "WOW2")
        self.app.add_profile(other, [])
        with patch.dict(os.environ, {"OPENAI_API_KEY": "fake"}), patch("career_quest.workflow._model_proposal", side_effect=RuntimeError("provider down")):
            workflow = self.app.create_workflow("WOW2", {"type": "NEXT_GRADE_READINESS"}, 3)
        self.assertEqual(workflow["source"], "deterministic")

    def test_http_goal_plan_alternative_observation_replan_next(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.app))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"

        def request(path, body=None):
            payload = None if body is None else json.dumps(body).encode()
            with urlopen(Request(base + path, data=payload, headers={"Content-Type": "application/json"}), timeout=5) as response:
                return response.status, json.load(response)

        try:
            with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
                status, workflow = request("/api/workflows", {"employee_id": "WOW", "goal": {"type": "NEXT_GRADE_READINESS"}, "horizon": 3})
            self.assertEqual(status, 201)
            workflow_id = workflow["id"]
            self.assertEqual(request(f"/api/workflows/{workflow_id}")[1]["state"], "WAITING_USER")
            with self.assertRaises(HTTPError) as error:
                request(f"/api/workflows/{workflow_id}/commands", {"action": "confirm_completion", "event_id": "EV_007"})
            self.assertEqual(error.exception.code, 400)
            request("/api/activity/complete", {"employee_id": "WOW", "event_id": "EV_006"})
            updated = request(f"/api/workflows/{workflow_id}")[1]
            self.assertEqual(updated["replan_diff"]["added"], ["EV_036", "EV_036"])
            self.assertEqual(updated["observations"][0]["event_id"], "EV_006")
            updated = request(f"/api/workflows/{workflow_id}/commands", {"action": "confirm_completion", "confirmed": True, "event_id": "EV_036"})[1]
            self.assertEqual(updated["state"], "WAITING_USER")
            self.assertEqual(updated["observed_readiness_pct"], 98)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
