> This FAQ describes the local Career Quest demo. See [DEMO.md](DEMO.md) for the verified flow and limitations.

# Career Quest FAQ

## What problem does Career Quest solve?

Employees receive fragmented HR activities without understanding how those activities connect to their career growth.

## Who is the product for?

Primary users are employees with 1–5 years of tenure.

Secondary users are HR specialists and managers.

## What does Career Quest recommend?

Career Quest recommends 1–3 relevant development activities based on:

- current grade;
- next-grade requirements;
- skill gaps;
- participation history;
- event effects.

## Why not simply recommend the employee's lowest skill?

The lowest skill may not be critical for reaching the next grade. Participation history may also show that the employee regularly skips similar activities.

The recommendation is therefore multi-factor.

## Where is AI used?

Optional AI reranks eligible candidates and selects supported explanation factors. Runtime verification checks the proposal and builds explanations from verified facts. Without AI, or if the call/verification fails, deterministic recommendations remain available. The UI labels the returned source explicitly.

Deterministic logic calculates facts and constraints.

## What is verified outside the LLM?

- employee and profile facts;
- skill levels;
- next-grade requirements;
- event existence;
- gain;
- `max_level`;
- eligibility;
- progress after completion.

## Can AI invent activities or skills?

Recommendations must reference valid dataset entities. The implemented runtime verifier rejects unsupported IDs and facts; rejected AI proposals fall back to deterministic recommendations.

## What happens after an activity is completed?

The server applies the event `gain`/`max_level` rules, saves completion, and recalculates the trajectory and recommendations. The UI displays the confirmed before/after skills, readiness change in percentage points, remaining gaps and next step. This result stays on the current page until the employee changes; a full browser reload clears the result block but retains saved server progress. Simulation previews the server-calculated effect without saving it.

## What data does the challenge provide?

- 200 employee profiles;
- 40 events;
- 60 skills;
- 24 months of activity history.

Files:

- `employees.json`;
- `events.json`;
- `skills.json`;
- `activity_history.csv`.

## Does the solution support new employees?

The web upload and `POST /api/profiles` accept additional profiles and optional history in the provided schema. A successful upload opens the new employee. Recommendations use the same API flow for every employee ID.

## What does HR see?

- common skill gaps;
- employees without a recommended next step;
- participation by activity.

There is no public performance leaderboard.

## How is privacy handled?

The included dataset is synthetic. The HR screen shows aggregates, but the local demo has no authentication or employee/HR authorization: anyone with API access can request an employee by ID. Production access controls are required before connecting real personnel data.

## Why is this not a chatbot?

The core system operates on structured employee state, requirements, event effects, and history to produce and verify an actionable career trajectory.

## What are the latency targets?

- UI response: ≤ 2 seconds;
- AI recommendation: ≤ 10 seconds.

## What is the main technical principle?

“Model proposes, runtime verifies.”

## What will be demonstrated?

Employee: profile → gaps → recommendation → explanation → activity completion → updated trajectory.

HR: aggregated competency and participation view.
