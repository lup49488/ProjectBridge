from fastapi.testclient import TestClient

from app.drafts import CS_CLUB_EXAMPLE_IDEA, CS_CLUB_EXAMPLE_TITLE


def _confirmed_project(client, project):
    demo = client.get("/api/v1/demo").json()
    response = client.put(f"/api/v1/projects/{project['id']}/requirements", json={
        "expected_idea_revision": project["idea_revision"],
        "expected_requirements_revision": project["requirements_revision"],
        "requirements": demo["project"]["requirements"],
    })
    assert response.status_code == 200, response.text
    return response.json()["project"]


def _input_revisions(client, project):
    profile_revision = client.get("/api/v1/profiles").json()["profiles_revision"]
    return {"idea": project["idea_revision"], "requirements": project["requirements_revision"],
            "team": project["team_revision"], "profiles": profile_revision}


def test_sessions_are_isolated_and_foreign_ids_are_not_found(session_client):
    first = session_client.get("/api/v1/profiles").json()["profiles"]
    first_alice = next(profile for profile in first if profile["display_name"] == "Alice")
    first_project = session_client.post("/api/v1/projects", json={
        "client_request_id": "first", "title": "First project", "idea": "Build a small first project for the school club.", "desired_team_size": 3,
    }).json()["project"]

    with TestClient(session_client.app) as second_client:
        assert second_client.post("/api/v1/demo/session").status_code == 200
        second = second_client.get("/api/v1/profiles").json()["profiles"]
        second_alice = next(profile for profile in second if profile["display_name"] == "Alice")
        assert second_alice["id"] != first_alice["id"]
        assert second_client.get(f"/api/v1/projects/{first_project['id']}").status_code == 404
        foreign_profile = second_client.patch(f"/api/v1/profiles/{first_alice['id']}", json={
            "expected_revision": 1, "display_name": "Changed",
        })
        assert foreign_profile.status_code == 404


def test_profile_edits_advance_the_workspace_revision_and_reject_stale_writes(session_client):
    profile = next(item for item in session_client.get("/api/v1/profiles").json()["profiles"]
                   if item["display_name"] == "Alice")

    updated = session_client.patch(f"/api/v1/profiles/{profile['id']}", json={
        "expected_revision": profile["revision"],
        "weekly_hours": 4,
        "role_preference": "support",
        "communication": "async",
        "structure": "flexible",
    })
    assert updated.status_code == 200, updated.text
    payload = updated.json()
    assert payload["profile"]["weekly_hours"] == 4
    assert payload["profile"]["role_preference"] == "support"
    assert payload["profile"]["revision"] == profile["revision"] + 1
    assert payload["profiles_revision"] == 2
    assert session_client.get("/api/v1/profiles").json()["profiles_revision"] == 2

    stale = session_client.patch(f"/api/v1/profiles/{profile['id']}", json={
        "expected_revision": profile["revision"], "weekly_hours": 3,
    })
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "STALE_INPUT"


def test_analysis_is_a_non_mutating_pending_fixture_and_nonmatching_ideas_fall_back(session_client, canonical_project):
    result = session_client.post(f"/api/v1/projects/{canonical_project['id']}/analysis", json={"expected_idea_revision": 1})
    assert result.status_code == 200
    payload = result.json()
    assert payload["generation"] == {"source": "fixture", "status": "ok", "reason_code": "exact_cs_club_example"}
    draft_requirements = [item for role in payload["data"]["roles"] for item in role["skill_requirements"]]
    assert all("critical" not in item for item in draft_requirements)
    assert any(item["suggested_critical"] for item in draft_requirements)
    assert session_client.get(f"/api/v1/projects/{canonical_project['id']}").json()["project"]["requirements"] is None

    other = session_client.post("/api/v1/projects", json={
        "client_request_id": "other", "title": "Art showcase", "idea": "Create an online gallery for student art projects.", "desired_team_size": 3,
    }).json()["project"]
    fallback = session_client.post(f"/api/v1/projects/{other['id']}/analysis", json={"expected_idea_revision": 1}).json()
    assert fallback["data"] is None
    assert fallback["generation"]["status"] == "needs_input"
    assert "CS Club" in fallback["warnings"][0]


