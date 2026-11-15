"""SQLAlchemy 2.0 typed models. Migrations live in backend/migrations (Alembic)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSON,
        list[str]: JSON,
    }


class BoardRow(Base):
    """A job board the user follows."""

    __tablename__ = "boards"
    __table_args__ = (UniqueConstraint("platform", "slug", name="uq_boards_platform_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(40))
    slug: Mapped[str] = mapped_column(String(500))
    org: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(100), default="")
    options: Mapped[dict[str, Any]] = mapped_column(default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    # Outcome of the latest scrape. Full history comes with the scrape_runs table.
    last_scraped_at: Mapped[datetime | None] = mapped_column(default=None)
    last_status: Mapped[str | None] = mapped_column(String(20), default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    last_count: Mapped[int | None] = mapped_column(Integer, default=None)

    postings: Mapped[list[PostingRow]] = relationship(
        back_populates="board", cascade="all, delete-orphan", passive_deletes=True
    )


class PostingRow(Base):
    """One job, deduplicated by `posting_key` (org + title + location).

    Only listing metadata is stored: never the description."""

    __tablename__ = "postings"

    id: Mapped[int] = mapped_column(primary_key=True)
    posting_key: Mapped[str] = mapped_column(String(1200), unique=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    req_id: Mapped[str] = mapped_column(String(200), default="")
    org: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(500))
    location: Mapped[str | None] = mapped_column(Text, default=None)
    url: Mapped[str] = mapped_column(Text)
    posted_raw: Mapped[str] = mapped_column(String(100), default="")
    posted_on: Mapped[date | None] = mapped_column(Date, default=None)
    workplace: Mapped[str | None] = mapped_column(String(40), default=None)
    employment_type: Mapped[str | None] = mapped_column(String(40), default=None)
    first_seen_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(default=None, index=True)

    board: Mapped[BoardRow] = relationship(back_populates="postings")


class PostingMarkRow(Base):
    """A posting the user hid. Keyed like postings, so a mark survives the
    posting being re-listed under a new requisition id."""

    __tablename__ = "posting_marks"

    posting_key: Mapped[str] = mapped_column(String(1200), primary_key=True)
    status: Mapped[str] = mapped_column(String(20))  # hidden | not_interested
    org: Mapped[str] = mapped_column(String(200), default="")
    title: Mapped[str] = mapped_column(String(500), default="")
    location: Mapped[str | None] = mapped_column(Text, default=None)
    url: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class JobProfileRow(Base):
    """A named set of title terms: one tab on the dashboard."""

    __tablename__ = "job_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    include_terms: Mapped[list[str]] = mapped_column(default=list)
    exclude_terms: Mapped[list[str]] = mapped_column(default=list)
    seniority_terms: Mapped[list[str]] = mapped_column(default=list)
    advanced: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AppSettingsRow(Base):
    """The single row of user settings (id is always 1)."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    max_age_days: Mapped[int] = mapped_column(Integer, default=30)
    states: Mapped[list[str]] = mapped_column(default=list)
    cities: Mapped[list[str]] = mapped_column(default=list)
    remote: Mapped[bool] = mapped_column(Boolean, default=True)
    remote_states: Mapped[list[str]] = mapped_column(default=list)
    keep_unknown_location: Mapped[bool] = mapped_column(Boolean, default=False)
    employment_types: Mapped[list[str]] = mapped_column(default=list)
    work_types: Mapped[list[str]] = mapped_column(default=list)
    scrape_interval_hours: Mapped[int] = mapped_column(Integer, default=6)
    # "New since last visit": postings first seen after previous_visit_at.
    last_visit_at: Mapped[datetime | None] = mapped_column(default=None)
    previous_visit_at: Mapped[datetime | None] = mapped_column(default=None)
    last_full_scrape_at: Mapped[datetime | None] = mapped_column(default=None)
