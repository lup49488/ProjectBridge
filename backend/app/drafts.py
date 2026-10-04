"""Deterministic, fixture/template draft providers; no external model calls."""

from __future__ import annotations

import hashlib
import math
import re

from pydantic import Field, model_validator

from .domain import GoalId, InterestId, ProjectContext, ProjectRequirements, SkillId, SkillRequirement, StudentProfile, StrictModel
from .fixtures import CS_CLUB_REQUIREMENTS
from .matching import rank_candidates
from .schemas import MilestoneInput, RoadmapInput, RoadmapTaskInput

CS_CLUB_EXAMPLE_TITLE = "CS Club website"
CS_CLUB_EXAMPLE_IDEA = (
    "I want to start a CS club and build a website where students can see meetings and projects. "
    "Club organizers need to edit the event list through a small content API. "
    "We can spend about three hours per person each week."
)


class DraftSkillRequirement(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    skill: SkillId
    aggregation: str
    required_level: int | None = Field(default=None, ge=1, le=4)
    target_capacity: float | None = Field(default=None, gt=0, le=16)
    importance: float = Field(gt=0, le=1)
    suggested_critical: bool
    critical_reason: str = Field(max_length=200)

    @model_validator(mode="after")
    def validate_target(self) -> "DraftSkillRequirement":
        if not math.isfinite(self.importance) or (self.target_capacity is not None and not math.isfinite(self.target_capacity)):
            raise ValueError("requirement values must be finite")
        if self.aggregation == "expert":
            if self.required_level is None or self.target_capacity is not None:
                raise ValueError("expert draft requirement has an invalid target")
        elif self.aggregation == "collaborative":
            if self.target_capacity is None or self.required_level is not None:
                raise ValueError("collaborative draft requirement has an invalid target")
        else:
            raise ValueError("unknown aggregation")
        return self


class DraftRole(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=100)
    priority: float = Field(gt=0, le=1)
    skill_requirements: tuple[DraftSkillRequirement, ...] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def validate_priority(self) -> "DraftRole":
        if not math.isfinite(self.priority):
            raise ValueError("role priority must be finite")
        return self


class RequirementDraft(StrictModel):
    schema_version: str = Field(default="1.1", pattern="^1\\.1$")
    summary: str = Field(min_length=1, max_length=300)
    roles: tuple[DraftRole, ...] = Field(min_length=1, max_length=4)
    interests: tuple[InterestId, ...] = ()
    goals: tuple[GoalId, ...] = ()
    weekly_hours_min: int = Field(ge=1, le=10)
    assumptions: tuple[str, ...] = Field(default=(), max_length=3)
    questions: tuple[str, ...] = Field(default=(), max_length=3)

    @model_validator(mode="after")
    def validate_draft(self) -> "RequirementDraft":
        if len({role.id for role in self.roles}) != len(self.roles):
            raise ValueError("role IDs must be unique")
        requirements = [item for role in self.roles for item in role.skill_requirements]
        if len({item.id for item in requirements}) != len(requirements):
            raise ValueError("requirement IDs must be unique")
        if len({item.skill for item in requirements}) != len(requirements):
            raise ValueError("skill IDs must be unique")
        if any(len(text) > 200 for text in (*self.assumptions, *self.questions)):
            raise ValueError("assumptions and questions must be at most 200 characters")
        return self


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def is_cs_club_example(title: str, idea: str) -> bool:
    expected = f"{_normalize(CS_CLUB_EXAMPLE_TITLE).casefold()}\n{_normalize(CS_CLUB_EXAMPLE_IDEA)}"
    supplied = f"{_normalize(title).casefold()}\n{_normalize(idea)}"
    return hashlib.sha256(supplied.encode("utf-8")).digest() == hashlib.sha256(expected.encode("utf-8")).digest()


def _canonical_requirement_draft() -> RequirementDraft:
    role_definitions = (
        ("frontend", "Frontend Developer", .4, "No release-blocking frontend threshold was stated."),
        ("backend", "Backend Developer", .3, "The idea explicitly requires an editable content API."),
        ("design", "UI Designer", .2, "The idea does not make this release-blocking."),
        ("coordination", "Project Coordinator", .1, "Coordination can be shared by the team."),
    )
    roles = []
    for (role_id, label, priority, reason), requirement in zip(role_definitions, CS_CLUB_REQUIREMENTS.skill_requirements):
        roles.append(DraftRole(id=role_id, label=label, priority=priority, skill_requirements=(DraftSkillRequirement(
            id=requirement.id, skill=requirement.skill, aggregation=requirement.aggregation,
            required_level=requirement.required_level, target_capacity=requirement.target_capacity,
            importance=requirement.importance, suggested_critical=requirement.critical, critical_reason=reason),)))
    return RequirementDraft(
        summary="A CS Club website with meeting details, project pages, and an editable event list backed by a small API.",
        roles=tuple(roles), interests=CS_CLUB_REQUIREMENTS.interests, goals=CS_CLUB_REQUIREMENTS.goals,
        weekly_hours_min=CS_CLUB_REQUIREMENTS.weekly_hours_min,
        assumptions=("The editable event list requires a small backend API.",), questions=(),
    )


def analyze_requirements(title: str, idea: str) -> tuple[dict | None, dict, list[str]]:
    if not is_cs_club_example(title, idea):
        return None, {"source": "template", "status": "needs_input", "reason_code": "manual_requirements_required"}, [
            "This idea does not match the CS Club demo fixture. Add requirements manually; no fixture was substituted."]
    draft = _canonical_requirement_draft()
    return draft.model_dump(mode="json"), {"source": "fixture", "status": "ok", "reason_code": "exact_cs_club_example"}, []


def build_explanation(project: ProjectContext, team_ids: list[str], profiles: tuple[StudentProfile, ...], candidate_id: str | None) -> dict:
    result = rank_candidates(project, team_ids, profiles)
    if not result["steps"]:
        return {"data": None, "generation": {"source": "template", "status": "needs_input", "reason_code": "no_candidate_to_explain"},
                "warnings": ["Add an available candidate or reduce team size before requesting an explanation."]}
    evaluations = result["steps"][0]["considered"]
    selected_id = candidate_id or result["steps"][0]["candidate"]["profile_id"]
    evidence = next((entry for entry in evaluations if entry["profile_id"] == selected_id), None)
    if evidence is None:
        raise ValueError("candidate is not an automatically eligible candidate for this team")
    candidate = next(profile for profile in profiles if profile.id == selected_id)
    components = evidence["compatibility_components"]
    facts = [
        {"id": "marginal_contribution", "value": evidence["marginal_contribution"], "text": f"Adds {evidence['marginal_contribution']:.3f} weighted skill coverage to this team."},
        {"id": "critical_gain", "value": evidence["critical_gain"], "text": f"Critical deficit improves by {evidence['critical_gain']:.3f}."},
        {"id": "general_score", "value": evidence["general_score"], "text": f"Contextual GeneralScore is {evidence['general_score']:.3f} (0 to 1)."},
        {"id": "availability", "value": components["availability"], "text": f"Availability alignment is {components['availability']:.3f} against {project.requirements.weekly_hours_min} hours per week."},
    ]
    if components["role"] is not None:
        facts.extend([
            {"id": "role_compatibility", "value": components["role"], "text": f"Average role preference alignment is {components['role']:.3f}."},
            {"id": "work_style_compatibility", "value": components["work_style"], "text": f"Average reported work-style alignment is {components['work_style']:.3f}."},
        ])
    warnings = list(evidence["warnings"])
    summary = f"{candidate.display_name} contributes to this project's current team score. Review the skill gain, availability, and collaboration evidence before choosing."
    return {"data": {"candidate_id": selected_id, "candidate_alias": candidate.display_name,
                      "selection_mode": result["steps"][0]["selection_mode"], "facts": facts, "warnings": warnings,
                      "summary": summary},
            "generation": {"source": "template", "status": "fallback", "reason_code": "deterministic_evidence_only"},
            "warnings": []}


def _canonical_roadmap() -> RoadmapInput:
    def task(title: str, done: str, skill: str | None = None, level: int | None = None, hours: float = 2):
        return RoadmapTaskInput(title=title, definition_of_done=done, required_skill=skill,
                                required_level=level, estimated_hours=hours)
    milestones = (
        MilestoneInput(week=1, title="Scope and wireframes", objective="Agree on the minimum club site and its content.", tasks=(
            task("Confirm the pages and event fields", "The team has an agreed page list and event field list.", hours=2),
            task("Draft the home page wireframe", "A wireframe shows the next meeting, project list, and navigation.", "ui_ux", 2, 2))),
        MilestoneInput(week=2, title="Frontend and content API", objective="Build the first usable pages and event endpoint.", tasks=(
            task("Build the meeting and project pages", "Both pages render the agreed club information.", "react", 3, 3),
            task("Implement the editable event API", "The API can list and update the event fixture.", "python", 3, 3))),
        MilestoneInput(week=3, title="Integration and content", objective="Connect the pages to the event data and review content.", tasks=(
            task("Connect the event list to the API", "The page displays events returned by the API.", "python", 3, 2),
            task("Review page content and accessibility", "The team records content edits and keyboard issues.", "ui_ux", 2, 2))),
        MilestoneInput(week=4, title="Testing and demo", objective="Fix the main issues and prepare a short walkthrough.", tasks=(
            task("Check the main pages and event flow", "The team records and resolves blocking demo defects.", "react", 2, 2),
            task("Prepare the club demo", "A short walkthrough covers meetings, projects, and editing an event.", hours=2))),
    )
    return RoadmapInput(milestones=milestones, assumptions=("This is an editable four-week starting plan for the CS Club example.",))


def _generic_roadmap(project: ProjectContext, title: str) -> RoadmapInput:
    requirements = project.requirements.skill_requirements
    phase_titles = ("Plan the first version", "Build the core", "Integrate and review", "Test and share")
    objectives = ("Agree on scope and a first deliverable.", "Implement the project's core requirements.",
                  "Connect the pieces and review remaining gaps.", "Test the result and prepare a demonstration.")
    milestones = []
    for week, (title, objective) in enumerate(zip(phase_titles, objectives), start=1):
        requirement = requirements[(week - 1) % len(requirements)]
        level = requirement.required_level if requirement.aggregation == "expert" else min(4, math.ceil(requirement.target_capacity or 1))
        milestones.append(MilestoneInput(week=week, title=title, objective=objective, tasks=(RoadmapTaskInput(
            title=f"Deliver {requirement.skill.replace('_', ' ')} work for {title[:48]}",
            definition_of_done=f"The team reviews and accepts a working contribution for the {requirement.skill.replace('_', ' ')} requirement.",
            required_skill=requirement.skill, required_level=level, estimated_hours=2),)))
    return RoadmapInput(milestones=tuple(milestones), assumptions=("Generated from confirmed requirements using an editable generic template.",))


def allocate_roadmap(roadmap: RoadmapInput, team: tuple[StudentProfile, ...]) -> tuple[RoadmapInput, list[dict]]:
    allocated: dict[tuple[str, int], float] = {}
    warnings = []
    milestones = []
    for milestone in roadmap.milestones:
        tasks = []
        for position, task in enumerate(milestone.tasks, start=1):
            qualified = []
            for profile in team:
                hours = profile.weekly_hours
                if hours is None or hours <= 0:
                    continue
                if task.required_skill is not None and profile.skills.get(task.required_skill, 0) < (task.required_level or 0):
                    continue
                used = allocated.get((profile.id, milestone.week), 0.0)
                if used + task.estimated_hours > hours:
                    continue
                qualified.append((used, profile.id, profile))
            qualified.sort(key=lambda item: (item[0], item[1]))
            owner = qualified[0][2] if qualified else None
            if owner:
                allocated[(owner.id, milestone.week)] = allocated.get((owner.id, milestone.week), 0.0) + task.estimated_hours
            else:
                warnings.append({"week": milestone.week, "position": position,
                                 "reason": "no_member_has_skill_and_weekly_capacity" if task.required_skill else "no_member_has_weekly_capacity"})
            tasks.append(task.model_copy(update={"owner_id": owner.id if owner else None}))
        milestones.append(milestone.model_copy(update={"tasks": tuple(tasks)}))
    return roadmap.model_copy(update={"milestones": tuple(milestones)}), warnings


def build_roadmap_draft(project: ProjectContext, title: str, idea: str, team: tuple[StudentProfile, ...]) -> tuple[dict, dict, list[dict]]:
    is_fixture = is_cs_club_example(title, idea)
    source_roadmap = _canonical_roadmap() if is_fixture else _generic_roadmap(project, title)
    assigned, warnings = allocate_roadmap(source_roadmap, team)
    generation = {"source": "fixture" if is_fixture else "template", "status": "ok" if is_fixture else "fallback",
                  "reason_code": "exact_cs_club_example" if is_fixture else "generic_confirmed_requirements_template"}
    return assigned.model_dump(mode="json"), generation, warnings
