from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = [
    "BillNo", "Outlet_Name", "Order_Datetime", "Group", "Order_Type",
    "Item", "Price", "Quantity", "Settlement", "Brand",
]


def parse_date_values(series: pd.Series) -> tuple[pd.Series, dict[str, int]]:
    quality = {"invalid_datetime": 0, "ambiguous_datetime": 0, "slash_mdy_datetime": 0, "documented_dmy_datetime": 0}
    if pd.api.types.is_datetime64_any_dtype(series):
        parsed = pd.to_datetime(series, errors="coerce")
        quality["invalid_datetime"] = int(parsed.isna().sum())
        return parsed, quality

    values = series.astype("string").str.strip()
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    ambiguous_indices = pd.Index([])
    slash = values.str.match(r"^\d{1,2}/\d{1,2}/\d{2,4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?$").fillna(False)
    documented = values.str.match(r"^\d{1,2}-\d{1,2}-\d{4}\s+\d{1,2}:\d{2}:\d{2}$").fillna(False)

    if slash.any():
        slash_values = values[slash]
        mdy = pd.to_datetime(slash_values, errors="coerce", format="mixed", dayfirst=False)
        dmy = pd.to_datetime(slash_values, errors="coerce", format="mixed", dayfirst=True)
        ambiguous = mdy.notna() & dmy.notna() & (mdy != dmy)
        quality["ambiguous_datetime"] = int(ambiguous.sum())
        ambiguous_indices = slash_values.index[ambiguous]
        accepted = mdy.copy()
        accepted[ambiguous] = pd.NaT
        parsed.loc[slash_values.index] = accepted
        quality["slash_mdy_datetime"] = int(accepted.notna().sum())

    if documented.any():
        accepted = pd.to_datetime(values[documented], errors="coerce", format="%d-%m-%Y %H:%M:%S")
        parsed.loc[accepted.index] = accepted
        quality["documented_dmy_datetime"] = int(accepted.notna().sum())

    remaining = parsed.isna() & values.notna() & ~parsed.index.isin(ambiguous_indices)
    if remaining.any():
        fallback = pd.to_datetime(values[remaining], errors="coerce", format="mixed")
        parsed.loc[fallback.index] = fallback
    quality["invalid_datetime"] = int(parsed.isna().sum())
    return parsed, quality


def normalize_bill_no(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().all() and (numeric % 1 == 0).all():
        return numeric.astype("int64").astype("string")
    return series.astype("string").str.strip()


def process_source(source: Path, output_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    if source.suffix.lower() in {".xlsx", ".xls"}:
        frame = pd.read_excel(source, engine="openpyxl" if source.suffix.lower() == ".xlsx" else None)
    elif source.suffix.lower() == ".csv":
        frame = pd.read_csv(source)
    else:
        raise ValueError(f"Unsupported source type: {source.suffix}")

    frame.columns = [str(column).strip() for column in frame.columns]
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
    frame = frame[REQUIRED_COLUMNS].copy()
    source_row_count = len(frame)
    quality: dict[str, Any] = {
        "missing_by_column": {column: int(frame[column].isna().sum()) for column in REQUIRED_COLUMNS},
        "invalid_numeric_by_column": {},
        "negative_price_rows": 0,
        "negative_quantity_rows": 0,
        "zero_price_rows": 0,
        "duplicate_full_rows": int(frame.duplicated(keep=False).sum()),
    }

    frame["BillNo"] = normalize_bill_no(frame["BillNo"])
    for column in ["Outlet_Name", "Group", "Order_Type", "Item", "Settlement", "Brand"]:
        frame[column] = frame[column].astype("string").str.strip()
    frame["Order_Datetime"], date_quality = parse_date_values(frame["Order_Datetime"])
    quality.update(date_quality)
    for column in ["Price", "Quantity"]:
        original_missing = frame[column].isna()
        numeric = pd.to_numeric(frame[column], errors="coerce")
        quality["invalid_numeric_by_column"][column] = int((numeric.isna() & ~original_missing).sum())
        frame[column] = numeric
    quality["negative_price_rows"] = int((frame["Price"] < 0).sum())
    quality["negative_quantity_rows"] = int((frame["Quantity"] < 0).sum())
    quality["zero_price_rows"] = int((frame["Price"] == 0).sum())

    frame["line_revenue"] = frame["Price"] * frame["Quantity"]
    frame["order_date"] = frame["Order_Datetime"].dt.date
    frame["order_month"] = frame["Order_Datetime"].dt.to_period("M").astype("string")
    frame["order_year"] = frame["Order_Datetime"].dt.year.astype("Int64")
    frame["order_weekday"] = frame["Order_Datetime"].dt.day_name().astype("string")
    frame["order_hour"] = frame["Order_Datetime"].dt.hour.astype("Int64")

    output_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = output_dir / "sales.parquet"
    frame.to_parquet(parquet_path, index=False, engine="pyarrow", compression="snappy")
    metadata = {
        "source_file": source.name,
        "source_row_count": source_row_count,
        "processed_row_count": len(frame),
        "columns": list(frame.columns),
        "date_min": frame["Order_Datetime"].min().date().isoformat() if frame["Order_Datetime"].notna().any() else None,
        "date_max": frame["Order_Datetime"].max().date().isoformat() if frame["Order_Datetime"].notna().any() else None,
        "timestamp_min": frame["Order_Datetime"].min().isoformat() if frame["Order_Datetime"].notna().any() else None,
        "timestamp_max": frame["Order_Datetime"].max().isoformat() if frame["Order_Datetime"].notna().any() else None,
        "distinct_orders": int(frame["BillNo"].nunique(dropna=True)),
        "data_quality": quality,
        "parquet_size_bytes": parquet_path.stat().st_size,
        "etl_seconds": round(time.perf_counter() - started, 3),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "currency_assumption": "INR (₹), based on the assessment's Indian outlet context",
        "date_parsing": "Excel datetime cells are preserved. String inputs accept unambiguous slash-formatted month/day values and DD-MM-YYYY HH:MM:SS; ambiguous string values are logged and excluded from processed dates.",
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize the business analytics source into Parquet.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()
    metadata = process_source(args.source, args.output_dir)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()

