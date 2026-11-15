"""Typed settings, read from environment variables only. Secrets never live in git."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    return int(value) if value else default


@dataclass(frozen=True)
class Config:
    database_url: str
    contact_url: str | None = None
    cors_origins: tuple[str, ...] = ()
    scrape_workers: int = 8
    testing: bool = False

    @classmethod
    def from_env(cls) -> Config:
        environment = os.environ.get("ENVIRONMENT", "production")
        database_url = os.environ.get("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("DATABASE_URL is not set (see .env.example)")
        origins = os.environ.get("CORS_ORIGINS", "")
        return cls(
            database_url=database_url,
            contact_url=os.environ.get("CONTACT_URL", "").strip() or None,
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
            scrape_workers=_int("SCRAPE_WORKERS", 8),
            testing=environment == "test",
        )
