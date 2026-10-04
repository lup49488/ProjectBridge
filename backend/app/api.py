"""Session-isolated project, profile, requirements, and team APIs."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4, uuid5

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import ValidationError

from .database import connect, transaction
from .domain import ProjectContext, ProjectRequirements, StudentProfile, model_payload
from .drafts import analyze_requirements, build_explanation, build_roadmap_draft, is_cs_club_example
from .fixtures import CS_CLUB_REQUIREMENTS, DEMO_PROFILES
from .matching import FORMULA_VERSION, rank_candidates
from .schemas import (AnalysisRequest, ExplanationRequest, ProfilePatch, ProjectCreate, ProjectPatch,
                      RequirementConfirmation, RoadmapDraftRequest, RoadmapInput, RoadmapSaveRequest, TaskStatusUpdate,
                      TeamSuggestionRequest, TeamUpdate)

router = APIRouter(prefix="/api/v1")
SESSION_COOKIE = "pb_demo_session"
SESSION_LIFETIME = timedelta(hours=24)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _scoped_fixture_id(session_id: str, fixture_id: str) -> str:
    """Stable opaque profile ID unique to this demo workspace."""
    return str(uuid5(UUID(session_id), fixture_id))


def _stale(message: str = "The project or team changed. Refresh and try again.") -> HTTPException:
    return HTTPException(status_code=409, detail={"code": "STALE_INPUT", "message": message, "retryable": True})


def _read_session(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail={"code": "SESSION_REQUIRED", "message": "Start a demo session first."})
    now = _iso(_now())
    connection = connect()
    try:
        connection.execute("DELETE FROM demo_sessions WHERE expires_at <= ?", (now,))
        row = connection.execute(
            "SELECT id, profiles_revision, expires_at FROM demo_sessions WHERE token_hash = ? AND expires_at > ?",
            (_token_hash(token), now),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail={"code": "SESSION_EXPIRED", "message": "The demo session expired. Start a new one."})
        return dict(row)
    finally:
        connection.close()


def _profile_from_row(row) -> StudentProfile:
    work_style = json.loads(row["work_style_json"])
    payload = {"id": row["id"], "display_name": row["display_name"], "skills": json.loads(row["skills_json"]),
               "interests": json.loads(row["interests_json"]), "goals": json.loads(row["goals_json"]),
               "weekly_hours": row["weekly_hours"], "is_fictional": bool(row["is_fictional"]), "revision": row["revision"],
               **work_style}
    return StudentProfile.model_validate(payload)


def _profiles(connection, session_id: str) -> tuple[StudentProfile, ...]:
    rows = connection.execute("SELECT * FROM student_profiles WHERE session_id = ? ORDER BY id", (session_id,)).fetchall()
    return tuple(_profile_from_row(row) for row in rows)


def _project_row(connection, project_id: str, session_id: str):
    row = connection.execute("SELECT * FROM projects WHERE id = ? AND session_id = ?", (project_id, session_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Project not found."})
    return row


def _project_payload(connection, row) -> dict:
    team = connection.execute("SELECT id, revision FROM teams WHERE project_id = ? AND session_id = ?", (row["id"], row["session_id"])).fetchone()
    members = connection.execute("SELECT student_id FROM team_members WHERE team_id = ? ORDER BY student_id", (team["id"],)).fetchall()
    requirements = json.loads(row["requirements_json"]) if row["requirements_json"] else None
    return {"id": row["id"], "title": row["title"], "idea": row["idea"], "desired_team_size": row["desired_team_size"],
            "idea_revision": row["idea_revision"], "requirements": requirements,
            "requirements_revision": row["requirements_revision"], "confirmed_idea_revision": row["confirmed_idea_revision"],
            "team_revision": team["revision"], "member_ids": [member["student_id"] for member in members],
            "created_at": row["created_at"], "updated_at": row["updated_at"]}


def _require_confirmed(row) -> ProjectRequirements:
    if row["requirements_json"] is None or row["confirmed_idea_revision"] != row["idea_revision"]:
        raise HTTPException(status_code=400, detail={"code": "REQUIREMENTS_NOT_CONFIRMED", "message": "Review and confirm current project requirements first."})
    return ProjectRequirements.model_validate_json(row["requirements_json"])


def _current_revisions(connection, row, session: dict) -> dict:
    team = connection.execute("SELECT revision FROM teams WHERE project_id = ? AND session_id = ?", (row["id"], session["id"])).fetchone()
    profile_revision = connection.execute("SELECT profiles_revision FROM demo_sessions WHERE id = ?", (session["id"],)).fetchone()
    if profile_revision is None:
        raise HTTPException(status_code=401, detail={"code": "SESSION_EXPIRED", "message": "The demo session expired."})
    return {"idea": row["idea_revision"], "requirements": row["requirements_revision"],
            "team": team["revision"], "profiles": profile_revision["profiles_revision"]}


def _check_revisions(connection, row, session: dict, supplied: dict) -> dict:
    current = _current_revisions(connection, row, session)
    if supplied != current:
        raise _stale()
    return current


@router.post("/demo/session")
def start_demo_session(request: Request, response: Response) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    now = _now()
    if token:
        connection = connect()
        try:
            row = connection.execute("SELECT id, profiles_revision, expires_at FROM demo_sessions WHERE token_hash = ? AND expires_at > ?",
                                     (_token_hash(token), _iso(now))).fetchone()
            if row:
                response.set_cookie(SESSION_COOKIE, token, max_age=int(SESSION_LIFETIME.total_seconds()), httponly=True,
                                    secure=request.url.scheme == "https", samesite="lax", path="/")
                return {"session_id": row["id"], "profiles_revision": row["profiles_revision"], "expires_at": row["expires_at"], "resumed": True}
        finally:
            connection.close()

    token = secrets.token_urlsafe(32)
    session_id = str(uuid4())
    created_at = _iso(now)
    expires_at = _iso(now + SESSION_LIFETIME)
    with transaction() as connection:
        connection.execute("INSERT INTO demo_sessions (id, token_hash, profiles_revision, created_at, expires_at) VALUES (?, ?, 1, ?, ?)",
                           (session_id, _token_hash(token), created_at, expires_at))
        for profile in DEMO_PROFILES:
            payload = model_payload(profile)
            work_style = {key: payload.pop(key) for key in ("role_preference", "communication", "structure")}
            connection.execute(
                """INSERT INTO student_profiles
                   (id, session_id, display_name, skills_json, interests_json, goals_json, work_style_json, weekly_hours, is_fictional, revision)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1)""",
                (_scoped_fixture_id(session_id, profile.id), session_id, profile.display_name,
                 json.dumps(payload["skills"], separators=(",", ":")), json.dumps(payload["interests"], separators=(",", ":")),
                 json.dumps(payload["goals"], separators=(",", ":")), json.dumps(work_style, separators=(",", ":")), profile.weekly_hours),
            )
    response.set_cookie(SESSION_COOKIE, token, max_age=int(SESSION_LIFETIME.total_seconds()), httponly=True,
                        secure=request.url.scheme == "https", samesite="lax", path="/")
    return {"session_id": session_id, "profiles_revision": 1, "expires_at": expires_at, "resumed": False}


@router.delete("/demo/session", status_code=204)
def reset_demo_session(request: Request, response: Response) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with transaction() as connection:
            connection.execute("DELETE FROM demo_sessions WHERE token_hash = ?", (_token_hash(token),))
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax", secure=request.url.scheme == "https")
    response.status_code = 204
    return response


@router.get("/demo")
def demo(request: Request) -> dict:
    session = _read_session(request)
    connection = connect()
    try:
        return {"project": {"id": "cs-club-demo", "desired_team_size": 4, "requirements": model_payload(CS_CLUB_REQUIREMENTS)},
                "profiles": [model_payload(profile) for profile in _profiles(connection, session["id"])],
                "fixture_label": "Demo fixture", "profiles_revision": session["profiles_revision"]}
    finally:
        connection.close()


@router.get("/demo/suggestion")
def demo_suggestion(request: Request, team: str = "alice") -> dict:
    session = _read_session(request)
    connection = connect()
    try:
        profiles = _profiles(connection, session["id"])
    finally:
        connection.close()
    project = ProjectContext(id="cs-club-demo", desired_team_size=4, requirements=CS_CLUB_REQUIREMENTS)
    aliases = {profile.id: _scoped_fixture_id(session["id"], profile.id) for profile in DEMO_PROFILES}
    aliases.update({value: value for value in aliases.values()})
    selected_ids = [aliases.get(part, part) for part in team.split(",") if part]
    valid_ids = {profile.id for profile in profiles}
    if len(selected_ids) != len(set(selected_ids)):
        raise HTTPException(status_code=422, detail={"code": "DUPLICATE_MEMBER", "message": "Team member IDs must be unique."})
    if len(selected_ids) > 4:
        raise HTTPException(status_code=422, detail={"code": "TEAM_AT_CAPACITY", "message": "The demo team can contain at most four profiles."})
    if set(selected_ids) - valid_ids:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "One or more profiles were not found."})
    result = rank_candidates(project, selected_ids, profiles)
    result["fixture_label"] = "Demo fixture"
    return result


@router.get("/profiles")
def list_profiles(request: Request) -> dict:
    session = _read_session(request)
    connection = connect()
    try:
        return {"profiles": [model_payload(profile) for profile in _profiles(connection, session["id"])],
                "profiles_revision": session["profiles_revision"]}
    finally:
        connection.close()


@router.patch("/profiles/{profile_id}")
def update_profile(profile_id: str, body: ProfilePatch, request: Request) -> dict:
    session = _read_session(request)
    with transaction() as connection:
        row = connection.execute("SELECT * FROM student_profiles WHERE id = ? AND session_id = ?", (profile_id, session["id"])).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Profile not found."})
        if row["revision"] != body.expected_revision:
            raise _stale("This profile changed. Refresh before saving.")
        current = _profile_from_row(row).model_dump(mode="json")
        values = body.model_dump(exclude={"expected_revision"}, exclude_unset=True)
        current.update(values)
        try:
            updated = StudentProfile.model_validate(current)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_PROFILE", "message": "Profile fields are invalid."}) from exc
        work_style = {key: getattr(updated, key) for key in ("role_preference", "communication", "structure")}
        connection.execute(
            """UPDATE student_profiles SET display_name = ?, skills_json = ?, interests_json = ?, goals_json = ?,
               work_style_json = ?, weekly_hours = ?, revision = revision + 1 WHERE id = ? AND session_id = ?""",
            (updated.display_name, json.dumps(updated.skills, separators=(",", ":")), json.dumps(updated.interests, separators=(",", ":")),
             json.dumps(updated.goals, separators=(",", ":")), json.dumps(work_style, separators=(",", ":")),
             updated.weekly_hours, profile_id, session["id"]),
        )
        connection.execute("UPDATE demo_sessions SET profiles_revision = profiles_revision + 1 WHERE id = ?", (session["id"],))
        saved = connection.execute("SELECT * FROM student_profiles WHERE id = ? AND session_id = ?", (profile_id, session["id"])).fetchone()
        revision = connection.execute("SELECT profiles_revision FROM demo_sessions WHERE id = ?", (session["id"],)).fetchone()[0]
        return {"profile": model_payload(_profile_from_row(saved)), "profiles_revision": revision}


@router.get("/projects")
def list_projects(request: Request) -> dict:
    session = _read_session(request)
    connection = connect()
    try:
        rows = connection.execute("SELECT * FROM projects WHERE session_id = ? ORDER BY created_at, id", (session["id"],)).fetchall()
        return {"projects": [_project_payload(connection, row) for row in rows]}
    finally:
        connection.close()


@router.post("/projects", status_code=201)
def create_project(body: ProjectCreate, request: Request) -> dict:
    session = _read_session(request)
    now = _iso(_now())
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute("SELECT * FROM projects WHERE session_id = ? AND client_request_id = ?",
                                      (session["id"], body.client_request_id)).fetchone()
        if existing:
            result = _project_payload(connection, existing)
            connection.commit()
            return {"project": result}
        project_id, team_id = str(uuid4()), str(uuid4())
        connection.execute(
            """INSERT INTO projects (id, session_id, client_request_id, title, idea, desired_team_size, idea_revision,
               requirements_revision, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, ?)""",
            (project_id, session["id"], body.client_request_id, body.title, body.idea, body.desired_team_size, now, now),
        )
        connection.execute("INSERT INTO teams (id, project_id, session_id, revision) VALUES (?, ?, ?, 1)", (team_id, project_id, session["id"]))
        row = _project_row(connection, project_id, session["id"])
        result = _project_payload(connection, row)
        connection.commit()
        return {"project": result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@router.get("/projects/{project_id}")
def get_project(project_id: str, request: Request) -> dict:
    session = _read_session(request)
    connection = connect()
    try:
        return {"project": _project_payload(connection, _project_row(connection, project_id, session["id"]))}
    finally:
        connection.close()


@router.patch("/projects/{project_id}")
def update_project(project_id: str, body: ProjectPatch, request: Request) -> dict:
    session = _read_session(request)
    with transaction() as connection:
        row = _project_row(connection, project_id, session["id"])
        if body.expected_idea_revision != row["idea_revision"]:
            raise _stale("The project idea changed. Refresh before saving.")
        values = body.model_dump(exclude={"expected_idea_revision"}, exclude_unset=True)
        if any(value is None for value in values.values()):
            raise HTTPException(status_code=422, detail={"code": "INVALID_PROJECT", "message": "Project fields cannot be null."})
        changes = {key: value for key, value in values.items() if value != row[key]}
        if "desired_team_size" in changes:
            team_size = connection.execute("SELECT count(*) FROM team_members WHERE team_id = (SELECT id FROM teams WHERE project_id = ?)",
                                           (project_id,)).fetchone()[0]
            if changes["desired_team_size"] < team_size:
                raise HTTPException(status_code=400, detail={"code": "MEMBERS_MUST_BE_REMOVED", "message": "Remove team members before reducing team size."})
        if changes:
            assignments = ", ".join(f"{key} = ?" for key in changes)
            connection.execute(f"UPDATE projects SET {assignments}, idea_revision = idea_revision + 1, confirmed_idea_revision = NULL, updated_at = ? WHERE id = ? AND session_id = ?",
                               (*changes.values(), _iso(_now()), project_id, session["id"]))
            row = _project_row(connection, project_id, session["id"])
        return {"project": _project_payload(connection, row)}


@router.put("/projects/{project_id}/requirements")
def confirm_requirements(project_id: str, body: RequirementConfirmation, request: Request) -> dict:
    session = _read_session(request)
    with transaction() as connection:
        row = _project_row(connection, project_id, session["id"])
        if body.expected_idea_revision != row["idea_revision"] or body.expected_requirements_revision != row["requirements_revision"]:
            raise _stale("Project requirements changed. Refresh before confirming.")
        encoded = json.dumps(model_payload(body.requirements), separators=(",", ":"))
        connection.execute("UPDATE projects SET requirements_json = ?, requirements_source = 'manual', requirements_revision = requirements_revision + 1, confirmed_idea_revision = idea_revision, updated_at = ? WHERE id = ? AND session_id = ?",
                           (encoded, _iso(_now()), project_id, session["id"]))
        saved = _project_row(connection, project_id, session["id"])
        return {"project": _project_payload(connection, saved), "requirements_source": "manual"}


@router.post("/projects/{project_id}/analysis")
def analyze_project(project_id: str, body: AnalysisRequest, request: Request) -> dict:
    session = _read_session(request)
    connection = connect()
    try:
        connection.execute("BEGIN")
        row = _project_row(connection, project_id, session["id"])
        if row["idea_revision"] != body.expected_idea_revision:
            raise _stale("The project idea changed. Refresh before generating a draft.")
        data, generation, warnings = analyze_requirements(row["title"], row["idea"])
        return {"data": data, "generation": generation, "input_revisions": _current_revisions(connection, row, session), "warnings": warnings}
    finally:
        connection.close()


@router.post("/projects/{project_id}/explanation")
def explain_candidate(project_id: str, body: ExplanationRequest, request: Request) -> dict:
    session = _read_session(request)
    connection = connect()
    try:
        _, project, _, member_ids, profiles, revisions = _matching_snapshot(connection, project_id, session)
        _check_revisions(connection, _project_row(connection, project_id, session["id"]), session, body.input_revisions.model_dump())
        try:
            result = build_explanation(project, member_ids, profiles, body.candidate_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "CANDIDATE_NOT_ELIGIBLE", "message": str(exc)}) from exc
        return {**result, "input_revisions": revisions, "formula_version": FORMULA_VERSION}
    finally:
        connection.close()


def _matching_snapshot(connection, project_id: str, session: dict):
    if not connection.in_transaction:
        connection.execute("BEGIN")
    row = _project_row(connection, project_id, session["id"])
    requirements = _require_confirmed(row)
    context = ProjectContext(id=row["id"], desired_team_size=row["desired_team_size"], requirements=requirements)
    team_row = connection.execute("SELECT id, revision FROM teams WHERE project_id = ? AND session_id = ?", (project_id, session["id"])).fetchone()
    member_ids = [item[0] for item in connection.execute("SELECT student_id FROM team_members WHERE team_id = ? ORDER BY student_id", (team_row["id"],)).fetchall()]
    profile_pool = _profiles(connection, session["id"])
    revisions = _current_revisions(connection, row, session)
    return row, context, team_row, member_ids, profile_pool, revisions


@router.get("/projects/{project_id}/matches")
def get_matches(project_id: str, request: Request) -> dict:
    session = _read_session(request)
    connection = connect()
    try:
        _, project, _, member_ids, profiles, revisions = _matching_snapshot(connection, project_id, session)
        data = rank_candidates(project, member_ids, profiles)
        return {"data": data, "input_revisions": revisions, "formula_version": FORMULA_VERSION}
    finally:
        connection.close()


@router.post("/projects/{project_id}/team/suggestion")
def suggest_team(project_id: str, body: TeamSuggestionRequest, request: Request) -> dict:
    session = _read_session(request)
    connection = connect()
    try:
        _, project, _, member_ids, profiles, revisions = _matching_snapshot(connection, project_id, session)
        _check_revisions(connection, _project_row(connection, project_id, session["id"]), session, body.input_revisions.model_dump())
        if body.target_size is not None and body.target_size < len(member_ids):
            raise HTTPException(status_code=400, detail={"code": "TARGET_BELOW_CURRENT_TEAM", "message": "Target size is below the current team size."})
        data = rank_candidates(project, member_ids, profiles, target_size=body.target_size)
        return {"data": data, "input_revisions": revisions, "formula_version": FORMULA_VERSION}
    finally:
        connection.close()


@router.put("/projects/{project_id}/team")
def save_team(project_id: str, body: TeamUpdate, request: Request) -> dict:
    session = _read_session(request)
    with transaction() as connection:
        row, project, team_row, current_ids, profiles, revisions = _matching_snapshot(connection, project_id, session)
        _check_revisions(connection, row, session, body.input_revisions.model_dump())
        if len(body.member_ids) != len(set(body.member_ids)):
            raise HTTPException(status_code=422, detail={"code": "DUPLICATE_MEMBER", "message": "Team member IDs must be unique."})
        if len(body.member_ids) > project.desired_team_size:
            raise HTTPException(status_code=400, detail={"code": "TEAM_AT_CAPACITY", "message": "Team exceeds desired size."})
        profile_ids = {profile.id for profile in profiles}
        if set(body.member_ids) - profile_ids:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "One or more profiles were not found."})
        if set(current_ids) != set(body.member_ids):
            removed = set(current_ids) - set(body.member_ids)
            if removed:
                placeholders = ",".join("?" for _ in removed)
                connection.execute(
                    f"""UPDATE tasks SET owner_student_id = NULL WHERE owner_student_id IN ({placeholders})
                        AND milestone_id IN (SELECT m.id FROM milestones m JOIN roadmaps r ON r.id = m.roadmap_id WHERE r.project_id = ?)""",
                    (*sorted(removed), project_id),
                )
                if connection.execute("SELECT changes()").fetchone()[0]:
                    connection.execute("UPDATE roadmaps SET revision = revision + 1, updated_at = ? WHERE project_id = ?", (_iso(_now()), project_id))
            connection.execute("DELETE FROM team_members WHERE team_id = ? AND session_id = ?", (team_row["id"], session["id"]))
            connection.executemany("INSERT INTO team_members (team_id, session_id, student_id) VALUES (?, ?, ?)",
                                   [(team_row["id"], session["id"], profile_id) for profile_id in body.member_ids])
            connection.execute("UPDATE teams SET revision = revision + 1 WHERE id = ? AND session_id = ?", (team_row["id"], session["id"]))
            revisions = _current_revisions(connection, row, session)
        data = rank_candidates(project, body.member_ids, profiles)
        return {"project": _project_payload(connection, row), "data": data, "input_revisions": revisions,
                "warnings": {profile.id: (["weekly_hours_unknown_or_zero"] if profile.weekly_hours in (None, 0) else
                                           (["weekly_hours_below_minimum"] if profile.weekly_hours < project.requirements.weekly_hours_min else []))
                             for profile in profiles if profile.id in body.member_ids}}


@router.get("/projects/{project_id}/missing-piece")
def get_missing_piece(project_id: str, request: Request) -> dict:
    session = _read_session(request)
    connection = connect()
    try:
        _, project, _, member_ids, profiles, revisions = _matching_snapshot(connection, project_id, session)
        data = rank_candidates(project, member_ids, profiles)
        return {"data": data["missing_piece"], "input_revisions": revisions, "formula_version": FORMULA_VERSION}
    finally:
        connection.close()


def _roadmap_payload(connection, row, current_revisions: dict) -> dict:
    milestones = connection.execute("SELECT * FROM milestones WHERE roadmap_id = ? ORDER BY week", (row["id"],)).fetchall()
    result = []
    for milestone in milestones:
        tasks = connection.execute("SELECT * FROM tasks WHERE milestone_id = ? ORDER BY position", (milestone["id"],)).fetchall()
        result.append({"id": milestone["id"], "week": milestone["week"], "title": milestone["title"],
                       "objective": milestone["objective"], "tasks": [
                           {"id": task["id"], "position": task["position"], "title": task["title"],
                            "definition_of_done": task["definition_of_done"], "required_skill": task["required_skill"],
                            "required_level": task["required_level"], "owner_id": task["owner_student_id"],
                            "estimated_hours": task["estimated_hours"], "status": task["status"],
                            "acknowledged_skill_mismatch": bool(task["acknowledged_skill_mismatch"])} for task in tasks]})
    source_revisions = {"idea": row["source_idea_revision"], "requirements": row["source_requirements_revision"],
                        "team": row["source_team_revision"], "profiles": row["source_profiles_revision"]}
    return {"id": row["id"], "revision": row["revision"], "source": row["source"],
            "input_revisions": source_revisions, "assumptions": json.loads(row["assumptions_json"]),
            "milestones": result, "stale": source_revisions != current_revisions}


def _validate_roadmap_assignments(roadmap, project: ProjectContext, team: tuple[StudentProfile, ...]) -> list[dict]:
    team_by_id = {profile.id: profile for profile in team}
    requirements = {requirement.skill: requirement for requirement in project.requirements.skill_requirements}
    allocations: dict[tuple[str, int], float] = {}
    warnings = []
    for milestone in roadmap.milestones:
        for position, task in enumerate(milestone.tasks, start=1):
            if task.required_skill is not None:
                requirement = requirements.get(task.required_skill)
                if requirement is None:
                    raise HTTPException(status_code=422, detail={"code": "UNKNOWN_TASK_SKILL", "message": "Task skills must appear in confirmed project requirements."})
                target = requirement.required_level if requirement.aggregation == "expert" else requirement.target_capacity
                if task.required_level is None or task.required_level > target:
                    raise HTTPException(status_code=422, detail={"code": "TASK_LEVEL_EXCEEDS_REQUIREMENT", "message": "Task level exceeds the confirmed requirement."})
            if task.owner_id is None:
                warnings.append({"week": milestone.week, "position": position, "reason": "task_unassigned"})
                continue
            profile = team_by_id.get(task.owner_id)
            if profile is None:
                raise HTTPException(status_code=422, detail={"code": "OWNER_NOT_IN_TEAM", "message": "Task owners must be selected team members."})
            if profile.weekly_hours is None or profile.weekly_hours <= 0:
                raise HTTPException(status_code=422, detail={"code": "OWNER_HAS_NO_CAPACITY", "message": "A task owner must report positive weekly hours."})
            skill_level = profile.skills.get(task.required_skill, 0) if task.required_skill else 0
            if task.required_skill and skill_level < (task.required_level or 0):
                if not task.acknowledged_skill_mismatch:
                    raise HTTPException(status_code=422, detail={"code": "SKILL_MISMATCH_NOT_ACKNOWLEDGED", "message": "A below-level assignment requires an explicit learning-task acknowledgment."})
                warnings.append({"week": milestone.week, "position": position, "reason": "acknowledged_skill_mismatch"})
            key = (profile.id, milestone.week)
            allocated = allocations.get(key, 0.0) + task.estimated_hours
            if allocated > profile.weekly_hours:
                raise HTTPException(status_code=422, detail={"code": "WEEKLY_CAPACITY_EXCEEDED", "message": "Task assignments exceed a member's reported weekly hours."})
            allocations[key] = allocated
    return warnings


@router.post("/projects/{project_id}/roadmap/draft")
def draft_roadmap(project_id: str, body: RoadmapDraftRequest, request: Request) -> dict:
    session = _read_session(request)
    connection = connect()
    try:
        row, project, _, member_ids, profiles, revisions = _matching_snapshot(connection, project_id, session)
        _check_revisions(connection, row, session, body.input_revisions.model_dump())
        members = tuple(profile for profile in profiles if profile.id in set(member_ids))
        data, generation, warnings = build_roadmap_draft(project, row["title"], row["idea"], members)
        draft = RoadmapInput.model_validate(data)
        warnings.extend(_validate_roadmap_assignments(draft, project, members))
        return {"data": data, "generation": generation, "input_revisions": revisions, "warnings": warnings}
    finally:
        connection.close()


@router.put("/projects/{project_id}/roadmap")
def save_roadmap(project_id: str, body: RoadmapSaveRequest, request: Request) -> dict:
    session = _read_session(request)
    now = _iso(_now())
    with transaction() as connection:
        row, project, _, member_ids, profiles, revisions = _matching_snapshot(connection, project_id, session)
        _check_revisions(connection, row, session, body.input_revisions.model_dump())
        members = tuple(profile for profile in profiles if profile.id in set(member_ids))
        warnings = _validate_roadmap_assignments(body.roadmap, project, members)
        if body.source == "fixture" and not is_cs_club_example(row["title"], row["idea"]):
            raise HTTPException(status_code=422, detail={"code": "FIXTURE_SOURCE_MISMATCH", "message": "Fixture source is reserved for the exact CS Club example."})
        existing = connection.execute("SELECT * FROM roadmaps WHERE project_id = ?", (project_id,)).fetchone()
        if existing:
            if not body.confirm_replace:
                raise HTTPException(status_code=409, detail={"code": "ROADMAP_REPLACEMENT_CONFIRMATION_REQUIRED", "message": "Confirm that replacing this roadmap will replace its tasks and progress."})
            if body.expected_roadmap_revision != existing["revision"]:
                raise _stale("The saved roadmap changed. Refresh before replacing it.")
            roadmap_id, roadmap_revision = existing["id"], existing["revision"] + 1
            connection.execute("DELETE FROM milestones WHERE roadmap_id = ?", (roadmap_id,))
            connection.execute("""UPDATE roadmaps SET source = ?, source_idea_revision = ?, source_requirements_revision = ?,
                source_team_revision = ?, source_profiles_revision = ?, assumptions_json = ?, revision = ?, updated_at = ? WHERE id = ?""",
                (body.source, revisions["idea"], revisions["requirements"], revisions["team"], revisions["profiles"],
                 json.dumps(body.roadmap.assumptions), roadmap_revision, now, roadmap_id))
        else:
            if body.confirm_replace or body.expected_roadmap_revision is not None:
                raise HTTPException(status_code=409, detail={"code": "ROADMAP_NOT_FOUND", "message": "There is no saved roadmap to replace."})
            roadmap_id, roadmap_revision = str(uuid4()), 1
            connection.execute("""INSERT INTO roadmaps (id, project_id, source, source_idea_revision, source_requirements_revision,
                source_team_revision, source_profiles_revision, assumptions_json, revision, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (roadmap_id, project_id, body.source, revisions["idea"], revisions["requirements"], revisions["team"],
                 revisions["profiles"], json.dumps(body.roadmap.assumptions), now, now))
        for milestone in body.roadmap.milestones:
            milestone_id = str(uuid4())
            connection.execute("INSERT INTO milestones (id, roadmap_id, week, title, objective) VALUES (?, ?, ?, ?, ?)",
                               (milestone_id, roadmap_id, milestone.week, milestone.title, milestone.objective))
            for position, task in enumerate(milestone.tasks, start=1):
                connection.execute("""INSERT INTO tasks (id, milestone_id, position, title, definition_of_done, required_skill,
                    required_level, owner_student_id, estimated_hours, status, acknowledged_skill_mismatch)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'todo', ?)""",
                    (str(uuid4()), milestone_id, position, task.title, task.definition_of_done, task.required_skill,
                     task.required_level, task.owner_id, task.estimated_hours, int(task.acknowledged_skill_mismatch)))
        saved = connection.execute("SELECT * FROM roadmaps WHERE id = ?", (roadmap_id,)).fetchone()
        return {"data": _roadmap_payload(connection, saved, revisions), "warnings": warnings}


