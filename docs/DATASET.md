# Career Quest dataset (v1.0)

Source: `data/` contains the real files from `career_quest_dataset.zip` (the `case_1/career_quest_dataset/` entries), including the English, Russian and Kazakh starter README. Apple `._*` metadata was excluded. The data is synthetic. Its snapshot date is **2026-10-01**; history covers 2024-10-01 through 2026-09-30.

| File | Shape and actual fields |
| --- | --- |
| `skills.json` | `meta`, `proficiency_scale` (0–5), `skills[]` (`skill_id`, `name`, `type`, `category`, `description`), `role_profiles[]` (`role`, `grade`, `required_skills`, `critical_skills`) |
| `employees.json` | `meta`, `employees[]`: `employee_id`, `full_name`, `department`, `role`, `grade`, `manager_id`, `hire_date`, `tenure_months`, `work_format`, `preferred_language`, `career_goal`, `skills`, `last_review_date` |
| `events.json` | `meta`, `events[]`: `event_id`, `title`, `description`, `type`, `format`, `duration_hours`, `mandatory`, `target_roles`, `target_grades`, `develops_skills`, `prerequisites`, `upcoming_sessions` |
| `activity_history.csv` | `record_id`, `employee_id`, `event_id`, `date`, `due_date`, `status`, `completion_pct`, `score`, `feedback_rating`, `assigned_by` |

Relations: employee `skills`, role profile `required_skills` and `critical_skills`, event `develops_skills` and `prerequisites` all reference `skills.skill_id`. `(role, grade)` selects a role profile. History joins employees and events by ID; `manager_id` joins employees. Missing employee skill means level 0.

Grades are `Junior → Middle → Senior → Lead`. Each role and grade has minimum levels in `required_skills`; `critical_skills` must meet their minimum for promotion. Requirements do not decrease across grades. A `career_goal` can name another target role and grade, but the next-grade trajectory uses the employee's current role and next grade.

Event eligibility requires the current role and grade in `target_roles` and `target_grades`, and every `prerequisites` level met. `self_paced` events are always available; scheduled events list `upcoming_sessions`. Mandatory events are HR assignments, not recommendation targets. Each `develops_skills` item has `skill_id`, `gain`, `max_level`; completion applies `min(current + gain, max_level)`. Empty effects occur for compliance training.

One history row is one participation. Statuses: `completed` (finished), `in_progress`, `dropped` (started then abandoned), `no_show` (registered but absent), `declined` (refused manager/HR assignment), `overdue` (mandatory event overdue). `completion_pct` is 0–100; `score` and `feedback_rating` are optional; `assigned_by` is `self`, `manager`, or `hr`. `dropped` and `no_show` are missed activities. Completed events are not repeated, except recurring `EV_036`. Skill levels in an employee profile are from `last_review_date`; completions after that date are not yet included and must be applied when loading state. New profiles and history rows use these same schemas.