def test_core_ai_and_roadmap_flow_requires_review_and_detects_stale_input(session_client, canonical_project):
    blocked = session_client.get(f"/api/v1/projects/{canonical_project['id']}/matches")
    assert blocked.status_code == 400

    project = _confirmed_project(session_client, canonical_project)
    revisions = _input_revisions(session_client, project)
    suggestion = session_client.post(f"/api/v1/projects/{project['id']}/team/suggestion", json={"input_revisions": revisions})
    assert suggestion.status_code == 200
    assert suggestion.json()["data"]["steps"][0]["candidate"]["critical_gain"] > 0
    assert all(row["coverage"] == 0 for row in suggestion.json()["data"]["current_coverage"])
    assert suggestion.json()["data"]["current_missing_piece"]["skill"] == "python"
    assert session_client.get(f"/api/v1/projects/{project['id']}").json()["project"]["member_ids"] == []

    charlie = next(profile["id"] for profile in session_client.get("/api/v1/profiles").json()["profiles"] if profile["display_name"] == "Charlie")
    saved_team = session_client.put(f"/api/v1/projects/{project['id']}/team", json={"input_revisions": revisions, "member_ids": [charlie]})
    assert saved_team.status_code == 200, saved_team.text
    project = saved_team.json()["project"]
    revisions = saved_team.json()["input_revisions"]
    current_coverage = {row["skill"]: row["coverage"] for row in saved_team.json()["data"]["current_coverage"]}
    assert current_coverage["python"] == 1
    assert current_coverage["react"] < 1
    assert saved_team.json()["data"]["current_missing_piece"]["skill"] == "react"

    explanation = session_client.post(f"/api/v1/projects/{project['id']}/explanation", json={"input_revisions": revisions})
    assert explanation.status_code == 200
    assert explanation.json()["data"]["facts"]
    assert explanation.json()["generation"]["source"] == "template"

    draft_response = session_client.post(f"/api/v1/projects/{project['id']}/roadmap/draft", json={"input_revisions": revisions})
    assert draft_response.status_code == 200, draft_response.text
    draft = draft_response.json()
    assert draft["generation"]["source"] == "fixture"
    assert len(draft["data"]["milestones"]) == 4
    assert session_client.get(f"/api/v1/projects/{project['id']}/roadmap").json()["data"] is None

    saved = session_client.put(f"/api/v1/projects/{project['id']}/roadmap", json={
        "input_revisions": revisions, "source": "fixture", "roadmap": draft["data"],
    })
    assert saved.status_code == 200, saved.text
    roadmap = saved.json()["data"]
    task_id = roadmap["milestones"][0]["tasks"][0]["id"]

    denied_replace = session_client.put(f"/api/v1/projects/{project['id']}/roadmap", json={
        "input_revisions": revisions, "source": "fixture", "roadmap": draft["data"],
    })
    assert denied_replace.status_code == 409
    assert denied_replace.json()["detail"]["code"] == "ROADMAP_REPLACEMENT_CONFIRMATION_REQUIRED"

    changed = session_client.patch(f"/api/v1/profiles/{charlie}", json={"expected_revision": 1, "weekly_hours": 2})
    assert changed.status_code == 200
    stale_explanation = session_client.post(f"/api/v1/projects/{project['id']}/explanation", json={"input_revisions": revisions})
    assert stale_explanation.status_code == 409
    assert session_client.get(f"/api/v1/projects/{project['id']}/roadmap").json()["data"]["stale"] is True

    task_update = session_client.patch(f"/api/v1/tasks/{task_id}", json={"expected_roadmap_revision": roadmap["revision"], "status": "done"})
    assert task_update.status_code == 200, task_update.text
    assert task_update.json()["status"] == "done"


def test_requirement_confirmation_requires_explicit_critical_flags(session_client, canonical_project):
    requirements = session_client.get("/api/v1/demo").json()["project"]["requirements"]
    del requirements["skill_requirements"][0]["critical"]
    result = session_client.put(f"/api/v1/projects/{canonical_project['id']}/requirements", json={
        "expected_idea_revision": 1, "expected_requirements_revision": 0, "requirements": requirements,
    })
    assert result.status_code == 422


def test_roadmap_save_checks_team_membership_skill_acknowledgment_and_capacity(session_client, canonical_project):
    project = _confirmed_project(session_client, canonical_project)
    revisions = _input_revisions(session_client, project)
    charlie = next(profile["id"] for profile in session_client.get("/api/v1/profiles").json()["profiles"] if profile["display_name"] == "Charlie")
    team = session_client.put(f"/api/v1/projects/{project['id']}/team", json={"input_revisions": revisions, "member_ids": [charlie]})
    project = team.json()["project"]
    revisions = team.json()["input_revisions"]
    base_task = {"title": "Build a task", "definition_of_done": "The task output is reviewed.",
                 "required_skill": "react", "required_level": 3, "owner_id": charlie, "estimated_hours": 1}
    roadmap = {"milestones": [{"week": 1, "title": "Build", "objective": "Complete the first task.", "tasks": [base_task]}]}

    mismatch = session_client.put(f"/api/v1/projects/{project['id']}/roadmap", json={
        "input_revisions": revisions, "source": "manual", "roadmap": roadmap,
    })
    assert mismatch.status_code == 422
    assert mismatch.json()["detail"]["code"] == "SKILL_MISMATCH_NOT_ACKNOWLEDGED"

    task_acknowledged = {**base_task, "acknowledged_skill_mismatch": True}
    too_much = {"milestones": [{"week": 1, "title": "Build", "objective": "Complete the first task.",
                                 "tasks": [{**task_acknowledged, "estimated_hours": 2}, {**task_acknowledged, "estimated_hours": 2}]}]}
    over_capacity = session_client.put(f"/api/v1/projects/{project['id']}/roadmap", json={
        "input_revisions": revisions, "source": "manual", "roadmap": too_much,
    })
    assert over_capacity.status_code == 422
    assert over_capacity.json()["detail"]["code"] == "WEEKLY_CAPACITY_EXCEEDED"

    accepted = session_client.put(f"/api/v1/projects/{project['id']}/roadmap", json={
        "input_revisions": revisions, "source": "manual",
        "roadmap": {"milestones": [{"week": 1, "title": "Build", "objective": "Complete the first task.", "tasks": [task_acknowledged]}]},
    })
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["warnings"][0]["reason"] == "acknowledged_skill_mismatch"


def test_state_changing_browser_requests_enforce_configured_origin(client):
    response = client.post("/api/v1/demo/session", headers={"Origin": "https://attacker.example"})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ORIGIN_NOT_ALLOWED"
