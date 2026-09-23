# Career Quest — HackAlem Challenge Mapping

## Project

Career Quest is a Halyk Bank employee development navigator. It connects an employee profile to next-grade requirements, skill gaps and participation history, then produces a multi-factor recommendation and explanation. Employees can preview and complete an activity to see an updated trajectory.

**Model proposes, runtime verifies.**

## Official Must-Have Mapping

| Requirement | Status | Implementation | Evidence |
| ----------- | ------ | -------------- | -------- |
| Employee profile | PASS | Profile includes assessed/effective skills and grouped activity history. | `career_quest/api.py` `App.profile`; `GET /api/employees/{employee_id}/profile` |
| Career trajectory | PASS | Calculates current and next grade, requirements, gaps and readiness. | `career_quest/engine.py` `Dataset.trajectory`; `GET /api/employees/{employee_id}/trajectory` |
| 1–3 recommended activities | PASS | Proposal verification enforces one to three unique eligible activities. | `career_quest/recommend.py` `verify_proposals`, `recommendations`; `GET /api/employees/{employee_id}/recommendations` |
| Multi-factor recommendation | PASS | Candidate score combines critical and ordinary gap closure, requirements helped, and participation history. | `career_quest/engine.py` `Dataset.candidates` |
| Grade consideration | PASS | Eligibility and recommendation evidence use the employee's current grade. | `career_quest/engine.py` `Dataset.eligible`, `Dataset.candidates` |
| Skill-gap consideration | PASS | Only activities that close a next-grade requirement gap become candidates. | `career_quest/engine.py` `Dataset.candidates` |
| Participation-history consideration | PASS | Similar completed, missed and declined activities affect candidate score and explanation. | `career_quest/engine.py` `Dataset.candidates`; `tests/test_engine.py` `test_three_similar_misses_affect_score_and_explanation` |
| Next-grade requirements | PASS | Requirements and critical skills come from the employee's role profile at the next grade. | `career_quest/engine.py` `Dataset.trajectory` |
| Recommendation explanation | PASS | Runtime builds explanations from verified evidence factors; at least three distinct supported factors are required. | `career_quest/recommend.py` `factor_evidence`, `verify_proposals` |
| Completion updates skills | PASS | Applies event `gain` subject to `max_level`, including completion of an in-progress activity. | `career_quest/engine.py` `apply_effects`, `Dataset.complete`; `tests/test_engine.py` `test_completion_gain_cap_and_recommendation_refresh` |
| Completion updates trajectory | PASS | Recalculates readiness and recommendations after completion. | `career_quest/api.py` `App.complete`; `tests/test_engine.py` `test_completion_gain_cap_and_recommendation_refresh` |
| HR skill-gap overview | PASS | HR endpoint aggregates common next-grade skill gaps. | `career_quest/api.py` `App.overview`; `GET /api/hr/overview` |
| Employees without next step | PASS | HR overview counts employees with no eligible candidate recommendation. | `career_quest/api.py` `App.overview`; `GET /api/hr/overview` |
| Activity participation statistics | PASS | HR overview reports participation and completions by activity. | `career_quest/api.py` `App.overview`; `GET /api/hr/overview` |
| Additional profile/history loading | PASS | New profiles and optional history are validated and accepted without judge-ID-specific logic. | `career_quest/engine.py` `Dataset.add_profile`; `POST /api/profiles`; `tests/test_engine.py` `test_new_profile_and_history_without_hardcoding` |
| No lowest-skill-only logic | PASS | Critical next-grade gaps can outrank a lower unrelated skill. | `career_quest/engine.py` `Dataset.candidates`; `tests/test_engine.py` `test_critical_gap_outweighs_lowest_unrelated_skill`, `test_unrelated_skill_does_not_rank_first` |
| No public employee leaderboard | PASS | HR endpoint returns aggregate metrics, not an employee ranking or list. | `career_quest/api.py` `App.overview`; `GET /api/hr/overview` |
| Employee/HR separation | PARTIAL | The UI has employee and HR views, but API requests have no authentication or role authorization. | `web/index.html`; `career_quest/api.py` `handler_for`; `docs/API.md` |
| UI latency ≤ 2 seconds | NOT VERIFIED | No end-to-end UI latency measurement is documented; local calculation timings do not establish this UI target. | `README.md` “Performance” |
| AI recommendation ≤ 10 seconds | PARTIAL | A request deadline, 8-second network timeout and deterministic fallback are implemented; live provider end-to-end latency is not verified. | `career_quest/recommend.py` `_model_proposals`, `recommendations`; `tests/test_engine.py` `test_slow_response_body_falls_back_within_deadline`; `README.md` “Limitations” |

## Judge Trap

**A recommendation must not be based on the lowest skill alone.** Candidate ranking considers next-grade criticality, gap closure, activity effect and participation history together. The tests confirm that a critical next-grade gap can outrank a lower unrelated skill and that similar missed activities affect ranking and explanation: `test_critical_gap_outweighs_lowest_unrelated_skill`, `test_three_similar_misses_affect_score_and_explanation`.

## Technical Differentiators

- Deterministic grade, gap, eligibility and activity calculations: `career_quest/engine.py`.
- Optional bounded AI reranking of prefiltered candidates, followed by evidence verification and deterministic fallback: `career_quest/recommend.py`.
- Dataset `gain`/`max_level` rules apply to projections and completions: `career_quest/engine.py` `apply_effects`.
- What-if simulation returns before/after state without mutation: `Dataset.simulate`; `test_simulation_does_not_mutate_state`.
- Completion state is persisted and restored by the API: `career_quest/api.py` `App.save`; `test_persistent_completion_reload`.

## Known Limitations

- The local demo has no production authentication or employee/HR role authorization.
- Trajectory follows the employee's current role; cross-role `career_goal` planning is not calculated.
- Live AI provider behavior and end-to-end latency are not verified here.
- The ≤2-second UI target has no documented end-to-end measurement.

## Reproducibility

- Run instructions: `README.md` — “Run Locally” (`python -m career_quest.api`).
- Tests: `tests/` (`python -m unittest discover -s tests -v`).
- API contracts: `docs/API.md`.
- Intended demo flow: `docs/DEMO.md`.
