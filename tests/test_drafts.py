import pytest
from pydantic import ValidationError

from app.drafts import (
    CS_CLUB_EXAMPLE_IDEA, CS_CLUB_EXAMPLE_TITLE, RequirementDraft,
    analyze_requirements, build_roadmap_draft,
)
from app.domain import ProjectContext
from app.fixtures import CS_CLUB_REQUIREMENTS, DEMO_PROFILES
from app.schemas import RoadmapInput


def test_canonical_analyzer_fixture_is_exact_and_keeps_criticality_pending():
    data, generation, warnings = analyze_requirements(CS_CLUB_EXAMPLE_TITLE, f"  {CS_CLUB_EXAMPLE_IDEA}  ")

    assert generation["source"] == "fixture"
    assert generation["status"] == "ok"
    assert warnings == []
    draft = RequirementDraft.model_validate(data)
    skills = [item for role in draft.roles for item in role.skill_requirements]
    assert any(item.suggested_critical for item in skills)
    assert all(not hasattr(item, "critical") for item in skills)


def test_analyzer_does_not_apply_canonical_fixture_to_arbitrary_text():
    data, generation, warnings = analyze_requirements("Art showcase", "Build a place where students can display artwork.")

    assert data is None
    assert generation["status"] == "needs_input"
    assert generation["reason_code"] == "manual_requirements_required"
    assert warnings


def test_roadmap_draft_is_bounded_and_assigns_only_qualified_members():
    project = ProjectContext(id="project-id", desired_team_size=4, requirements=CS_CLUB_REQUIREMENTS)
    members = tuple(profile for profile in DEMO_PROFILES if profile.id == "charlie")

    data, generation, warnings = build_roadmap_draft(project, CS_CLUB_EXAMPLE_TITLE, CS_CLUB_EXAMPLE_IDEA, members)
    roadmap = RoadmapInput.model_validate(data)
    tasks = [task for milestone in roadmap.milestones for task in milestone.tasks]

    assert generation["source"] == "fixture"
    assert len(roadmap.milestones) == 4
    assert len(tasks) <= 12
    assert all(task.owner_id is None or task.owner_id in {member.id for member in members} for task in tasks)
    assert warnings  # React work remains unassigned for this Python-focused member.


def test_requirement_drafts_reject_noncanonical_skills_and_unconfirmed_critical_fields():
    data, _, _ = analyze_requirements(CS_CLUB_EXAMPLE_TITLE, CS_CLUB_EXAMPLE_IDEA)
    skill = data["roles"][0]["skill_requirements"][0]
    skill["skill"] = "cosmic_telepathy"

    with pytest.raises(ValidationError):
        RequirementDraft.model_validate(data)
    skill["skill"] = "react"
    skill["critical"] = True
    with pytest.raises(ValidationError):
        RequirementDraft.model_validate(data)
