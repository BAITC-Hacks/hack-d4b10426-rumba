import tempfile
import json
import os
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from career_quest.api import App, handler_for
from career_quest.engine import Dataset, apply_effects
from career_quest.recommend import recommendations, verify_proposals

DATA = Path(__file__).resolve().parents[1] / "data"


class CareerQuestTests(unittest.TestCase):
    def setUp(self):
        self.dataset = Dataset(DATA)

    def employee(self, employee_id="JUDGE_1", role="Backend Engineer", grade="Junior", skills=None):
        return {"employee_id": employee_id, "full_name": "Judge Profile", "department": "Backend Development",
                "role": role, "grade": grade, "manager_id": None, "hire_date": "2026-01-01",
                "tenure_months": 9, "work_format": "office", "preferred_language": "en",
                "career_goal": None, "skills": skills or {}, "last_review_date": "2026-09-30"}

    def test_critical_gap_outweighs_lowest_unrelated_skill(self):
        skills = dict(self.dataset.profiles[("Backend Engineer", "Middle")]["required_skills"])
        skills["SK_API_DESIGN"] = 2
        skills["SK_PUBLIC_SPEAKING"] = 0
        self.dataset.add_profile(self.employee(skills=skills))
        picks = recommendations(self.dataset, "JUDGE_1", use_ai=False)["recommendations"]
        self.assertTrue(picks)
        self.assertGreater(picks[0]["critical_gap_units_closed"], 0)

    def test_three_similar_misses_affect_score_and_explanation(self):
        skills = {"SK_API_DESIGN": 2, "SK_SYSTEM_DESIGN": 1}
        history = [{"record_id": f"J{i}", "employee_id": "JUDGE_1", "event_id": "EV_005",
                    "date": f"2026-09-0{i}", "status": "no_show"} for i in range(1, 4)]
        baseline = self.employee(skills=skills)
        self.dataset.add_profile(baseline)
        initial = next(x for x in self.dataset.candidates("JUDGE_1") if x["event_id"] == "EV_005")
        other = Dataset(DATA)
        other.add_profile(baseline | {"employee_id": "JUDGE_2"}, [x | {"employee_id": "JUDGE_2"} for x in history])
        affected = next(x for x in other.candidates("JUDGE_2") if x["event_id"] == "EV_005")
        self.assertLess(affected["score"], initial["score"])
        self.assertEqual(affected["history"]["similar_missed"], 3)
        verified = verify_proposals(other, "JUDGE_2", [{"event_id": "EV_005", "factors": ["gap", "gain", "history"]}], other.candidates("JUDGE_2"))
        self.assertIn("3 missed", verified[0]["explanation"])

    def test_max_level_makes_gain_useless(self):
        skills = dict(self.dataset.profiles[("Backend Engineer", "Middle")]["required_skills"])
        skills["SK_SYSTEM_DESIGN"] = 3
        skills["SK_API_DESIGN"] = 3
        self.dataset.add_profile(self.employee(skills=skills))
        self.assertNotIn("EV_005", [x["event_id"] for x in self.dataset.candidates("JUDGE_1")])
        self.assertEqual(apply_effects({"SK_API_DESIGN": 4}, self.dataset.events["EV_005"])["SK_API_DESIGN"], 4)

    def test_unrelated_skill_does_not_rank_first(self):
        skills = dict(self.dataset.profiles[("Backend Engineer", "Middle")]["required_skills"])
        skills["SK_API_DESIGN"] = 2
        skills["SK_PROSPECTING"] = 0
        self.dataset.add_profile(self.employee(skills=skills))
        unrelated = deepcopy(self.dataset.events["EV_005"])
        unrelated["event_id"] = "JUDGE_UNRELATED"
        unrelated["develops_skills"] = [{"skill_id": "SK_PROSPECTING", "gain": 5, "max_level": 5}]
        self.dataset.events["JUDGE_UNRELATED"] = unrelated
        picks = self.dataset.candidates("JUDGE_1")
        self.assertTrue(picks)
        self.assertNotIn("JUDGE_UNRELATED", [x["event_id"] for x in picks])
        self.assertGreater(picks[0]["gap_units_closed"], 0)

    def test_new_profile_and_history_without_hardcoding(self):
        employee = self.employee(employee_id="ARBITRARY_NEW_ID", skills={"SK_API_DESIGN": 1})
        history = [{"record_id": "NEW1", "employee_id": "ARBITRARY_NEW_ID", "event_id": "EV_005",
                    "date": "2026-09-30", "status": "declined"}]
        self.dataset.add_profile(employee, history)
        self.assertEqual(self.dataset.participation("ARBITRARY_NEW_ID")["declined"][0]["event_id"], "EV_005")
        self.assertEqual(self.dataset.trajectory("ARBITRARY_NEW_ID")["current_grade"], "Junior")

    def test_ai_invalid_id_is_rejected(self):
        self.dataset.add_profile(self.employee(skills={"SK_API_DESIGN": 1}))
        with self.assertRaises(ValueError):
            verify_proposals(self.dataset, "JUDGE_1", [{"event_id": "FAKE", "factors": ["grade", "gap", "gain"]}], self.dataset.candidates("JUDGE_1"))

    def test_ai_invalid_id_falls_back_to_verified_ranking(self):
        self.dataset.add_profile(self.employee(skills={"SK_API_DESIGN": 1}))
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}), patch(
            "career_quest.recommend._model_proposals",
            return_value=[{"event_id": "FAKE", "factors": ["grade", "gap", "gain"]}],
        ):
            result = recommendations(self.dataset, "JUDGE_1")
        self.assertEqual(result["source"], "deterministic")
        self.assertTrue(result["recommendations"])
        self.assertNotEqual(result["recommendations"][0]["event_id"], "FAKE")

    def test_slow_response_body_falls_back_within_deadline(self):
        self.dataset.add_profile(self.employee(skills={"SK_API_DESIGN": 1}))
        entered = threading.Event()
        release = threading.Event()

        class SlowResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def read(self, *_):
                entered.set()
                release.wait(2)
                return b'{"choices":[{"message":{"content":"{\\"recommendations\\":[{\\"event_id\\":\\"EV_005\\",\\"factors\\":[\\"grade\\",\\"gap\\",\\"gain\\"]}]}"}}]}'

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch("career_quest.recommend.AI_DEADLINE_SECONDS", 0.2), patch("career_quest.recommend.urlopen", return_value=SlowResponse()):
            start = time.monotonic()
            result = recommendations(self.dataset, "JUDGE_1")
            elapsed = time.monotonic() - start
            self.assertTrue(entered.is_set())
            self.assertEqual(result["source"], "deterministic")
            self.assertLess(elapsed, 0.5)
            second_start = time.monotonic()
            self.assertEqual(recommendations(self.dataset, "JUDGE_1")["source"], "deterministic")
            self.assertLess(time.monotonic() - second_start, 0.5)
            release.set()

    def test_no_api_key_keeps_deterministic_recommendations(self):
        self.dataset.add_profile(self.employee(skills={"SK_API_DESIGN": 1}))
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), patch("career_quest.recommend._model_proposals") as model:
            result = recommendations(self.dataset, "JUDGE_1")
        self.assertEqual(result["source"], "deterministic")
        self.assertTrue(result["recommendations"])
        model.assert_not_called()

    def test_failed_import_leaves_persistence_and_hr_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "changes.json"
            app = App(DATA, path)
            good = self.employee(employee_id="EXISTING", skills={"SK_API_DESIGN": 1})
            app.add_profile(good, [])
            previous = path.read_bytes()
            bad = self.employee(employee_id="BROKEN", skills={"SK_API_DESIGN": 1})
            history = [{"record_id": "BAD_1", "employee_id": "BROKEN", "event_id": "EV_005", "date": "2026-09-20", "status": "completed", "completion_pct": "100"},
                       {"record_id": "BAD_2", "employee_id": "BROKEN", "event_id": "EV_005", "date": "2026-09-21", "status": "invalid"}]
            with self.assertRaises(ValueError):
                app.add_profile(bad, history)
            self.assertEqual(path.read_bytes(), previous)
            self.assertNotIn("BROKEN", app.dataset.employees)
            self.assertEqual(app.overview()["employee_count"], len(app.dataset.employees))
            self.assertEqual(App(DATA, path).overview()["employee_count"], len(app.dataset.employees))

    def test_import_duplicate_record_id_and_completed_repeat(self):
        base = self.employee(skills={"SK_API_DESIGN": 1})
        row = {"record_id": "DUP", "employee_id": "JUDGE_1", "event_id": "EV_005", "date": "2026-09-20", "status": "no_show"}
        with self.assertRaises(ValueError):
            self.dataset.add_profile(base, [row, row])
        completed = row | {"status": "completed", "completion_pct": "100"}
        with self.assertRaises(ValueError):
            self.dataset.add_profile(base, [completed, completed | {"record_id": "OTHER"}])
        self.dataset.add_profile(base, [row, row | {"record_id": "SECOND", "date": "2026-09-21"}])
        self.assertEqual(len(self.dataset.participation("JUDGE_1")["missed"]), 2)

    def test_in_progress_completion_transitions_and_stays_unrecommended(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "changes.json"
            app = App(DATA, path)
            employee = self.employee(skills={"SK_SYSTEM_DESIGN": 2, "SK_API_DESIGN": 2})
            active = {"record_id": "ACTIVE", "employee_id": "JUDGE_1", "event_id": "EV_005", "date": "2026-09-20", "status": "in_progress", "completion_pct": "50"}
            app.add_profile(employee, [active])
            self.assertNotIn("EV_005", [x["event_id"] for x in app.dataset.candidates("JUDGE_1")])
            result = app.complete("JUDGE_1", "EV_005")
            self.assertEqual(result["record"]["record_id"], "ACTIVE")
            self.assertEqual(result["record"]["status"], "completed")
            self.assertEqual(result["trajectory"]["current_skills"]["SK_API_DESIGN"], 3)
            restored = App(DATA, path)
            self.assertEqual(len(restored.dataset.participation("JUDGE_1")["completed"]), 1)
            self.assertEqual(len(restored.dataset.participation("JUDGE_1")["in_progress"]), 0)
            self.assertNotIn("EV_005", [x["event_id"] for x in restored.dataset.candidates("JUDGE_1")])

    def test_existing_dataset_in_progress_can_complete(self):
        active = next(row for row in self.dataset.history if row["status"] == "in_progress" and
                      not any(other["employee_id"] == row["employee_id"] and other["event_id"] == row["event_id"] and
                              other["status"] == "completed" for other in self.dataset.history))
        employee_id, event_id = active["employee_id"], active["event_id"]
        self.assertNotIn(event_id, [item["event_id"] for item in self.dataset.candidates(employee_id)])
        result = self.dataset.complete(employee_id, event_id)
        self.assertEqual(result["record"]["record_id"], active["record_id"])
        self.assertEqual(active["status"], "completed")
        self.assertNotIn(event_id, [item["event_id"] for item in self.dataset.candidates(employee_id)])

    def test_http_smoke_and_failed_import_hr(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            app = App(DATA, Path(tmp) / "changes.json")
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(app))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f"http://127.0.0.1:{server.server_port}"

            def request(path, body=None):
                payload = None if body is None else json.dumps(body).encode()
                with urlopen(Request(base + path, data=payload, headers={"Content-Type": "application/json"}), timeout=5) as response:
                    return response.status, json.load(response)

            try:
                employee = self.employee(skills={"SK_SYSTEM_DESIGN": 2, "SK_API_DESIGN": 2})
                self.assertEqual(request("/api/profiles", {"employee": employee})[0], 201)
                self.assertEqual(request("/api/employees/JUDGE_1/profile")[0], 200)
                rec = request("/api/employees/JUDGE_1/recommendations")[1]
                self.assertEqual(rec["source"], "deterministic")
                self.assertEqual(request("/api/activity/simulate", {"employee_id": "JUDGE_1", "event_id": "EV_005"})[0], 200)
                self.assertEqual(request("/api/activity/complete", {"employee_id": "JUDGE_1", "event_id": "EV_005"})[0], 200)
                bad = self.employee(employee_id="BROKEN")
                with self.assertRaises(HTTPError) as error:
                    request("/api/profiles", {"employee": bad, "history": [{"record_id": "BAD", "employee_id": "BROKEN", "event_id": "EV_005", "date": "2026-09-20", "status": "unknown"}]})
                self.assertEqual(error.exception.code, 400)
                self.assertEqual(request("/api/hr/overview")[1]["employee_count"], 201)
            finally:
                server.shutdown()
                server.server_close()

    def test_completion_gain_cap_and_recommendation_refresh(self):
        self.dataset.add_profile(self.employee(skills={"SK_SYSTEM_DESIGN": 2, "SK_API_DESIGN": 2}))
        before = self.dataset.trajectory("JUDGE_1")
        result = self.dataset.complete("JUDGE_1", "EV_005")
        self.assertEqual(result["trajectory"]["current_skills"]["SK_SYSTEM_DESIGN"], 3)
        self.assertEqual(result["trajectory"]["current_skills"]["SK_API_DESIGN"], 3)
        self.assertGreater(result["trajectory"]["readiness_pct"], before["readiness_pct"])
        self.assertNotIn("EV_005", [x["event_id"] for x in self.dataset.candidates("JUDGE_1")])

    def test_simulation_does_not_mutate_state(self):
        self.dataset.add_profile(self.employee(skills={"SK_SYSTEM_DESIGN": 1, "SK_API_DESIGN": 2}))
        before = deepcopy(self.dataset.current_skills("JUDGE_1"))
        count = len(self.dataset.history)
        result = self.dataset.simulate("JUDGE_1", "EV_005")
        self.assertNotEqual(result["before"]["readiness_pct"], result["after"]["readiness_pct"])
        self.assertEqual(self.dataset.current_skills("JUDGE_1"), before)
        self.assertEqual(len(self.dataset.history), count)

    def test_persistent_completion_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "changes.json"
            app = App(DATA, path)
            app.add_profile(self.employee(skills={"SK_SYSTEM_DESIGN": 1, "SK_API_DESIGN": 2}), [])
            app.complete("JUDGE_1", "EV_005")
            restored = App(DATA, path)
            self.assertEqual(restored.dataset.current_skills("JUDGE_1")["SK_API_DESIGN"], 3)


if __name__ == "__main__":
    unittest.main()
