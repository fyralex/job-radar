"""Declared per-platform board options, so the API can validate what the UI sends."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

OptionKind = Literal["bool", "list"]


@dataclass(frozen=True, slots=True)
class Option:
    kind: OptionKind
    help: str


def validate_options(declared: Mapping[str, Option], options: Mapping[str, Any]) -> dict[str, Any]:
    """Return a clean copy of `options`, or raise ValueError naming the problem."""
    clean: dict[str, Any] = {}
    for name, value in options.items():
        spec = declared.get(name)
        if spec is None:
            raise ValueError(f"unknown option '{name}'")
        if spec.kind == "bool":
            if not isinstance(value, bool):
                raise ValueError(f"option '{name}' must be true or false")
            clean[name] = value
        else:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ValueError(f"option '{name}' must be a list of strings")
            clean[name] = [v.strip() for v in value if v.strip()]
    return clean
