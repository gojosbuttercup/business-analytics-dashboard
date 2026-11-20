from pathlib import Path

import duckdb
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


ROOT = Path(__file__).resolve().parents[2]


def client() -> TestClient:
    settings = Settings(
        data_path=ROOT / "data/processed/sales.parquet",
        metadata_path=ROOT / "data/processed/metadata.json",
        static_dir=ROOT / "backend/static",
    )
    return TestClient(create_app(settings))


def test_health_and_metadata():
    api = client()
    health = api.get("/api/health")
    assert health.status_code == 200
    assert health.json()["records"] == 300000

    metadata = api.get("/api/meta")
    assert metadata.status_code == 200
    assert metadata.json()["distinct_orders"] == 110478
    assert metadata.json()["date_min"] == "2025-06-17"
    assert metadata.json()["date_max"] == "2026-06-16"


def test_full_dashboard_matches_independent_duckdb_totals():
    api = client()
    payload = api.get("/api/dashboard?start_date=2025-06-17&end_date=2026-06-16").json()
    conn = duckdb.connect()
    expected = conn.execute(
        """
        SELECT COUNT(*), COUNT(DISTINCT BillNo), SUM(line_revenue), SUM(Quantity)
        FROM read_parquet(?)
        """,
        [str(ROOT / "data/processed/sales.parquet")],
    ).fetchone()
    conn.close()
    assert payload["kpis"]["total_records"] == expected[0]
    assert payload["kpis"]["total_orders"] == expected[1]
    assert payload["kpis"]["total_revenue"] == expected[2]
    assert payload["kpis"]["units_sold"] == expected[3]
    assert payload["kpis"]["average_order_value"] == expected[2] / expected[1]


def test_filters_are_composable_and_order_count_is_distinct():
    api = client()
    response = api.get(
        "/api/dashboard?start_date=2025-06-17&end_date=2025-06-17&outlet=MG%20Road&group=Burgers&order_type=Delivery"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["kpis"]["total_records"] > payload["kpis"]["total_orders"]
    assert payload["category"][0]["name"] == "Burgers"
    assert all(row["name"] == "Delivery" for row in payload["order_type"])


def test_empty_results_are_valid_and_export_is_filtered():
    api = client()
    response = api.get("/api/dashboard?start_date=2030-01-01&end_date=2030-01-02")
    assert response.status_code == 200
    assert response.json()["has_data"] is False
    assert response.json()["kpis"]["total_orders"] == 0

    query = "start_date=2025-06-17&end_date=2025-06-17&group=Burgers"
    filtered_dashboard = api.get(f"/api/dashboard?{query}").json()
    export = api.get(f"/api/export.csv?{query}")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert "line_revenue" in export.text.splitlines()[0]
    assert len(export.text.splitlines()) - 1 == filtered_dashboard["kpis"]["total_records"]

