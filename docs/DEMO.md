# Local demo walkthrough

This walkthrough uses fictional demo profiles. The current application is fixture/template based and does not call an external AI provider.

## Start the app

In one PowerShell window, from the repository root:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -e ".[test]"
uvicorn app.main:app --app-dir backend --reload
```

In another PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL printed in the terminal (normally `http://localhost:5173`). The frontend's local API target defaults to `http://127.0.0.1:8000`.

## Walk through the fictional project

1. Select **Start a project**, then **Use CS Club example**.
2. Review the requirements and explicitly confirm them.
3. Inspect fictional profiles and candidate explanations, then choose or request a team suggestion.
4. Review the Missing Piece and team coverage.
5. Generate an editable roadmap draft and save it.
6. Change a task status, refresh the page, and verify the status persists.
7. Change the team and review the stale-plan warning. Drafting a replacement does not replace the saved roadmap until the explicit confirmation action.

Generic ideas use editable starter requirements and remain in manual review. Matching is deterministic; scores are transparent heuristics, not probabilities. See [README.md](../README.md) for endpoints and [TESTING.md](TESTING.md) for the checks actually run.
