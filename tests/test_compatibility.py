from app.domain import StudentProfile
from app.matching import compatibility_components


def profile(profile_id, *, role="lead", communication="async", structure="structured", hours=4):
    return StudentProfile(id=profile_id, display_name=profile_id.title(), role_preference=role,
                          communication=communication, structure=structure, weekly_hours=hours)


def test_low_availability_is_capped_in_compatibility():
    candidate = profile("alice", hours=1)
    teammate = profile("founder", role="support")

    result = compatibility_components(candidate, (teammate,), 4)

    assert result["availability"] == .25
    assert result["role"] == 1.0
    assert result["work_style"] == 1.0
    assert result["compatibility"] == .6625


def test_empty_team_uses_availability_only():
    result = compatibility_components(profile("alice", hours=1), (), 4)

    assert result == {"availability": .25, "role": None, "work_style": None, "compatibility": .25}


def test_lead_lead_and_different_work_styles_are_preferences_not_a_block():
    candidate = profile("alice", role="lead", communication="async", structure="structured")
    teammate = profile("bob", role="lead", communication="synchronous", structure="spontaneous")

    result = compatibility_components(candidate, (teammate,), 4)

    assert result["role"] == .6
    assert result["work_style"] == .6
    assert result["compatibility"] == .78


def test_support_pair_and_wildcards_have_frozen_scores():
    support = compatibility_components(profile("alice", role="support"), (profile("bob", role="support"),), 4)
    wildcard = compatibility_components(
        profile("flex", role="flexible", communication="mixed", structure="flexible", hours=3),
        (profile("lead", role="lead", communication="async", structure="structured"),), 4)

    assert support["compatibility"] == .925
    assert wildcard["role"] == .9
    assert wildcard["work_style"] == .85
    assert wildcard["compatibility"] == .82


def test_missing_style_dimensions_are_excluded_and_no_evidence_is_neutral():
    partially_known = compatibility_components(
        profile("alice", communication=None, structure="structured"),
        (profile("bob", communication="async", structure="structured"),), 4)
    unknown = compatibility_components(
        profile("alice", communication=None, structure=None),
        (profile("bob", communication=None, structure=None),), 4)

    assert partially_known["work_style"] == 1.0
    assert unknown["work_style"] == .75


def test_multi_member_compatibility_averages_pair_scores():
    candidate = profile("alice", role="support", communication="async", structure="structured", hours=3)
    bob = profile("bob", role="lead", communication="synchronous", structure="spontaneous")
    charlie = profile("charlie", role="support", communication="async", structure="structured")

    result = compatibility_components(candidate, (bob, charlie), 4)

    assert result["availability"] == .75
    assert result["role"] == .875
    assert result["work_style"] == .8
