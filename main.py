#!/usr/bin/env python3
"""Typer CLI entrypoint for the João Pessoa restaurant crawler."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from restaurant_crawler import __version__
from restaurant_crawler.config.settings import get_settings, reload_settings
from restaurant_crawler.crawler.engine import CrawlEngine
from restaurant_crawler.database.connection import Database
from restaurant_crawler.database.repository import RestaurantRepository
from restaurant_crawler.exporters.csv_exporter import CsvExporter
from restaurant_crawler.exporters.report_generator import ReportGenerator
from restaurant_crawler.pipelines.validation_pipeline import ValidationPipeline
from restaurant_crawler.utils.logging import setup_logging

app = typer.Typer(
    name="restaurant-crawler",
    help="Production crawler for publicly discoverable restaurants in João Pessoa, PB, Brazil.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


def _engine(config: Optional[Path] = None) -> CrawlEngine:
    if config:
        settings = reload_settings(config)
    else:
        settings = get_settings()
    setup_logging(settings.logs_path, level=settings.log_level)
    return CrawlEngine(settings)


@app.callback()
def main_callback(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config.yaml",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """Restaurant crawler CLI."""
    if config:
        reload_settings(config)


@app.command("crawl")
def crawl_cmd(
    resume: bool = typer.Option(False, "--resume", help="Resume interrupted crawl"),
) -> None:
    """Discover and scrape restaurants."""
    engine = _engine()
    console.print(f"[bold]Restaurant Crawler v{__version__}[/bold]")
    console.print(
        f"Target: {engine.settings.city}, {engine.settings.state}, {engine.settings.country}"
    )
    stats = asyncio.run(engine.crawl(resume=resume))
    _print_stats(stats)
    # Auto-export + report after crawl
    export_cmd()
    validate_cmd()


@app.command("resume")
def resume_cmd() -> None:
    """Resume an interrupted crawl job."""
    engine = _engine()
    state = engine.state.load()
    console.print(f"Previous state: {state.get('status', 'unknown')}")
    stats = asyncio.run(engine.crawl(resume=True))
    _print_stats(stats)
    export_cmd()
    validate_cmd()


@app.command("export")
def export_cmd() -> None:
    """Export SQLite data to UTF-8 CSV files."""
    settings = get_settings()
    repo = RestaurantRepository(Database(settings.db_path))
    paths = CsvExporter(settings, repo).export_all()
    console.print("[green]CSV export complete[/green]")
    for name, path in paths.items():
        console.print(f"  {name}: {path}")


@app.command("validate")
def validate_cmd() -> None:
    """Validate crawled data and write reports."""
    settings = get_settings()
    repo = RestaurantRepository(Database(settings.db_path))
    report = ValidationPipeline(settings, repo).validate()
    paths = ReportGenerator(settings, repo).generate(validation=report)
    console.print(
        f"[green]Validation:[/green] {report.valid_restaurants}/{report.total_restaurants} "
        f"valid ({report.success_rate}%)"
    )
    for name, path in paths.items():
        console.print(f"  {name}: {path}")


@app.command("images")
def images_cmd() -> None:
    """Download / retry restaurant images only."""
    engine = _engine()
    result = asyncio.run(engine.process_images_only())
    console.print(f"Photos downloaded: {result.get('photos_downloaded', 0)}")


@app.command("menus")
def menus_cmd() -> None:
    """Extract / retry menus only."""
    engine = _engine()
    result = asyncio.run(engine.process_menus_only())
    console.print(f"Menu items extracted: {result.get('menu_items', 0)}")


@app.command("stats")
def stats_cmd() -> None:
    """Show database statistics."""
    settings = get_settings()
    repo = RestaurantRepository(Database(settings.db_path))
    _print_stats(repo.stats())


def _print_stats(stats: dict) -> None:
    table = Table(title="Crawler Statistics")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for key, value in stats.items():
        table.add_row(str(key), str(value))
    console.print(table)


@app.command("version")
def version_cmd() -> None:
    """Show package version."""
    console.print(__version__)


if __name__ == "__main__":
    app()
