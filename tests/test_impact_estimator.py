"""
Unit tests for chaos_tester.impact_estimator.

Verifies the (documented, tunable) dollar-impact and fix build-time heuristics
return sane, ordered, non-zero values across severities and modules, degrade
gracefully on unknown input, and that the estimates flow through
TestResult.to_dict().

Run: python -m pytest tests/test_impact_estimator.py -v
"""

from __future__ import annotations

import pytest

from chaos_tester.impact_estimator import (
    estimate_dollar_impact,
    estimate_fix_time,
    format_dollar_impact,
)
from chaos_tester.models import TestResult, TestStatus, Severity

ISSUE_SEVERITIES = ["critical", "high", "medium", "low"]
MODULES = ["forms", "security", "availability", "auth", "chaos", "links"]


# -------------------------------------------------------------------
# Dollar impact
# -------------------------------------------------------------------

@pytest.mark.parametrize("module", MODULES)
@pytest.mark.parametrize("severity", ISSUE_SEVERITIES)
def test_dollar_impact_is_positive_for_real_issues(severity, module):
    """Every displayed finding type gets a real, non-zero dollar figure."""
    assert estimate_dollar_impact(severity, module) > 0


@pytest.mark.parametrize("module", MODULES)
def test_dollar_impact_orders_by_severity(module):
    """More severe findings must never estimate less than milder ones."""
    vals = [estimate_dollar_impact(s, module) for s in ISSUE_SEVERITIES]
    assert vals == sorted(vals, reverse=True)
    assert vals[0] > vals[-1]  # critical strictly worse than low


def test_info_impact_is_minimal():
    assert estimate_dollar_impact("info", "forms") == 0
    assert format_dollar_impact(0) == "Minimal"


def test_dollar_impact_unknown_inputs_do_not_raise():
    assert estimate_dollar_impact("bogus", "bogus") == 0
    assert estimate_dollar_impact(None, None) == 0
    assert estimate_dollar_impact("", "") == 0


def test_format_dollar_impact():
    assert format_dollar_impact(6000) == "$6,000/yr"
    assert format_dollar_impact(13500) == "$13,500/yr"
    assert format_dollar_impact(0) == "Minimal"
    assert format_dollar_impact(-5) == "Minimal"


def test_reported_finding_forms_high():
    """The finding from the bug report: forms / high."""
    assert estimate_dollar_impact("high", "forms") == 6000
    assert format_dollar_impact(estimate_dollar_impact("high", "forms")) == "$6,000/yr"


# -------------------------------------------------------------------
# Fix build-time
# -------------------------------------------------------------------

@pytest.mark.parametrize("module", MODULES)
@pytest.mark.parametrize("severity", ISSUE_SEVERITIES + ["info"])
def test_fix_time_is_positive_and_labelled(severity, module):
    fix = estimate_fix_time(severity, module)
    assert fix["minutes"] > 0
    assert isinstance(fix["label"], str) and fix["label"].startswith("~")


@pytest.mark.parametrize("module", MODULES)
def test_fix_time_orders_by_severity(module):
    mins = [estimate_fix_time(s, module)["minutes"] for s in ISSUE_SEVERITIES]
    assert mins == sorted(mins, reverse=True)


def test_fix_time_unknown_inputs_do_not_raise():
    assert estimate_fix_time("bogus", "bogus")["minutes"] > 0
    assert estimate_fix_time(None, None)["minutes"] > 0


def test_reported_finding_fix_time():
    assert estimate_fix_time("high", "forms") == {"label": "~2 hours", "minutes": 120}


# -------------------------------------------------------------------
# Integration: estimates flow through TestResult.to_dict()
# -------------------------------------------------------------------

def test_to_dict_includes_estimates_and_keeps_legacy_fields():
    r = TestResult(
        module="forms",
        name="Missing CSRF token: auth-form",
        status=TestStatus.FAILED,
        severity=Severity.HIGH,
        recommendation="Add CSRF token to all POST forms.",
        duration_ms=0.0,
    )
    d = r.to_dict()
    # new estimate fields
    assert d["dollar_impact"] == 6000
    assert d["dollar_impact_display"] == "$6,000/yr"
    assert d["fix_time"] == "~2 hours"
    assert d["fix_time_minutes"] == 120
    # legacy fields untouched
    assert d["status"] == "failed"
    assert d["severity"] == "high"
    assert d["duration_ms"] == 0.0
    assert d["recommendation"] == "Add CSRF token to all POST forms."
