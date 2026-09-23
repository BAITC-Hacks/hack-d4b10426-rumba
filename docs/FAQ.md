> This FAQ documents the intended Career Quest behavior based on the official HackAlem challenge. Implementation status may evolve during the hackathon.

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

AI is used for multi-factor semantic recommendation, reranking, and explanation.

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

No. Recommendations must reference valid dataset entities. A planned verifier rejects unsupported IDs and facts; this is a design requirement if the verifier is not yet implemented.

## What happens after an activity is completed?

Skill progress should be updated using the event `gain`/`max_level` rules, and the trajectory and recommendations should be recalculated.

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

The challenge requires loading additional profiles and history in the provided schema. The solution must not use hardcoded judge-profile logic.

## What does HR see?

- common skill gaps;
- employees without a recommended next step;
- participation by activity.

There is no public performance leaderboard.

## How is privacy handled?

Employee engagement and history are not exposed to other employees. Employee and HR roles are separated.

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
