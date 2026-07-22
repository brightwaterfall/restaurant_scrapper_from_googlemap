# Restaurant Crawler — João Pessoa, Paraíba, Brazil

Production-ready Python crawler that discovers publicly mapped restaurants in **João Pessoa**, enriches them from official websites when available, extracts menus (HTML / PDF / image+OCR), downloads high-resolution photos, stores results in **SQLite**, and exports **UTF-8 CSV** plus HTML/JSON/TXT reports.

## Features

- Public discovery via OpenStreetMap **Overpass API** (amenities: restaurant, cafe, fast_food, etc.)
- Optional Nominatim reverse geocoding for missing addresses
- Website type detection (static HTML vs dynamic / SPA)
- **BeautifulSoup** for static pages, **Playwright** for dynamic pages
- Infinite scroll + pagination handling
- Menu extraction from HTML, PDF (`pdfplumber` / PyMuPDF), and images (Tesseract OCR)
- Image download with thumbnail avoidance and `RestaurantName_001.jpg` naming
- Deduplication with **RapidFuzz** (90% threshold) + fingerprinting
- Resume interrupted jobs
- Polite crawling: concurrency limits, delays, robots.txt respect
- Retries (5x, exponential backoff), 30s timeout
- Validation report + crawl statistics
- Typer CLI: `crawl`, `export`, `validate`, `images`, `menus`, `resume`

## Requirements

- Python **3.12+**
- Tesseract OCR (optional, for image menus)
- Chromium for Playwright

### Windows Tesseract

Install from https://github.com/UB-Mannheim/tesseract/wiki and optionally set `ocr.tesseract_cmd` in `config.yaml`.

## Installation

```bash
cd restaurant-scrapper
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

## Configuration

Edit `restaurant_crawler/config/config.yaml`:

| Key | Description |
|---|---|
| `city` / `state` / `country` | Target location |
| `geo.*` | Bounding box for discovery |
| `max_concurrent` | Concurrent restaurant scrapes |
| `timeout` | HTTP timeout (seconds) |
| `request_delay` | Per-host polite delay |
| `respect_robots_txt` | Honor robots.txt |
| `headless` | Playwright headless mode |
| `dedup_threshold` | RapidFuzz similarity (default 90) |
| `output_folder` | CSV / report output |
| `database_path` | SQLite file |
| `log_level` | Loguru level |

## Folder structure

```
restaurant-scrapper/
├── main.py
├── requirements.txt
├── README.md
├── pytest.ini
├── tests/
└── restaurant_crawler/
    ├── config/          # config.yaml + Settings
    ├── crawler/         # discovery, browser, engine, resume, scrapy spider
    ├── extractors/      # contact, social, hours, images, website
    ├── menus/           # HTML / PDF / OCR parsers
    ├── images/          # download + Pillow processing
    ├── pipelines/       # validation
    ├── database/        # schema, connection, repository
    ├── models/          # Pydantic models
    ├── exporters/       # CSV + reports
    ├── utils/           # http, robots, dedupe, normalize, logging
    ├── data/            # SQLite, images, menus, state
    ├── exports/         # CSV + reports
    └── logs/
```

## Execution

```bash
# Full crawl (discover + scrape + export + validate)
python main.py crawl

# Resume interrupted run
python main.py resume

# Export CSV only
python main.py export

# Validate + write reports
python main.py validate

# Retry menus / images only
python main.py menus
python main.py images

# Database stats
python main.py stats
```

Custom config:

```bash
python main.py --config path/to/config.yaml crawl
```

## Outputs

### SQLite (`restaurant_crawler/data/restaurants.db`)

Tables: `restaurants`, `menus`, `menu_items`, `photos`, `sources`, `crawl_logs`, `crawl_state`

### CSV (`restaurant_crawler/exports/`)

- `restaurants.csv`
- `menus.csv`
- `menu_items.csv`
- `photos.csv`
- `sources.csv`

### Reports

- `report.html`
- `report.json`
- `report.txt`

### Images

`restaurant_crawler/data/images/<restaurant-slug>/<slug>_001.jpg`

## Data fields collected

Restaurant name, address, latitude/longitude, Google Maps URL, website, phone, email, Facebook, Instagram, delivery platforms, categories, opening hours, complete menu (category, item, description, price, currency, notes, availability), high-resolution photos, source URLs.

## Architecture notes

1. **Discovery** — Overpass query inside João Pessoa bbox → Restaurant + Source rows
2. **Dedup** — fingerprint + RapidFuzz name/address/geo/phone/website
3. **Website scrape** — detect static vs dynamic → extract contact/social/hours/images/menu links
4. **Menus** — HTML first; PDF/image when linked; OCR only for image menus
5. **Persist** — SQLite upserts; state file for resume
6. **Export / validate** — Pandas CSV + validation pipeline + reports

## Tests

```bash
pytest -q
```

Coverage includes unit, parser, database, exporter, validation, and extractor tests.

## Troubleshooting

| Issue | Fix |
|---|---|
| Overpass timeout / empty discovery | Re-run later; Overpass can rate-limit. Increase `discovery.overpass_timeout`. |
| Playwright missing browser | `playwright install chromium` |
| OCR not working | Install Tesseract; set `ocr.tesseract_cmd`; ensure `por` language data |
| Many missing menus | Expected for OSM POIs without websites or without structured menus |
| robots.txt blocks | Leave `respect_robots_txt: true` (recommended). Only disable for local debugging. |
| Resume not picking jobs | Pending statuses are `discovered` and `failed` — check `python main.py stats` |

## Legal / ethics

Crawl only publicly available information. Respect `robots.txt`, site terms of use, and local laws. Keep concurrency and delays conservative. This project does not bypass authentication, CAPTCHAs, or access controls.

## Example session

```bash
pip install -r requirements.txt
playwright install chromium
python main.py crawl
python main.py stats
```

Open `restaurant_crawler/exports/report.html` for a summary.
