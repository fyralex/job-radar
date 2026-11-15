"""The user's location rule: where they'll work on site, and whether remote counts.

Configured in Settings, stored in `app_settings`, and applied to location *text*
only (no geocoding, nothing sent to a third party):

- `states`: two-letter codes. Any place in one of them counts ("Austin, TX",
  "Texas", "US-TX-Austin").
- `cities`: "City, ST" entries. A city counts when the text names it and either
  names the same state or no state at all. City names shared by several places
  ("Cambridge", "Portland") are why the state check exists; a part that names a
  non-US country ("Cambridge, United Kingdom") never counts.
- With no states and no cities, every named place counts, abroad too.
- `remote`: whether remote jobs count. Nationwide US remote always counts then;
  remote limited to some states ("Remote - Texas", "US-TX-Remote") counts only
  if one of them is in `remote_states` (default: `states`).
- `keep_unknown`: keep postings whose text names no place we can read ("3
  Locations", "Multiple locations", an office nickname). Off by default.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property

from job_radar.sources.common import (
    FOREIGN_RE,
    REMOTE_RE,
    STATE_CODES,
    US_RE,
    is_us_remote,
    location_parts,
    remote_states,
    states_in,
)

PLACEHOLDER_RE = re.compile(r"^\s*\d+\s+locations?\s*$|multiple locations", re.IGNORECASE)

LOCAL, AWAY, UNKNOWN = "local", "away", "unknown"


def parse_city(entry: str) -> tuple[str, str] | None:
    """'Austin, TX' -> ('Austin', 'TX'); anything else -> None."""
    city, sep, state = entry.rpartition(",")
    city, state = city.strip(), state.strip().upper()
    if not sep or not city or state not in STATE_CODES:
        return None
    return city, state


@dataclass(frozen=True)
class LocationRule:
    states: frozenset[str] = frozenset()
    cities: tuple[tuple[str, str], ...] = ()
    remote: bool = True
    remote_states: frozenset[str] = frozenset()
    keep_unknown: bool = False

    @classmethod
    def build(
        cls,
        states: Iterable[str] = (),
        cities: Iterable[str] = (),
        remote: bool = True,
        remote_states: Iterable[str] = (),
        keep_unknown: bool = False,
    ) -> LocationRule:
        state_set = frozenset(s.strip().upper() for s in states if s.strip().upper() in STATE_CODES)
        parsed = tuple(c for c in (parse_city(x) for x in cities) if c is not None)
        remote_set = frozenset(
            s.strip().upper() for s in remote_states if s.strip().upper() in STATE_CODES
        )
        return cls(state_set, parsed, remote, remote_set or state_set, keep_unknown)

    @property
    def any_place(self) -> bool:
        return not self.states and not self.cities

    @cached_property
    def _city_res(self) -> tuple[tuple[re.Pattern[str], str], ...]:
        return tuple(
            (re.compile(rf"(?<![A-Za-z]){re.escape(city)}(?![A-Za-z])", re.IGNORECASE), state)
            for city, state in self.cities
        )

    def classify_part(self, part: str) -> str:
        """LOCAL (a place the user will work), AWAY (a place elsewhere) or
        UNKNOWN (no place we can read)."""
        if PLACEHOLDER_RE.search(part):
            return UNKNOWN
        states = states_in(part)
        foreign = bool(FOREIGN_RE.search(part))
        if states & self.states:
            return LOCAL
        if not foreign:
            for pattern, state in self._city_res:
                if pattern.search(part) and (not states or state in states):
                    return LOCAL
        words = set(re.findall(r"[a-z]+", part.lower()))
        named = bool(states) or foreign or bool(US_RE.search(part)) or bool(words)
        if self.any_place and named and not REMOTE_RE.search(part):
            return LOCAL
        if states or foreign:
            return AWAY
        return UNKNOWN

    def is_local(self, location: str | None) -> bool:
        """The text names a place the user will work at, outside a remote-only part."""
        return any(
            self.classify_part(p) == LOCAL and not REMOTE_RE.search(p)
            for p in location_parts(location)
        )

    def is_remote_ok(self, location: str | None) -> bool:
        if not self.remote or not location:
            return False
        if is_us_remote(location):
            return True
        return any(remote_states(p) & self.remote_states for p in location_parts(location))

    def is_placeless(self, location: str | None) -> bool:
        parts = location_parts(location)
        if not parts:
            return True
        return all(self.classify_part(p) == UNKNOWN and not REMOTE_RE.search(p) for p in parts)

    def wanted(self, location: str | None) -> bool:
        if self.is_local(location) or self.is_remote_ok(location):
            return True
        return self.keep_unknown and self.is_placeless(location)
