# AI use disclosure

This note separates AI use during development from AI behavior in the submitted application. It is intended to support the Devpost disclosure; confirm the final wording against the submission form before submitting.

## Submission-ready draft

> **Development:** OpenAI Codex was used as an AI coding assistant to help implement and revise parts of the application, investigate and fix issues, prepare and run tests, review the interface, and draft project documentation. Pinjia Lu is the sole listed team member and is responsible for the submitted project and its final decisions. The exact Codex model/build is not recorded in this repository; do not claim a specific model version unless you verify it in the Codex client.
>
> **In the application:** ProjectBridge does not call an external generative AI model or AI API. It uses a predefined CS Club example and editable templates. Team matching, scores, coverage, candidate explanations, and roadmap drafts are produced by deterministic application logic. Scores are heuristics, not predictions. Profile and example project data are fictional.

## Verified implementation boundary

- No external model/provider request is implemented in the current app.
- The exact CS Club example may load predefined requirements and a roadmap template. Other ideas receive editable starter requirements for human review.
- Candidate matching, team coverage, Missing Piece, explanations, and roadmap templates are produced by deterministic Python code.
- Requirement changes require explicit confirmation; a team or roadmap is saved only after the user chooses the save action.
- All bundled demo profiles and example data are fictional. Do not enter real student data in a public demo.

## Before submitting

- Verify that the development-tools description reflects all tools actually used by the team. The repository cannot establish activity outside this project history.
- If the form asks for an exact model name or version, check the Codex client and enter only a verified value; otherwise name OpenAI Codex without guessing a model version.
- Be prepared to explain the implementation, deterministic scoring, and the parts assisted by Codex.
- Update this disclosure if any live provider, model, or additional AI-generated asset is added.
