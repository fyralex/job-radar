"""Flask CLI commands: `flask boards import <file>`, `flask scrape`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click
import yaml
from flask import Flask
from sqlalchemy import select

from job_radar.db import session_scope
from job_radar.models import BoardRow
from job_radar.services.boards_repo import clean_board_input
from job_radar.services.refresh import run_scrape


def load_board_file(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    boards = data.get("boards") if isinstance(data, dict) else None
    if not isinstance(boards, list):
        raise click.ClickException(f"{path}: expected a top-level 'boards:' list")
    return [clean_board_input(b) for b in boards if isinstance(b, dict)]


def register_cli(app: Flask) -> None:
    boards_group = click.Group("boards", help="Manage followed boards.")

    @boards_group.command("import")
    @click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
    def import_boards(path: Path) -> None:
        """Add the boards listed in a YAML file (see config/boards.example.yaml).
        Boards already followed are left alone."""
        from job_radar.app import EXTENSION

        factory = app.extensions[EXTENSION].sessions
        added = skipped = 0
        with session_scope(factory) as session:
            for board in load_board_file(path):
                exists = session.scalar(
                    select(BoardRow.id).where(
                        BoardRow.platform == board["platform"], BoardRow.slug == board["slug"]
                    )
                )
                if exists:
                    skipped += 1
                    continue
                session.add(BoardRow(**board))
                added += 1
        click.echo(f"added {added} boards, skipped {skipped} already followed")

    @app.cli.command("scrape")
    def scrape() -> None:
        """Scrape every enabled board now."""
        from job_radar.app import EXTENSION

        app_state = app.extensions[EXTENSION]
        summary = run_scrape(
            app_state.sessions, app_state.config.contact_url, app_state.config.scrape_workers
        )
        if summary is None:
            raise click.ClickException("a scrape is already running")
        click.echo(f"{summary.boards} boards, {summary.failed} failed, {summary.postings} postings")

    app.cli.add_command(boards_group)
