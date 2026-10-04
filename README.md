# ProjectBridge

Turn student ideas into teams that can actually build them.

**Author:** Pinjia Lu  
**License:** [MIT](LICENSE)

This repository implements [ProjectBridge_SPEC.md](ProjectBridge_SPEC.md). It includes a fixture-first React flow for creating a project, reviewing requirements, editing fictional profiles, choosing a team, and drafting/saving a roadmap with task progress.

## Current status

- React + TypeScript + Vite project-to-roadmap flow: project creation, requirement review, profile editing, team selection and suggestions, evidence explanations, roadmap drafts, and task status updates.
- FastAPI health, anonymous session, profile, project, requirement-confirmation, matching, suggestion, and team-save endpoints.
- SQLite-backed demo workspaces with hashed session tokens, expiry, reset, revision checks, and per-session queries.
- Validated requirements and fictional profile domain types.
- Deterministic expert/collaborative coverage, critical gain, candidate scoring, greedy suggestions, and Missing Piece.
- Frozen collaboration score: availability `.45`, role preference `.30`, work style `.25`, combined as `C` inside GeneralScore.
- Exact-input CS Club requirement fixture; arbitrary ideas stay in manual-review mode instead of receiving a misleading fixture.
- Evidence-grounded explanation templates and editable roadmap drafts; no external AI provider calls are implemented.
- Roadmap owner, skill, weekly-capacity, replacement, revision, stale-state, and task-progress checks.
- AI remains in fixture mode. No provider is called.

## Run locally

Backend (Python 3.11+):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -e ".[test]"
uvicorn app.main:app --app-dir backend --reload
```

Frontend (Node.js):

```powershell
cd frontend
npm ci
npm run dev
```

The frontend expects the backend at `http://127.0.0.1:8000`. API docs are available at `/docs` while the backend is running. Use “CS Club example” on the project form to load the deterministic fixture path; other ideas receive clearly labeled editable starter requirements.

## API endpoints

- `GET /health`
- `POST /api/v1/demo/session` starts or resumes the isolated fictional workspace.
- `DELETE /api/v1/demo/session` resets only that workspace.
- `GET /api/v1/demo`, `GET /api/v1/profiles`, `PATCH /api/v1/profiles/{id}`
- `GET|POST /api/v1/projects`, `GET|PATCH /api/v1/projects/{id}`
- `PUT /api/v1/projects/{id}/requirements` explicitly confirms founder-reviewed requirements.
- `GET /api/v1/projects/{id}/matches`, `POST /api/v1/projects/{id}/team/suggestion`
- `PUT /api/v1/projects/{id}/team`, `GET /api/v1/projects/{id}/missing-piece`
- `POST /api/v1/projects/{id}/analysis`, `/explanation`, `/roadmap/draft`
- `PUT|GET /api/v1/projects/{id}/roadmap`, `PATCH /api/v1/tasks/{id}`

All profiles are fictional. Compatibility uses capped reported availability, a symmetric lead/flexible/support table, and shared known communication/structure preferences. Unknown work-style dimensions are excluded; no shared known dimensions use a neutral `.75`; an empty team uses availability alone. Scores are transparent heuristics out of 100 or `[0,1]` as labeled, not probabilities or predictions of collaboration success.

## Validation status

Pytest coverage lives under `tests/`; see [docs/TESTING.md](docs/TESTING.md) for the latest recorded results, visual checks, and remaining gaps. Run `python -m pytest -q`. From `frontend/`, run `npm run build` and `npm run test:e2e` (uses installed Chrome and disposable local SQLite data). The browser suite covers the fixture workflow, 390px layouts, keyboard activation, and API failure/retry. Other mobile widths, cross-browser behavior, hosted deployment, and live-AI integration remain unverified; live-AI integration is not implemented.

## Demo and release notes

The reproducible local walkthrough is in [docs/DEMO.md](docs/DEMO.md); a time-coded video narration is in [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md). [docs/AI_USE.md](docs/AI_USE.md) records the development and in-product AI boundary, and [docs/THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md) lists third-party resources and observed licenses. The public source repository is [lup49488/ProjectBridge](https://github.com/lup49488/ProjectBridge). No hosted demo is currently available.

## Scope

No student enrollment, real profiles, messaging, authentication, live model calls, deployment, or submission is included. See the specification for the complete MVP acceptance boundary.
