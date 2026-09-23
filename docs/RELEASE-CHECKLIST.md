# Career Quest — Release Checklist

## Core Product

- [ ] Employee profile loads
- [ ] Current and next grade are visible
- [ ] Skill gaps are visible
- [ ] 1–3 recommendations are returned
- [ ] Recommendation uses multiple factors
- [ ] Participation history influences recommendation
- [ ] Lowest-skill-only trap is avoided
- [ ] Recommendation evidence is visible

## AI

- [ ] OpenAI recommendation path works when an API key is present
- [ ] Runtime verifies model output
- [ ] Invalid or slow AI falls back to deterministic ranking
- [ ] Deterministic mode works without an API key
- [ ] API key is never committed

## Workflow

- [ ] What-if simulation does not mutate state
- [ ] Completion updates skills
- [ ] Completion updates career trajectory
- [ ] Next recommendation recalculates
- [ ] In-progress activity can be completed correctly

## Judge Profiles

- [ ] Arbitrary employee profile can be imported
- [ ] History can be validated
- [ ] Failed import does not corrupt state
- [ ] Recommendation logic does not hardcode employee IDs

## HR

- [ ] Common skill gaps are available
- [ ] Participation statistics are available
- [ ] Employees without a useful next step are represented
- [ ] No public employee leaderboard is shown

## Frontend

- [ ] Profile remains available while recommendations are slow
- [ ] Switching employees cannot show stale responses
- [ ] Simulation result is clearly marked as a prediction
- [ ] Completion result shows before and after
- [ ] Mobile layout remains usable

## Demo Scenario

Use a verified profile only while its current API response still supports the intended comparison. The current demo guide uses E0005; confirm it against the live profile, trajectory and recommendations before presenting, or choose an equivalent current profile. See `docs/DEMO.md` for the baseline and the effect of saved local state.

Expected sequence:

1. Open the employee profile.
2. Show the target grade.
3. Compare the weakest skill with a critical next-grade gap.
4. Show the recommendation.
5. Show why it was recommended and its evidence.
6. Run What-If.
7. Complete the activity.
8. Show updated progress.
9. Show the next recommendation.
10. Open the HR view.

## Before Submission

Run these commands from the repository root (Python 3.10+):

```powershell
# Unit tests
python -m unittest discover -s tests -v

# Python compile check
python -m compileall -q career_quest

# Start the application
python -m career_quest.api
```

- [ ] `git status` is clean
- [ ] Tests are green
- [ ] README launch command works
- [ ] No secrets are present in the repository
- [ ] Demo flow has been verified
- [ ] Latest commits have been pushed
- [ ] No force-push is required

This checklist is an operational release aid and does not claim functionality beyond the current implementation.
