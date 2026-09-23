# Career Quest — Demo Scenario

## Goal

Show how Career Quest helps an employee understand a suitable next career step and why it is recommended.

## Demo User

Use a neutral example with no real personal data:

- Current role: Backend Engineer
- Current grade: Middle
- Target grade: Senior

## Demo Flow

### Step 1 — Employee Profile

Show the employee's current role and grade, skills, activity history, and requirements for the next grade.

### Step 2 — Skill Gaps

Compare current skills with next-grade requirements. Do not automatically recommend the employee's lowest skill; consider which gaps matter for the target grade.

### Step 3 — Recommendation

Offer 1–3 activities, considering current grade, next-grade requirements, skill gaps, participation history, and each activity's effect.

### Step 4 — Explanation

Explain why an activity was selected. For example, a demo explanation might show:

- System Design: current 2
- Senior requirement: 4
- Activity gain: +1
- This activity reduces a critical next-grade gap.
- Participation history was considered.

These values are illustrative demo examples, not claims about the dataset.

### Step 5 — What-If

Show the expected effect before completion:

**BEFORE** → current skill state → current grade readiness

**AFTER** → projected skill state → updated grade readiness

### Step 6 — Complete Activity

On completion, apply the dataset's `gain` and `max_level` rules, update employee state, recalculate the trajectory, and refresh recommendations.

### Step 7 — HR View

Show an aggregated overview of common skill gaps, activity participation, and employees without a useful next step. Do not use a public employee leaderboard.

## Why AI Is Needed

AI supports multi-factor recommendations and explanations. Deterministic runtime logic handles skill gaps, grade requirements, activity effects, `gain`/`max_level` rules, and validation.

**Model proposes, runtime verifies.**

## Judge Trap

**A recommendation must not be based on the lowest skill alone.** An employee may have the lowest Public Speaking score while System Design is more critical for the next grade; participation history may also show repeated skips of similar Public Speaking activities. Consider these factors together.

## Demo Success Criteria

The demo should show:

1. Employee profile
2. Career trajectory
3. 1–3 recommendations
4. Multi-factor explanation
5. Progress change after completion
6. HR overview

This document describes the intended demo flow based on the official HackAlem Career Quest challenge. It does not claim that every listed capability is already implemented.