@router.get("/projects/{project_id}/roadmap")
def get_roadmap(project_id: str, request: Request) -> dict:
    session = _read_session(request)
    connection = connect()
    try:
        project = _project_row(connection, project_id, session["id"])
        revisions = _current_revisions(connection, project, session)
        roadmap = connection.execute("SELECT * FROM roadmaps WHERE project_id = ?", (project_id,)).fetchone()
        return {"data": _roadmap_payload(connection, roadmap, revisions) if roadmap else None,
                "warnings": ["No saved roadmap exists yet."] if roadmap is None else []}
    finally:
        connection.close()


@router.patch("/tasks/{task_id}")
def update_task_status(task_id: str, body: TaskStatusUpdate, request: Request) -> dict:
    session = _read_session(request)
    with transaction() as connection:
        row = connection.execute("""SELECT t.id, t.status, r.id AS roadmap_id, r.revision AS roadmap_revision
            FROM tasks t JOIN milestones m ON m.id = t.milestone_id JOIN roadmaps r ON r.id = m.roadmap_id
            JOIN projects p ON p.id = r.project_id WHERE t.id = ? AND p.session_id = ?""",
            (task_id, session["id"])).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Task not found."})
        if body.expected_roadmap_revision != row["roadmap_revision"]:
            raise _stale("The roadmap changed. Refresh before updating task status.")
        connection.execute("UPDATE tasks SET status = ? WHERE id = ?", (body.status, task_id))
        connection.execute("UPDATE roadmaps SET revision = revision + 1, updated_at = ? WHERE id = ?", (_iso(_now()), row["roadmap_id"]))
        updated_revision = connection.execute("SELECT revision FROM roadmaps WHERE id = ?", (row["roadmap_id"],)).fetchone()[0]
        return {"task_id": task_id, "status": body.status, "roadmap_revision": updated_revision}
