from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

import duckdb
import pandas as pd

from app.config import Settings
from app.models import DashboardFilters


class TTLCache:
    def __init__(self, ttl_seconds: int, max_entries: int):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._items: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._items.get(key)
            if not item:
                return None
            expires, value = item
            if expires <= time.monotonic():
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._items[key] = (time.monotonic() + self.ttl_seconds, value)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)


class DataStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.data_path = settings.data_path.resolve()
        self.metadata_path = settings.metadata_path.resolve()
        if not self.data_path.exists():
            raise FileNotFoundError(f"Processed dataset not found: {self.data_path}")
        self.metadata = self._read_metadata()
        self.cache = TTLCache(settings.cache_ttl_seconds, settings.cache_max_entries)
        self._filter_cache: dict[str, list[str]] | None = None
        self._filter_lock = threading.Lock()

    def _read_metadata(self) -> dict[str, Any]:
        if self.metadata_path.exists():
            return json.loads(self.metadata_path.read_text(encoding="utf-8"))
        return {}

    def connection(self):
        conn = duckdb.connect(database=":memory:")
        conn.execute("PRAGMA threads=4")
        return conn

    def _where_clause(self, filters: DashboardFilters) -> tuple[str, list[Any]]:
        clauses = ["1 = 1"]
        params: list[Any] = [str(self.data_path)]
        if filters.start_date:
            clauses.append("order_date >= ?")
            params.append(filters.start_date)
        if filters.end_date:
            clauses.append("order_date <= ?")
            params.append(filters.end_date)
        for column, values in (
            ("Outlet_Name", filters.outlet),
            ("Brand", filters.brand),
            ("Group", filters.group),
            ("Order_Type", filters.order_type),
            ("Settlement", filters.settlement),
        ):
            if values:
                placeholders = ", ".join("?" for _ in values)
                clauses.append(f'"{column}" IN ({placeholders})')
                params.extend(values)
        return " AND ".join(clauses), params

    def filter_options(self) -> dict[str, list[str]]:
        with self._filter_lock:
            if self._filter_cache is not None:
                return self._filter_cache
            conn = self.connection()
            try:
                result: dict[str, list[str]] = {}
                for key, column in (
                    ("outlet", "Outlet_Name"),
                    ("brand", "Brand"),
                    ("group", "Group"),
                    ("order_type", "Order_Type"),
                    ("settlement", "Settlement"),
                ):
                    rows = conn.execute(
                        f'SELECT DISTINCT "{column}" FROM read_parquet(?) WHERE "{column}" IS NOT NULL ORDER BY 1',
                        [str(self.data_path)],
                    ).fetchall()
                    result[key] = [str(row[0]) for row in rows]
                self._filter_cache = result
                return result
            finally:
                conn.close()

    @staticmethod
    def _frame_to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
        if frame.empty:
            return []
        frame = frame.where(pd.notna(frame), None)
        return json.loads(frame.to_json(orient="records", date_format="iso"))

    def dashboard(self, filters: DashboardFilters) -> dict[str, Any]:
        cache_key = json.dumps(filters.model_dump(mode="json"), sort_keys=True)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        started = time.perf_counter()
        where, params = self._where_clause(filters)
        # The first parameter is the Parquet path. Every query uses a fresh connection
        # so concurrent requests remain isolated without sharing DuckDB connections.
        base = f"WITH filtered AS (SELECT * FROM read_parquet(?) WHERE {where.replace('1 = 1 AND ', '', 1)}) "
        conn = self.connection()
        try:
            total_records, total_orders, total_revenue, units_sold = conn.execute(
                base + """
                    SELECT COUNT(*), COUNT(DISTINCT BillNo), COALESCE(SUM(line_revenue), 0), COALESCE(SUM(Quantity), 0)
                    FROM filtered
                """,
                params,
            ).fetchone()
            total_orders = int(total_orders or 0)
            total_revenue = float(total_revenue or 0)
            units_sold = float(units_sold or 0)

            trend_period = {
                "daily": "DATE_TRUNC('day', order_datetime)::DATE",
                "weekly": "DATE_TRUNC('week', order_datetime)::DATE",
                "monthly": "DATE_TRUNC('month', order_datetime)::DATE",
            }[filters.granularity]

            def query_rows(select_sql: str) -> list[dict[str, Any]]:
                return self._frame_to_records(conn.execute(base + select_sql, params).fetchdf())

            trend = query_rows(f"""
                SELECT {trend_period} AS period, COALESCE(SUM(line_revenue), 0) AS revenue,
                       COUNT(DISTINCT BillNo) AS orders, COALESCE(SUM(Quantity), 0) AS units
                FROM filtered GROUP BY 1 ORDER BY 1
            """)
            category = query_rows("""
                SELECT \"Group\" AS name, COALESCE(SUM(line_revenue), 0) AS revenue,
                       COUNT(DISTINCT BillNo) AS orders, COALESCE(SUM(Quantity), 0) AS units
                FROM filtered GROUP BY 1 ORDER BY revenue DESC
            """)
            order_type = query_rows("""
                SELECT \"Order_Type\" AS name, COALESCE(SUM(line_revenue), 0) AS revenue,
                       COUNT(DISTINCT BillNo) AS orders, COUNT(*) AS records
                FROM filtered GROUP BY 1 ORDER BY revenue DESC
            """)
            outlets = query_rows("""
                SELECT \"Outlet_Name\" AS name, COALESCE(SUM(line_revenue), 0) AS revenue,
                       COUNT(DISTINCT BillNo) AS orders, COALESCE(SUM(Quantity), 0) AS units
                FROM filtered GROUP BY 1 ORDER BY revenue DESC
            """)
            top_items = query_rows("""
                SELECT Item AS name, COALESCE(SUM(line_revenue), 0) AS revenue,
                       COALESCE(SUM(Quantity), 0) AS units, COUNT(*) AS records
                FROM filtered GROUP BY 1 ORDER BY revenue DESC LIMIT 8
            """)
        finally:
            conn.close()

        result = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "filters": filters.model_dump(mode="json"),
            "kpis": {
                "total_records": int(total_records or 0),
                "total_orders": total_orders,
                "total_revenue": total_revenue,
                "units_sold": units_sold,
                "average_order_value": total_revenue / total_orders if total_orders else 0,
                "average_units_per_order": units_sold / total_orders if total_orders else 0,
            },
            "trend": trend,
            "category": category,
            "order_type": order_type,
            "outlets": outlets,
            "top_items": top_items,
            "has_data": bool(total_records),
            "query_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        self.cache.set(cache_key, result)
        return result

    def export_frame(self, filters: DashboardFilters) -> pd.DataFrame:
        where, params = self._where_clause(filters)
        query = f"""
            SELECT BillNo, Outlet_Name, order_datetime AS Order_Datetime, \"Group\", Order_Type,
                   Item, Price, Quantity, line_revenue, Settlement, Brand, order_date,
                   order_month, order_year, order_weekday, order_hour
            FROM read_parquet(?) WHERE {where.replace('1 = 1 AND ', '', 1)}
            ORDER BY order_datetime, BillNo
        """
        conn = self.connection()
        try:
            return conn.execute(query, params).fetchdf()
        finally:
            conn.close()

