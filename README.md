# Career Quest

Career Quest is Rumba's HackAlem AI concept for Halyk Bank.

## Executive Summary

- **Problem:** Employees see HR events in isolation and cannot tell how learning, assessments, rotations, and other activities affect career growth.
- **Solution:** A career profile connects grade requirements, skill gaps, participation history, and relevant activities into a clear next step.
- **Target User:** Primarily employees with 1–5 years of tenure; HR is the secondary user.
- **Why AI:** A multi-factor decision layer can rank suitable activities and explain their relevance in context.
- **Expected Value:** More actionable development plans for employees and better visibility into career support for HR.

## Problem

Scattered HR events make it difficult for employees to see which activities matter for their next grade or how completed activities change their progress.

## Users

- **Employee:** Reviews their current grade, skills, career trajectory, gaps, and recommended actions.
- **HR:** Reviews employee development and activity participation through a separate role-based view.

## Core Workflow

Employee profile → current grade and skills → next-grade requirements → skill gaps → participation history → 1–3 recommended activities → explanation using at least three factors → activity completion → updated skills and progress → new recommendation.

## Recommendation Logic

Recommendations should consider **current grade**, **next-grade requirements**, **skill gaps**, **participation history**, and **event effects**. The deterministic runtime is intended to calculate factual gaps and activity effects, including `gain` and `max_level`, while AI proposes or reranks activities. A deterministic verifier then checks that each proposal is eligible and consistent with those facts. Explanations should cite at least three relevant factors.

## Why This Is Not a Chatbot Wrapper

The intended flow is:

`Profile + History + Requirements → Deterministic Feature Engine → AI Recommendation → Verification → Career Progress Update`

**Model proposes, runtime verifies.** AI is a multi-factor decision layer; the runtime owns calculations and validation.

## Architecture

The proposed architecture has a web frontend, employee and HR views, a deterministic career/skill engine, an AI recommendation layer, and a deterministic verifier. Progress is recalculated after an activity is completed. These are design targets, not claims of completed functionality.

## Data

The challenge dataset is described as `employees.json` (200 employees), `events.json` (40 events), `skills.json` (60 skills), and `activity_history.csv` (24 months of activity history). This describes the challenge inputs; it does not imply that every dataset file is already committed here.

## HackAlem Must-Have Requirements

- Employee profile and career trajectory
- 1–3 AI recommendations
- Recommendation explanation using multiple factors
- Progress update after activity completion
- HR view
- Support for uploading an additional profile

## Evaluation Strategy

A key judge trap is recommending an activity solely because it improves the employee's lowest skill. Evaluation should test whether recommendations also reflect **next-grade criticality** and **participation history**, and whether verified event effects produce a credible progress update and subsequent recommendation.

## Privacy and Roles

Employee and HR access should be separated. Individual employee development data should not be exposed through a public employee leaderboard.

## Planned Technical Direction

- Modular monolith
- Deterministic career/skill engine
- Fast OpenAI model for semantic recommendation or reranking
- Structured outputs
- Deterministic verifier
- Web frontend

The specific model and libraries have not been selected here.

## Running Locally

Run instructions will be updated as implementation lands.

## Team

Rumba — 2 participants.
