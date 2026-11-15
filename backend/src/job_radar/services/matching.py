"""Job profiles: what kinds of jobs the user is looking for.

A profile matches a posting's *title* (listings carry no descriptions):

- the title contains at least one include term,
- contains no exclude term,
- and, if the profile lists seniority terms, contains one of those too.

Terms are case-insensitive phrases matched on word boundaries; spaces and hyphens
between words are interchangeable or optional ("full stack" matches "Full-Stack"
and "Fullstack"). An `advanced`
profile treats its terms as regular expressions instead; the presets below are
advanced, since they were tuned as regexes.

Presets are starting points the user copies into their own profiles. The
software list is broad on purpose: a stray match costs less than a missed
posting.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field


def _phrase_pattern(term: str) -> str:
    words = [re.escape(w) for w in re.split(r"[\s\-]+", term.strip()) if w]
    return r"(?<!\w)" + r"[\s\-]*".join(words) + r"(?!\w)"


def compile_terms(terms: Sequence[str], advanced: bool) -> re.Pattern[str] | None:
    """One case-insensitive pattern for a list of terms, or None for no terms.
    Raises ValueError for an invalid regex in an advanced profile."""
    cleaned = [t.strip() for t in terms if t.strip()]
    if not cleaned:
        return None
    parts = cleaned if advanced else [_phrase_pattern(t) for t in cleaned]
    try:
        return re.compile("|".join(f"(?:{p})" for p in parts), re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f"invalid pattern: {exc}") from exc


@dataclass(frozen=True)
class ProfileMatcher:
    include: re.Pattern[str] | None
    exclude: re.Pattern[str] | None = None
    seniority: re.Pattern[str] | None = None

    @classmethod
    def build(
        cls,
        include: Sequence[str],
        exclude: Sequence[str] = (),
        seniority: Sequence[str] = (),
        advanced: bool = False,
    ) -> ProfileMatcher:
        return cls(
            compile_terms(include, advanced),
            compile_terms(exclude, advanced),
            compile_terms(seniority, advanced),
        )

    def matches(self, title: str) -> bool:
        if self.include is None or not self.include.search(title):
            return False
        if self.exclude is not None and self.exclude.search(title):
            return False
        return self.seniority is None or bool(self.seniority.search(title))


@dataclass(frozen=True)
class Preset:
    key: str
    name: str
    include: tuple[str, ...]
    exclude: tuple[str, ...] = ()
    seniority: tuple[str, ...] = ()
    advanced: bool = True
    description: str = ""
    examples: tuple[str, ...] = field(default=())


SOFTWARE = Preset(
    key="software",
    name="Software engineering",
    description="Software, data, ML, DevOps/cloud and integration engineering titles.",
    include=(
        r"software",
        r"developer",
        r"programmer",
        r"full[- ]?stack",
        r"back[- ]?end",
        r"front[- ]?end (engineer|developer)|\bfrontend\b",
        r"mobile (engineer|developer)",
        r"\bpython\b",
        r"data engineer",
        r"data scientist",
        r"informatics",
        r"machine learning engineer",
        r"\bml ?ops\b|machine learning ops",
        r"\b(ai|ml)\b.*\bengineer",
        r"\bengineer\b.*\b(ai|ml)\b",
        r"devops|devsecops",
        r"\bcloud\b.*\bengineer",
        r"platform engineer",
        r"observability",
        r"site reliability|\bsre\b",
        r"\bhpc\b|high performance computing|research computing",
        r"integrations? (engineer|programmer|developer)",
        r"\bengineer\b.*\bintegrations\b",
        r"forward[- ]deployed (software )?engineer",
        r"computer (engineer|scientist)",
        r"systems analyst",
        r"applications? analyst",
    ),
    exclude=(
        r"\bintern(ship)?s?\b",
        r"\bco-?op\b",
        r"^student\b|\bstudent (worker|assistant|employee|intern)",
        r"\bfaculty\b",
        r"postdoc|post-doc",
        r"\badjunct\b",
        r"\blecturer\b",
        r"\bprofessor\b",
        r"course developer",
        r"micro-?credential",
        r"statistical programm",
    ),
)

BIOSTATISTICS = Preset(
    key="biostatistics",
    name="Biostatistics & evidence synthesis",
    description="Biostatistics, epidemiology, statistical programming, systematic reviews.",
    include=(
        r"biostatistic",
        r"statistician",
        r"statistical (methodologist|consultant)",
        r"statistical programm",
        r"methodologist",
        r"epidemiolog",
        r"meta[- ]?analy",
        r"evidence synthesis",
        r"systematic review",
        r"literature review",
        r"evidence[- ]based medicine",
        r"\bebm\b",
    ),
    exclude=(r"\bintern(ship)?s?\b", r"\bco-?op\b", r"\bstudent\b"),
)

HEOR_RWE = Preset(
    key="heor_rwe",
    name="HEOR / real-world evidence (associate & director)",
    description="Health economics and real-world evidence titles at associate or director level.",
    include=(
        r"\bheor\b",
        r"health economic",
        r"health outcomes",
        r"outcomes research",
        r"real[- ]world (evidence|data|insights|research|analytics)",
        r"\brwe\b",
        r"\brwd\b",
        r"evidence generation",
    ),
    exclude=(r"\bintern(ship)?s?\b", r"\bstudent\b"),
    seniority=(r"\b(associate|director)\b",),
)

PRESETS: tuple[Preset, ...] = (SOFTWARE, BIOSTATISTICS, HEOR_RWE)


def preset_matcher(preset: Preset) -> ProfileMatcher:
    return ProfileMatcher.build(preset.include, preset.exclude, preset.seniority, preset.advanced)
