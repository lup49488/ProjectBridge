"""Strict request schemas for the session-scoped core API."""

from __future__ import annotations

from math import isfinite
from typing import Literal

from pydantic import Field, model_validator

from .domain import GoalId, InterestId, ProjectRequirements, RolePreference, SkillId, StrictModel


class ProjectCreate(StrictModel):
    client_request_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=100)
    idea: str = Field(min_length=20, max_length=2000)
    desired_team_size: int = Field(ge=2, le=4)


class ProjectPatch(StrictModel):
    expected_idea_revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=100)
    idea: str | None = Field(default=None, min_length=20, max_length=2000)
    desired_team_size: int | None = Field(default=None, ge=2, le=4)


class ProfilePatch(StrictModel):
    expected_revision: int = Field(ge=1)
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    skills: dict[SkillId, int] | None = None
    interests: tuple[InterestId, ...] | None = None
    goals: tuple[GoalId, ...] | None = None
    role_preference: RolePreference | None = None
    communication: str | None = None
    structure: str | None = None
    weekly_hours: int | None = Field(default=None, ge=0, le=10)


class RequirementConfirmation(StrictModel):
    expected_idea_revision: int = Field(ge=1)
    expected_requirements_revision: int = Field(ge=0)
    requirements: ProjectRequirements


class InputRevisions(StrictModel):
    idea: int = Field(ge=1)
    requirements: int = Field(ge=0)
    team: int = Field(ge=1)
    profiles: int = Field(ge=1)


class TeamSuggestionRequest(StrictModel):
    input_revisions: InputRevisions
    target_size: int | None = Field(default=None, ge=2, le=4)


class TeamUpdate(StrictModel):
    input_revisions: InputRevisions
    member_ids: tuple[str, ...] = Field(max_length=4)


class AnalysisRequest(StrictModel):
    expected_idea_revision: int = Field(ge=1)


class ExplanationRequest(StrictModel):
    input_revisions: InputRevisions
    candidate_id: str | None = None


class RoadmapTaskInput(StrictModel):
    title: str = Field(min_length=1, max_length=120)
    definition_of_done: str = Field(min_length=1, max_length=500)
    required_skill: SkillId | None = None
    required_level: int | None = Field(default=None, ge=1, le=4)
    owner_id: str | None = None
    estimated_hours: float = Field(ge=.5, le=4)
    acknowledged_skill_mismatch: bool = False

    @model_validator(mode="after")
    def validate_task(self) -> "RoadmapTaskInput":
        if not isfinite(self.estimated_hours):
            raise ValueError("estimated_hours must be finite")
        if (self.required_skill is None) != (self.required_level is None):
            raise ValueError("required_skill and required_level must both be set or both be null")
        return self


class MilestoneInput(StrictModel):
    week: int = Field(ge=1, le=4)
    title: str = Field(min_length=1, max_length=120)
    objective: str = Field(min_length=1, max_length=300)
    tasks: tuple[RoadmapTaskInput, ...] = Field(min_length=1, max_length=12)


class RoadmapInput(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    milestones: tuple[MilestoneInput, ...] = Field(min_length=1, max_length=4)
    assumptions: tuple[str, ...] = Field(default=(), max_length=3)

    @model_validator(mode="after")
    def validate_roadmap(self) -> "RoadmapInput":
        weeks = [milestone.week for milestone in self.milestones]
        if len(weeks) != len(set(weeks)):
            raise ValueError("roadmap milestone weeks must be unique")
        if sum(len(milestone.tasks) for milestone in self.milestones) > 12:
            raise ValueError("roadmap may contain at most 12 tasks")
        if any(len(text) > 200 for text in self.assumptions):
            raise ValueError("roadmap assumptions must be at most 200 characters")
        return self


class RoadmapDraftRequest(StrictModel):
    input_revisions: InputRevisions


class RoadmapSaveRequest(StrictModel):
    input_revisions: InputRevisions
    expected_roadmap_revision: int | None = Field(default=None, ge=1)
    confirm_replace: bool = False
    source: Literal["fixture", "template", "manual"] = "manual"
    roadmap: RoadmapInput


class TaskStatusUpdate(StrictModel):
    expected_roadmap_revision: int = Field(ge=1)
    status: Literal["todo", "doing", "done"]

