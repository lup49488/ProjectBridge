"""Validated, provider-independent domain types for team composition v1."""

from __future__ import annotations

from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SkillId = Literal["react", "python", "api_design", "ui_ux", "coordination", "writing", "outreach"]
InterestId = Literal["web", "ai", "education", "art", "community"]
GoalId = Literal["learn", "portfolio", "competition", "help_school", "fun"]
RolePreference = Literal["lead", "flexible", "support"]
CommunicationStyle = Literal["async", "mixed", "synchronous"]
StructureStyle = Literal["structured", "flexible", "spontaneous"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SkillRequirement(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    skill: SkillId
    aggregation: Literal["expert", "collaborative"]
    required_level: int | None = Field(default=None, ge=1, le=4)
    target_capacity: float | None = Field(default=None, gt=0, le=16)
    importance: float = Field(gt=0, le=1)
    critical: bool

    @model_validator(mode="after")
    def validate_aggregation_target(self) -> "SkillRequirement":
        if not isfinite(self.importance):
            raise ValueError("importance must be finite")
        if self.aggregation == "expert":
            if self.required_level is None or self.target_capacity is not None:
                raise ValueError("expert requires required_level and forbids target_capacity")
        elif self.target_capacity is None or self.required_level is not None:
            raise ValueError("collaborative requires target_capacity and forbids required_level")
        return self


class ProjectRequirements(StrictModel):
    schema_version: Literal["1.1"] = "1.1"
    interests: tuple[InterestId, ...] = ()
    goals: tuple[GoalId, ...] = ()
    weekly_hours_min: int = Field(ge=1, le=10)
    skill_requirements: tuple[SkillRequirement, ...] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_uniqueness(self) -> "ProjectRequirements":
        ids = [r.id for r in self.skill_requirements]
        skills = [r.skill for r in self.skill_requirements]
        if len(ids) != len(set(ids)) or len(skills) != len(set(skills)):
            raise ValueError("requirement IDs and skill IDs must be unique")
        return self


class StudentProfile(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=80)
    skills: dict[SkillId, int] = Field(default_factory=dict)
    interests: tuple[InterestId, ...] = ()
    goals: tuple[GoalId, ...] = ()
    role_preference: RolePreference
    communication: CommunicationStyle | None = None
    structure: StructureStyle | None = None
    weekly_hours: int | None = Field(default=None, ge=0, le=10)
    is_fictional: Literal[True] = True
    revision: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_skills(self) -> "StudentProfile":
        if any(isinstance(level, bool) or level < 0 or level > 4 for level in self.skills.values()):
            raise ValueError("skill levels must be integers from 0 through 4")
        return self


class ProjectContext(StrictModel):
    id: str
    desired_team_size: int = Field(ge=2, le=4)
    requirements: ProjectRequirements


def model_payload(model: BaseModel) -> dict:
    """Return JSON-compatible values for API responses and fixture persistence."""
    return model.model_dump(mode="json")
