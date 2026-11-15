"""Source modules, one per job-board platform, keyed by platform id.

Only platforms allowed by the data collection policy in CLAUDE.md belong here.
A new platform needs the owner's approval first (see the add-source-module
skill)."""

from __future__ import annotations

from collections.abc import Mapping
from types import ModuleType
from typing import Protocol, cast

from job_radar.http import HttpClient
from job_radar.sources import (
    ashby,
    breezy,
    greenhouse,
    jobvite,
    jsonld,
    lever,
    recruitee,
    teamtailor,
    workable,
)
from job_radar.sources.common import Board, RawPosting
from job_radar.sources.options import Option


class SourceModule(Protocol):
    PLATFORM_NAME: str
    SLUG_HELP: str
    OPTIONS: Mapping[str, Option]

    def fetch_board(self, client: HttpClient, board: Board) -> list[RawPosting]: ...

    def board_url(self, board: Board) -> str: ...


_MODULES: dict[str, ModuleType] = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "workable": workable,
    "teamtailor": teamtailor,
    "breezy": breezy,
    "jobvite": jobvite,
    "recruitee": recruitee,
    "jsonld": jsonld,
}
PLATFORMS: dict[str, SourceModule] = {k: cast(SourceModule, m) for k, m in _MODULES.items()}


def get_platform(platform: str) -> SourceModule:
    try:
        return PLATFORMS[platform]
    except KeyError:
        raise ValueError(f"unknown platform '{platform}'") from None
