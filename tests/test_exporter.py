"""CSV exporter tests."""

from pathlib import Path

import pandas as pd

from restaurant_crawler.exporters.csv_exporter import CsvExporter
from restaurant_crawler.models.restaurant import Restaurant


def test_csv_export(settings, repo):
    repo.upsert_restaurant(
        Restaurant(
            name="Export Cafe",
            address="Manaíra",
            latitude=-7.1,
            longitude=-34.84,
            phone="83900001111",
        )
    )
    paths = CsvExporter(settings, repo).export_all()
    restaurants_csv = Path(paths["restaurants.csv"])
    assert restaurants_csv.exists()
    df = pd.read_csv(restaurants_csv)
    assert len(df) == 1
    assert df.iloc[0]["name"] == "Export Cafe"
