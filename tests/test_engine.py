import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from career_quest.api import App
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
        skills["SK_PUBLIC_SPEAKING"] = 0
        self.dataset.add_profile(self.employee(skills=skills))
        picks = self.dataset.candidates("JUDGE_1")
        self.assertTrue(picks)
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
