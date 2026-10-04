"""Pure deterministic team-composition engine. No I/O, providers, or randomness."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from typing import Iterable

from .domain import ProjectContext, ProjectRequirements, SkillRequirement, StudentProfile

FORMULA_VERSION = "team-composition-v1"
ALPHA = .70
EPSILON = .05
GENERAL_WEIGHTS = {"marginal_contribution": .40, "individual_fit": .25, "compatibility": .20, "interest_goal_fit": .15}
COMPATIBILITY_WEIGHTS = {"availability": .45, "role": .30, "work_style": .25}
ROLE_PAIR_SCORES = {"lead_lead": .60, "support_support": .75, "lead_support": 1.0}
WORK_STYLE_SCORES = {"same": 1.0, "wildcard": .85, "different": .60}
UNKNOWN_WORK_STYLE_NEUTRAL = .75
QUANTUM = Decimal("0.00000001")


def q(value: float) -> float:
    return float(Decimal(str(value)).quantize(QUANTUM, rounding=ROUND_HALF_EVEN))


def effective_value(requirement: SkillRequirement, team: Iterable[StudentProfile]) -> float:
    levels = [p.skills.get(requirement.skill, 0) for p in team]
    if requirement.aggregation == "expert":
        return float(max(levels, default=0))
    return sum(level * ALPHA**index for index, level in enumerate(sorted(levels, reverse=True)))


def requirement_coverage(requirement: SkillRequirement, team: Iterable[StudentProfile]) -> float:
    effective = effective_value(requirement, team)
    target = requirement.required_level if requirement.aggregation == "expert" else requirement.target_capacity
    return min(effective / target, 1.0)  # type: ignore[operator]


def coverage_breakdown(requirements: ProjectRequirements, team: Iterable[StudentProfile]) -> list[dict]:
    members = tuple(team)
    total_importance = sum(r.importance for r in requirements.skill_requirements)
    rows = []
    for r in sorted(requirements.skill_requirements, key=lambda item: item.id):
        observed = sorted((p.skills.get(r.skill, 0) for p in members), reverse=True)
        cov = requirement_coverage(r, members)
        rows.append({"requirement_id": r.id, "skill": r.skill, "aggregation": r.aggregation,
                     "target": r.required_level if r.aggregation == "expert" else r.target_capacity,
                     "importance": r.importance, "critical": r.critical, "observed_levels": observed,
                     "not_reported_member_ids": [p.id for p in members if r.skill not in p.skills],
                     "effective_value": effective_value(r, members), "coverage": q(cov),
                     "weighted_coverage": q(r.importance / total_importance * cov)})
    return rows


def total_coverage(requirements: ProjectRequirements, team: Iterable[StudentProfile]) -> float:
    rows = coverage_breakdown(requirements, team)
    return sum(row["weighted_coverage"] for row in rows)


def critical_deficit(requirements: ProjectRequirements, team: Iterable[StudentProfile]) -> float:
    critical = [r for r in requirements.skill_requirements if r.critical]
    if not critical:
        return 0.0
    weight = sum(r.importance for r in critical)
    return q(sum(r.importance / weight * (1 - requirement_coverage(r, team)) for r in critical))


def _tag_fit(wanted: tuple[str, ...], actual: tuple[str, ...]) -> float:
    if not wanted:
        return .5
    if not actual:
        return 0.0
    return len(set(wanted) & set(actual)) / len(set(wanted))


def availability_alignment(candidate: StudentProfile, weekly_hours_min: int) -> float:
    """Fraction of project hours the candidate reports, capped at full alignment.

    Automatic selection filters unknown/zero-hour profiles before scoring, as the
    formula is defined only for positive candidate and project hours.
    """
    if weekly_hours_min <= 0:
        raise ValueError("weekly_hours_min must be positive")
    if candidate.weekly_hours is None or candidate.weekly_hours <= 0:
        raise ValueError("candidate needs positive known weekly hours for compatibility scoring")
    return min(candidate.weekly_hours / weekly_hours_min, 1.0)


def _role_pair_score(left: str, right: str) -> float:
    if left == "flexible" or right == "flexible":
        return .90
    if left == right == "lead":
        return ROLE_PAIR_SCORES["lead_lead"]
    if left == right == "support":
        return ROLE_PAIR_SCORES["support_support"]
    return ROLE_PAIR_SCORES["lead_support"]


def _work_style_pair_score(left: StudentProfile, right: StudentProfile) -> float:
    comparable = []
    wildcard_values = {"mixed", "flexible"}
    for field in ("communication", "structure"):
        left_value, right_value = getattr(left, field), getattr(right, field)
        if left_value is None or right_value is None:
            continue
        if left_value == right_value:
            comparable.append(WORK_STYLE_SCORES["same"])
        elif left_value in wildcard_values or right_value in wildcard_values:
            comparable.append(WORK_STYLE_SCORES["wildcard"])
        else:
            comparable.append(WORK_STYLE_SCORES["different"])
    if not comparable:
        return UNKNOWN_WORK_STYLE_NEUTRAL
    return sum(comparable) / len(comparable)


def compatibility_components(candidate: StudentProfile, team: tuple[StudentProfile, ...], weekly_hours_min: int) -> dict:
    availability = availability_alignment(candidate, weekly_hours_min)
    if not team:
        return {"availability": q(availability), "role": None, "work_style": None,
                "compatibility": q(availability)}
    role = sum(_role_pair_score(candidate.role_preference, member.role_preference) for member in team) / len(team)
    work_style = sum(_work_style_pair_score(candidate, member) for member in team) / len(team)
    value = (.45 * availability) + (.30 * role) + (.25 * work_style)
    return {"availability": q(availability), "role": q(role), "work_style": q(work_style),
            "compatibility": q(value)}


def _score_components(req: ProjectRequirements, candidate: StudentProfile, team: tuple[StudentProfile, ...]) -> dict:
    mc = max(0.0, total_coverage(req, (*team, candidate)) - total_coverage(req, team))
    individual = total_coverage(req, (candidate,))
    compatibility = compatibility_components(candidate, team, req.weekly_hours_min)
    compat = compatibility["compatibility"]
    interest = (_tag_fit(req.interests, candidate.interests) + _tag_fit(req.goals, candidate.goals)) / 2
    score = .4 * mc + .25 * individual + .2 * compat + .15 * interest
    return {"marginal_contribution": q(mc), "individual_fit": q(individual), "compatibility": q(compat),
            "compatibility_components": compatibility, "interest_goal_fit": q(interest), "general_score": q(score)}


def missing_piece(requirements: ProjectRequirements, team: Iterable[StudentProfile], profiles: Iterable[StudentProfile], weekly_hours_min: int = 1) -> dict | None:
    members = tuple(team)
    rows = coverage_breakdown(requirements, members)
    gaps = [row for row in rows if row["coverage"] < 1]
    if not gaps:
        return None
    critical_gaps = [row for row in gaps if row["critical"]]
    active = critical_gaps or gaps
    chosen = sorted(active, key=lambda row: (-q(row["importance"] * (1-row["coverage"])), row["requirement_id"]))[0]
    req = next(r for r in requirements.skill_requirements if r.id == chosen["requirement_id"])
    candidates = []
    for profile in profiles:
        if profile.id in {member.id for member in members}:
            continue
        before = requirement_coverage(req, members)
        after = requirement_coverage(req, (*members, profile))
        if after <= before:
            continue
        warnings = ["weekly_hours_below_minimum"] if profile.weekly_hours is not None and profile.weekly_hours < weekly_hours_min else []
        if profile.weekly_hours in (None, 0):
            warnings.append("excluded_from_automatic_selection_unknown_or_zero_hours")
        candidates.append({"profile_id": profile.id, "weighted_improvement": q(req.importance * (after-before)),
                           "automatic_feasible": profile.weekly_hours is not None and profile.weekly_hours > 0,
                           "warnings": warnings})
    candidates.sort(key=lambda item: (-item["weighted_improvement"], item["profile_id"]))
    return {"label": "Critical Missing Piece" if chosen["critical"] else "Missing Piece", **chosen,
            "best_for_this_gap": candidates, "no_improving_candidate": not candidates}


def rank_candidates(project: ProjectContext, team_ids: Iterable[str], profiles: Iterable[StudentProfile], *, target_size: int | None = None) -> dict:
    pool = tuple(sorted(profiles, key=lambda p: p.id))
    by_id = {p.id: p for p in pool}
    selected_ids = list(team_ids)
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("team member IDs must be unique")
    unknown = set(selected_ids) - set(by_id)
    if unknown:
        raise ValueError(f"unknown profile IDs: {', '.join(sorted(unknown))}")
    if len(selected_ids) > project.desired_team_size:
        raise ValueError("current team exceeds desired_team_size")
    team = [by_id[profile_id] for profile_id in selected_ids]
    current_team = tuple(team)
    current_coverage = coverage_breakdown(project.requirements, current_team)
    current_missing_piece = missing_piece(project.requirements, current_team, pool, project.requirements.weekly_hours_min)
    target = min(target_size or project.desired_team_size, project.desired_team_size)
    steps = []
    while len(team) < target:
        current = tuple(team)
        available = [p for p in pool if p.id not in selected_ids and p.weekly_hours is not None and p.weekly_hours > 0]
        if not available:
            break
        current_rows = coverage_breakdown(project.requirements, current)
        gaps_remain = any(row["coverage"] < 1 for row in current_rows)
        unresolved_critical = any(row["critical"] and row["coverage"] < 1 for row in current_rows)
        evaluated = []
        for person in available:
            before_deficit = critical_deficit(project.requirements, current)
            after_deficit = critical_deficit(project.requirements, (*current, person))
            cg = q(before_deficit-after_deficit)
            components = _score_components(project.requirements, person, current)
            warnings = []
            if person.weekly_hours is not None and person.weekly_hours < project.requirements.weekly_hours_min:
                warnings.append("weekly_hours_below_minimum")
            evaluated.append({"profile_id": person.id, "critical_gain": cg, **components, "warnings": warnings})
        positive_cg = [item for item in evaluated if item["critical_gain"] > 0]
        if unresolved_critical and positive_cg:
            max_cg = max(item["critical_gain"] for item in positive_cg)
            eligible = [item for item in positive_cg if q(max_cg-item["critical_gain"]) <= EPSILON]
            mode = "critical_priority"
        elif gaps_remain and any(item["marginal_contribution"] > 0 for item in evaluated):
            eligible = [item for item in evaluated if item["marginal_contribution"] > 0]
            mode = "positive_marginal_contribution"
        else:
            eligible, mode = evaluated, "general_score"
        eligible.sort(key=lambda item: (-item["general_score"], -item["marginal_contribution"], item["profile_id"]))
        chosen = eligible[0]
        steps.append({"selection_order": len(steps)+1, "selection_mode": mode, "candidate": chosen,
                      "considered": evaluated, "coverage_before": q(total_coverage(project.requirements, current))})
        selected_ids.append(chosen["profile_id"])
        team.append(by_id[chosen["profile_id"]])
    return {"formula_version": FORMULA_VERSION,
            "formula_parameters": {"alpha": ALPHA, "epsilon": EPSILON, "general_score_weights": GENERAL_WEIGHTS,
                                   "compatibility_weights": COMPATIBILITY_WEIGHTS,
                                   "role_pair_scores": ROLE_PAIR_SCORES,
                                   "work_style_pair_scores": WORK_STYLE_SCORES,
                                   "unknown_work_style_neutral": UNKNOWN_WORK_STYLE_NEUTRAL,
                                   "precision": "decimal half-even quantized to 8 places for decisions"},
            "team_ids": selected_ids, "steps": steps,
            "current_coverage": current_coverage,
            "current_missing_piece": current_missing_piece,
            "coverage": coverage_breakdown(project.requirements, team),
            "total_coverage": q(total_coverage(project.requirements, team)),
            "critical_deficit": critical_deficit(project.requirements, team),
            "missing_piece": missing_piece(project.requirements, team, pool, project.requirements.weekly_hours_min)}
