# Career Quest — Technical Pitch

## 15-second Product Summary

Career Quest turns employee development from a list of HR activities into an explainable path toward the next career grade.

It combines employee skills, next-grade requirements, participation history and activity effects to recommend and execute useful development steps.

## Core Problem

Employees receive training, mentorship, assessment and rotation opportunities, but often do not understand:

- which activity matters now;
- why it matters;
- how it affects career progression;
- what should happen next.

## Core Product Flow

```text
Employee State
→ Grade Requirements
→ Skill Gaps
→ Candidate Activities
→ AI Decision
→ Runtime Verification
→ User-Confirmed Action
→ Observed State
→ Updated Career Path
```

## Why This Is Not a Chatbot

Career Quest does not rely on free-form conversation as its primary interface. The system works with structured employee state and executable actions.

The language model may propose a plan. The runtime owns canonical facts, state changes and verification.

Key principle:

- Model proposes.
- Runtime verifies.
- Runtime executes user-confirmed actions.
- Observations update state.
- The plan adapts.

## AI Role

When enabled, AI provides bounded semantic decision-making:

- selecting relevant development activities from eligible candidates;
- combining multiple evidence factors;
- ordering possible next steps;
- selecting evidence factors for explainable recommendations.

The runtime constructs explanations from verified evidence. AI does not directly:

- change employee skills;
- invent activities;
- mark activities completed;
- calculate canonical progress;
- own application state.

Without an API key, or when a proposal fails verification or times out, the deterministic planner uses the same verification path.

## Deterministic Runtime

The runtime verifies:

- employee state;
- grade requirements;
- activity eligibility;
- skill gaps;
- `gain` / `max_level` rules;
- activity effects;
- valid identifiers;
- completion results.

## Career Workflow Runtime

The implemented workflow compiles the supported `NEXT_GRADE_READINESS` goal into a typed plan of up to three activities.

Example:

```text
Goal: Middle Backend Engineer → Senior readiness

PLAN
→ VERIFY
→ ACTIVITY
→ USER CONFIRMATION
→ EXECUTE
→ OBSERVE
→ CHECK
→ REASSESS
→ NEXT / REPLAN
```

Future steps are tentative. After each confirmed activity, the runtime reads the updated state, records an observation and revalidates the remaining plan. If the previous plan is no longer useful, the remaining workflow is rebuilt.

## Why Replanning Matters

A static recommendation list assumes the future will match the original prediction. Career Quest treats future steps as provisional.

Example:

```text
Original plan:
Activity A → Activity B → Activity C

Another valid activity is completed:
OBSERVE
→ state changed
→ a future step may no longer be useful
→ mark the future path DIRTY
→ REPLAN
```

Completed work is preserved. Only the future path changes.

## Human Control

Automatic:

- inspect state;
- calculate gaps;
- plan;
- simulate;
- verify;
- replan.

User-confirmed:

- activity completion and other actions that mutate employee progress.

The system does not pretend to complete training on behalf of the employee.

## Business Value

For employees:

- understand what to do next;
- understand why;
- see expected impact;
- see progress toward the next grade.

For HR:

- identify common competency gaps;
- understand participation;
- identify employees without useful next steps.

## Demo Story

1. Open employee profile.
2. Show current and target grade.
3. Show critical skill gaps.
4. Generate a recommendation and workflow.
5. Show structured WHY evidence.
6. Show projected progress.
7. Confirm an activity.
8. Runtime observes actual state.
9. Demonstrate replanning when the future plan becomes stale.
10. Show updated trajectory and HR view.

## One-line Technical Differentiator

Career Quest is an explainable career decision system where AI proposes actions but a deterministic runtime owns state, verifies effects and adapts the workflow after real observations.

This document is a presentation aid. The repository implementation and README remain the source of truth for implemented capabilities.
