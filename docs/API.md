# Career Quest API v1

Run `python -m career_quest.api` from the repository root. Default origin is `http://127.0.0.1:8000`. JSON is UTF-8. The dataset snapshot date (2026-10-01) is used for event availability and new completion records. Responses are deterministic except optional OpenAI reranking. Contracts below are stable for the web client.

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/health` | status and snapshot date |
| GET | `/api/employees/{employee_id}/profile` | employee fields, effective `current_skills`, participation grouped into `completed`, `missed`, `declined`, `in_progress` |
| GET | `/api/employees/{employee_id}/trajectory` | grade, next grade, requirements, skill and critical gaps, readiness percentage, promotion critical-skill flag |
| GET | `/api/employees/{employee_id}/recommendations` | `source`, `candidate_count`, 1–3 verified recommendations; each includes structured effects, history, projected readiness, factors and explanation |
| POST | `/api/activity/simulate` | `{ "employee_id": "E0001", "event_id": "EV_005" }` → before/after trajectory and skill changes, without mutation |
| POST | `/api/activity/complete` | same body → completion record, updated trajectory, simulation and recalculated recommendations |
| POST | `/api/profiles` | `{ "employee": { ...employees.json entry... }, "history": [ ...CSV-shaped records... ] }` → stored new profile |
| GET | `/api/hr/overview` | grade counts, common skill gaps, employee count without recommendation, average skill levels and participation/completion by activity; no employee leaderboard |
| POST | `/api/workflows` | `{ "employee_id": "E0005", "goal": {"type":"NEXT_GRADE_READINESS"}, "horizon": 3 }` → persisted verified workflow; one active workflow per employee |
| GET | `/api/workflows/{id}` | canonical state, observed and forecast readiness, typed nodes, observations, replan diff and append-only factual trace |
| POST | `/api/workflows/{id}/commands` | `{ "action":"confirm_completion", "confirmed":true, "event_id":"EV_007" }` or `{ "action":"replan" }` → updated workflow |

Unknown IDs return 404; invalid body or ineligible events return 400. `POST /api/profiles` requires a new ID, a known role/grade, valid skill IDs and levels, and history references to known events. Mutations are saved atomically to `state/changes.json`, which is excluded from Git. Completion rejects events already completed (except recurring `EV_036`) and in-progress events.

The local demo API has no authentication. It should be placed behind employee/HR authorization before use with real HR data. The committed challenge dataset contains synthetic people only.

Workflow `confirm_completion` accepts only the current activity while `WAITING_USER` and requires literal `confirmed: true`. It persists domain completion and workflow trace in the same atomic state file. The existing `/api/activity/complete` endpoint also observes an alternative activity for an active workflow and replans stale future steps. Workflow states are `PLANNING`, `VERIFYING`, `WAITING_USER`, `EXECUTING`, `CHECKING`, `NEEDS_REPLAN`, `BLOCKED` and `DONE`; transitions are recorded with `PLAN`, `VERIFY`, `READY`, `EXECUTE`, `OBSERVE`, `CHECK`, `REASSESS`, `NEXT`, `REPLAN`, `DONE` and `BLOCKED` facts. Future nodes are tentative and the next activity is revalidated against committed employee state. Grade is never advanced automatically.
