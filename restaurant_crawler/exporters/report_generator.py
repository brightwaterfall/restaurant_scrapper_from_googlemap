"""Generate HTML / JSON / TXT crawl reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from restaurant_crawler.config.settings import Settings
from restaurant_crawler.database.repository import RestaurantRepository
from restaurant_crawler.pipelines.validation_pipeline import ValidationReport
from restaurant_crawler.utils.logging import get_logger

logger = get_logger()

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8"/>
  <title>Restaurant Crawler Report — João Pessoa</title>
  <style>
    body {{ font-family: Georgia, 'Times New Roman', serif; margin: 2rem; background: #f7f3ec; color: #1f1a14; }}
    h1 {{ font-size: 2rem; margin-bottom: 0.25rem; }}
    .meta {{ color: #5c5346; margin-bottom: 2rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; }}
    .stat {{ background: #fff; border: 1px solid #e2d8c8; padding: 1rem; }}
    .stat strong {{ display: block; font-size: 1.6rem; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 2rem; background: #fff; }}
    th, td {{ border: 1px solid #e2d8c8; padding: 0.5rem; text-align: left; font-size: 0.95rem; }}
    th {{ background: #efe6d8; }}
  </style>
</head>
<body>
  <h1>Restaurant Crawler Report</h1>
  <p class="meta">João Pessoa · Paraíba · Brazil · Generated {generated_at}</p>
  <div class="grid">
    <div class="stat"><span>Restaurants</span><strong>{restaurants}</strong></div>
    <div class="stat"><span>Menus</span><strong>{menus}</strong></div>
    <div class="stat"><span>Menu Items</span><strong>{menu_items}</strong></div>
    <div class="stat"><span>Photos Downloaded</span><strong>{photos_downloaded}</strong></div>
    <div class="stat"><span>Failures</span><strong>{failed}</strong></div>
    <div class="stat"><span>Success Rate</span><strong>{success_rate}%</strong></div>
    <div class="stat"><span>Execution Time</span><strong>{elapsed}s</strong></div>
    <div class="stat"><span>Missing Menus</span><strong>{missing_menus}</strong></div>
  </div>
  <h2>Validation Issues (top 50)</h2>
  <table>
    <thead><tr><th>Restaurant</th><th>Code</th><th>Severity</th><th>Message</th></tr></thead>
    <tbody>
      {issue_rows}
    </tbody>
  </table>
</body>
</html>
"""


class ReportGenerator:
    def __init__(self, settings: Settings, repo: RestaurantRepository) -> None:
        self.settings = settings
        self.repo = repo
        self.output = settings.output_path
        self.output.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        validation: ValidationReport | None = None,
        crawl_stats: dict | None = None,
    ) -> dict[str, str]:
        stats = self.repo.stats()
        crawl_stats = crawl_stats or self.repo.get_state("crawl_run", {})
        elapsed = 0
        if isinstance(crawl_stats, dict):
            elapsed = crawl_stats.get("stats", {}).get("elapsed_seconds") or crawl_stats.get(
                "elapsed_seconds", 0
            )

        success_rate = validation.success_rate if validation else 0.0
        missing_menus = len(validation.missing_menus) if validation else 0
        issues = validation.issues[:50] if validation else []

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "city": self.settings.city,
            "state": self.settings.state,
            "country": self.settings.country,
            "stats": stats,
            "crawl": crawl_stats,
            "validation": validation.to_dict() if validation else None,
            "execution_time_seconds": elapsed,
            "success_rate": success_rate,
            "failures": stats.get("failed", 0),
            "missing_menus": missing_menus,
        }

        json_path = self.output / "report.json"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        txt_path = self.output / "report.txt"
        txt_path.write_text(self._to_text(payload), encoding="utf-8")

        issue_rows = "\n".join(
            f"<tr><td>{i.name}</td><td>{i.code}</td><td>{i.severity}</td><td>{i.message}</td></tr>"
            for i in issues
        ) or "<tr><td colspan='4'>No issues</td></tr>"

        html = HTML_TEMPLATE.format(
            generated_at=payload["generated_at"],
            restaurants=stats.get("restaurants", 0),
            menus=stats.get("menus", 0),
            menu_items=stats.get("menu_items", 0),
            photos_downloaded=stats.get("photos_downloaded", 0),
            failed=stats.get("failed", 0),
            success_rate=success_rate,
            elapsed=elapsed,
            missing_menus=missing_menus,
            issue_rows=issue_rows,
        )
        html_path = self.output / "report.html"
        html_path.write_text(html, encoding="utf-8")

        logger.info("Reports written to {}", self.output)
        return {
            "report.json": str(json_path),
            "report.txt": str(txt_path),
            "report.html": str(html_path),
        }

    def _to_text(self, payload: dict) -> str:
        stats = payload["stats"]
        lines = [
            "Restaurant Crawler Report",
            f"Location: {payload['city']}, {payload['state']}, {payload['country']}",
            f"Generated: {payload['generated_at']}",
            "",
            f"Restaurants found: {stats.get('restaurants', 0)}",
            f"Menus found: {stats.get('menus', 0)}",
            f"Menu items: {stats.get('menu_items', 0)}",
            f"Photos downloaded: {stats.get('photos_downloaded', 0)}",
            f"Failures: {payload.get('failures', 0)}",
            f"Missing menus: {payload.get('missing_menus', 0)}",
            f"Execution time (s): {payload.get('execution_time_seconds', 0)}",
            f"Success rate (%): {payload.get('success_rate', 0)}",
        ]
        return "\n".join(lines) + "\n"
