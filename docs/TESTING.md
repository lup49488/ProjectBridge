# Testing and visual review

Last verified: October 2, 2026, on Windows with Python 3.12, installed Chrome, and Playwright.

## Results

| Check | Command / method | Result |
|---|---|---|
| Backend unit and API suite | `python -m pytest -q` | 17 passed in 0.55 seconds; one Starlette/httpx deprecation warning |
| Frontend type check and production bundle | `cd frontend; npm run build` | Passed with Vite 8.3.1 |
| Browser end-to-end and responsive checks | `cd frontend; npm run test:e2e` | 3 passed using Chrome and disposable SQLite data |
| Visual review | Playwright screenshots at desktop and 390px mobile | Reviewed; candidate explanation now expands beside its profile, and mobile candidate actions fit without horizontal overflow |

## Browser coverage

- Create the CS Club fixture project, review requirements, add a profile, save the team, draft and save a roadmap, update a task, and reload to verify persistence.
- Check no horizontal overflow at 390px for the landing, requirements, Team Builder, and saved roadmap. Review screenshots for the home page and full-page project flows.
- Open a candidate's **Why?** explanation, verify it appears within that candidate row, then collapse it; verify no unrelated top-of-page notice appears.
- Navigate the primary project flow with Tab and Enter; verify visible focus styling.
- Simulate a profiles API 503; verify an announced error and successful Retry recovery.
- Capture browser page errors and console errors during the main saved-project flow. The missing favicon that surfaced as a browser 404 was fixed with a local SVG favicon; the rerun passed.

The visual review found that the mobile hero artwork crossed the primary action and the roadmap objective text clipped on one line. The hero spacing was adjusted and roadmap objectives now wrap in a two-line editable field. Both were visually checked after the changes.

Screenshots and Playwright traces are generated outside the repository. They are evidence for this local review, not committed release assets.

## Browser smoke evidence from an earlier session

The previous manual Chrome smoke run covered the end-to-end fixture scenario, team-change stale-plan warning, replacement confirmation, and task reset on confirmed replacement. That is retained as historical evidence; this turn reran the automated browser suite, not the full manual scenario.

## Remaining checks

- Other mobile widths, keyboard-only completion of every path, and non-Chrome browsers.
- Live model/provider calls (not implemented), hosted persistence, deployment configuration, and public URL checks.
- Final public screenshots/video must be captured from the release candidate and checked against its actual behavior.

No deployment or submission was performed.
