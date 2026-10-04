"""Fictional, stable demo profiles and the canonical CS Club scenario."""

from .domain import ProjectRequirements, SkillRequirement, StudentProfile

CS_CLUB_REQUIREMENTS = ProjectRequirements(
    interests=("web", "education"),
    goals=("learn", "help_school"),
    weekly_hours_min=3,
    skill_requirements=(
        SkillRequirement(id="frontend-react", skill="react", aggregation="expert", required_level=3, importance=.4, critical=False),
        SkillRequirement(id="backend-python", skill="python", aggregation="expert", required_level=3, importance=.3, critical=True),
        SkillRequirement(id="design-uiux", skill="ui_ux", aggregation="collaborative", target_capacity=4, importance=.2, critical=False),
        SkillRequirement(id="coordination-skill", skill="coordination", aggregation="collaborative", target_capacity=3, importance=.1, critical=False),
    ),
)

DEMO_PROFILES = (
    StudentProfile(id="alice", display_name="Alice", skills={"react": 3, "python": 2, "ui_ux": 2}, interests=("web", "education"), goals=("learn", "portfolio"), role_preference="lead", communication="mixed", structure="structured", weekly_hours=3),
    StudentProfile(id="bob", display_name="Bob", skills={"react": 3, "python": 2}, interests=("web",), goals=("portfolio",), role_preference="lead", communication="mixed", structure="structured", weekly_hours=3),
    StudentProfile(id="charlie", display_name="Charlie", skills={"react": 1, "python": 3, "api_design": 3, "ui_ux": 3}, interests=("web", "education"), goals=("learn", "help_school"), role_preference="flexible", communication="async", structure="structured", weekly_hours=3),
    StudentProfile(id="emily", display_name="Emily", skills={"react": 1, "python": 1, "ui_ux": 2, "coordination": 3, "writing": 2}, interests=("education", "community"), goals=("help_school", "fun"), role_preference="support", communication="async", structure="flexible", weekly_hours=4),
    StudentProfile(id="devon", display_name="Devon", skills={"react": 1, "ui_ux": 1}, interests=("web", "art"), goals=("learn", "fun"), role_preference="flexible", communication="mixed", structure="flexible", weekly_hours=2),
    StudentProfile(id="frankie", display_name="Frankie", skills={"ui_ux": 3, "writing": 2}, interests=("art", "education"), goals=("portfolio", "help_school"), role_preference="support", communication="async", structure="structured", weekly_hours=5),
    StudentProfile(id="grace", display_name="Grace", skills={"outreach": 3, "writing": 3, "coordination": 2}, interests=("community", "education"), goals=("help_school", "fun"), role_preference="support", communication="synchronous", structure="structured", weekly_hours=3),
    StudentProfile(id="harper", display_name="Harper", skills={"python": 2, "api_design": 2}, interests=("ai", "web"), goals=("learn", "competition"), role_preference="flexible", communication="mixed", structure="spontaneous", weekly_hours=0),
)
