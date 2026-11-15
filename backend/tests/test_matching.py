from __future__ import annotations

import pytest

from job_radar.services.matching import (
    BIOSTATISTICS,
    HEOR_RWE,
    SOFTWARE,
    ProfileMatcher,
    compile_terms,
    preset_matcher,
)

software = preset_matcher(SOFTWARE)


@pytest.mark.parametrize(
    "title",
    [
        "Senior Software Engineer",
        "Senior AI Engineer",
        "Senior Programmer Analyst",
        "Cloud Engineer II",
        "Software Security Engineer",
        "Engineer II, Software",
        "Snowflake Developer",
        "Senior DevOps Engineer",
        "Machine Learning Ops Eng II",
        "High Performance Computing Engineer",
        "Senior Workday Integration Engineer",
        "Data Scientist",
        "Software Engineer, Internal Tools",
        "Computer Systems Analyst",
        "Forward-Deployed Engineer",
        "Senior Engineer, Partner Integrations",
        "Staff Integrations Engineer",
    ],
)
def test_software_matches(title: str) -> None:
    assert software.matches(title)


@pytest.mark.parametrize(
    "title",
    [
        "Software Engineering Intern",
        "Software Engineering Co-Op",
        "Student Software Developer",
        "Adjunct Faculty - Computer Science",
        "Principal Programmer, Statistical Programming (Remote)",
        "Director of Development",
        "Security Guard",
        "Systems Engineer II - Integration & Test",
    ],
)
def test_software_rejects(title: str) -> None:
    assert not software.matches(title)


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Principal Biostatistician", True),
        ("Quantitative Epidemiologist", True),
        ("Epidemiologist, Internal Medicine", True),
        ("Systematic Reviewer", True),
        ("Biostatistics Intern", False),
        ("Software Engineer", False),
    ],
)
def test_biostatistics(title: str, expected: bool) -> None:
    assert preset_matcher(BIOSTATISTICS).matches(title) is expected


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Associate Director, Health Economics and Outcomes Research", True),
        ("Director, Real-World Evidence", True),
        ("HEOR Associate", True),
        ("HEOR Scientist", False),  # below associate/director level
        ("RWE Analyst", False),
        ("Brewer", False),  # "rwe" inside a word
    ],
)
def test_heor_needs_seniority(title: str, expected: bool) -> None:
    assert preset_matcher(HEOR_RWE).matches(title) is expected


def test_plain_phrases_use_word_boundaries_and_flexible_separators() -> None:
    matcher = ProfileMatcher.build(["full stack", "react"], exclude=["intern"])
    assert matcher.matches("Full-Stack Engineer")
    assert matcher.matches("Fullstack Engineer")  # separators may be absent too
    assert matcher.matches("Full Stack Engineer")
    assert matcher.matches("React Developer")
    assert not matcher.matches("Reactor Operator")
    assert not matcher.matches("React Intern")
    assert matcher.matches("React Engineer, Internal Tools")


def test_plain_phrases_escape_regex_characters() -> None:
    matcher = ProfileMatcher.build(["C++", ".NET"])
    assert matcher.matches("C++ Developer")
    assert matcher.matches("Senior .NET Engineer")
    assert not matcher.matches("C Developer")


def test_seniority_terms() -> None:
    matcher = ProfileMatcher.build(["engineer"], seniority=["senior", "staff"])
    assert matcher.matches("Senior Engineer")
    assert not matcher.matches("Engineer II")


def test_no_include_terms_matches_nothing() -> None:
    assert not ProfileMatcher.build([]).matches("Software Engineer")


def test_invalid_regex_raises() -> None:
    with pytest.raises(ValueError, match="invalid pattern"):
        compile_terms(["(unclosed"], advanced=True)
