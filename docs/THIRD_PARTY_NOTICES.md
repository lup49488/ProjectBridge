# Third-party resources and notices

This inventory is based on the source tree, Python project metadata, and the current frontend lockfile. It describes the current local release candidate; it is not a substitute for checking the exact files included in the eventual public repository or distribution.

## Project assets and references

- **Code, UI, fixture profiles, and example content:** ProjectBridge-authored project materials. The demo profiles and CS Club scenario are fictional.
- **External APIs, datasets, copied templates, and third-party images/icons:** None are used by the current application.
- **Fonts:** Stylesheets name common font families with system fallbacks; no font files are vendored and no remote font service is loaded.
- **Conceptual background:** The specification cites the UCLA Department of Psychology article [“Highlighting Faculty Member Matthew Lieberman”](https://www.psych.ucla.edu/news/highlighting-faculty-member-matthew-lieberman/) as broad background for the idea of compatibility in teams. ProjectBridge does not use UCLA or Resonance code, data, or algorithm, and neither UCLA nor Resonance endorses this project. ProjectBridge's matching rules and score formula are its own documented heuristics.

## Direct software dependencies

| Package | Use | License observed |
|---|---|---|
| FastAPI | Python API framework | MIT |
| Pydantic | Request and domain validation | MIT |
| Uvicorn | Python ASGI server | BSD-3-Clause |
| React, React DOM | Browser UI runtime | MIT |
| Vite, `@vitejs/plugin-react` | Frontend development and build | MIT |
| TypeScript | Type checking and compilation | Apache-2.0 |
| Playwright, `@playwright/test` | Browser end-to-end testing | Apache-2.0 |
| `@types/react`, `@types/react-dom` | Type declarations | MIT |

Python dependency versions are declared as ranges in `pyproject.toml`, rather than fixed in a Python lockfile. Frontend package versions and transitive dependencies are recorded in `frontend/package-lock.json`.

## Notable transitive build dependency

The current frontend lockfile includes `lightningcss` and `lightningcss-win32-x64-msvc` under MPL-2.0. These are build-tool dependencies, not application runtime packages. Keep their license terms with those packages if redistributing their source or binaries; do not represent the whole application as overriding their separate license. The current public-repository plan should include the package lockfile and this notice, and should not commit `node_modules/` or generated build output.

## Public source package checks

- Preserve each dependency's own license and notices; ProjectBridge's MIT license applies to this project's code and accompanying files only.
- Include `frontend/package-lock.json`, `pyproject.toml`, and this notice file in the source repository.
- Exclude installed packages, build output, test output, local databases, environment files, and machine-specific data.
- Re-run the license inventory if dependencies change or a distributable bundle is added.
