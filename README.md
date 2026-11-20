# Business Analytics Dashboard

Business Analytics is a production-oriented dashboard for exploring 300,000 restaurant sales line items. It keeps the source at line-item grain, calculates revenue as `Price × Quantity`, and uses server-side DuckDB aggregations so the browser never receives the full dataset.

## Current source findings

The supplied workbook contains one worksheet and 300,000 data rows with the expected columns: `BillNo`, `Outlet_Name`, `Order_Datetime`, `Group`, `Order_Type`, `Item`, `Price`, `Quantity`, `Settlement`, and `Brand`.

- Date range: `2025-06-17 11:02:40` through `2026-06-16 23:48:34`.
- Processed records: 300,000. Distinct orders: 110,478.
- Missing required values: none. Invalid numeric values: none. Negative prices or quantities: none.
- Zero-price rows: 8,611. These are preserved and reported, not silently changed.
- Fully duplicated rows: none. Repeated `BillNo` values are legitimate multi-line orders; the maximum bill has 6 line items.
- `BillNo` does not cross outlets or calendar dates in this source.

## Features

- KPI cards for line-item records, distinct orders, revenue, units, average order value, and average units per order.
- Daily, weekly, and monthly revenue trend.
- Revenue by menu category, order type distribution, outlet performance, and top-selling items.
- Date, outlet, brand, category, order type, and settlement filters with combined semantics.
- Empty, loading, and error states; responsive desktop/tablet/mobile layout.
- Filtered CSV export.
- 60-second bounded in-process cache for repeated dashboard filter combinations.

## Architecture

```text
Excel / CSV source
        |
        v
scripts/process_data.py  ->  data/processed/sales.parquet + metadata.json
        |
        v
FastAPI -> DuckDB read_parquet() -> aggregated JSON / CSV
        |
        v
React + Vite + TypeScript + Tailwind + Recharts
```

Parquet is the deployment artifact because it is compact, typed, columnar, and directly queryable by DuckDB. DuckDB was selected instead of loading a large dataframe per request because it provides efficient SQL aggregation over Parquet with a small operational footprint. Each request uses its own DuckDB connection, which keeps concurrent requests isolated.

## Data assumptions and date parsing

The supplied workbook stores every `Order_Datetime` cell as a true Excel datetime with an `m/d/yy h:mm` display format. The ETL therefore preserves those typed values and does not infer a string format for this source. For future Excel/CSV inputs, string values are accepted when they are unambiguous slash-formatted month/day dates or the documented `DD-MM-YYYY HH:MM:SS` format. Ambiguous slash dates are counted as data-quality issues and excluded from derived dates rather than silently guessed.

Prices are interpreted as Indian rupees because the assessment describes Indian outlets. Revenue is the sum of `Price × Quantity` at line-item grain. Total orders is `COUNT(DISTINCT BillNo)`, never a row count. Filters select matching line items first; revenue and units aggregate those lines, while order KPIs continue to use distinct `BillNo` values from the filtered line set.

## Local setup

Requirements: Python 3.12+, Node.js 20+, and npm.

```powershell
# From the repository root
python -m pip install -r backend/requirements.txt
python scripts/process_data.py data/data.xlsx --output-dir data/processed

# Terminal 1
$env:PYTHONPATH = "backend"
uvicorn app.main:app --app-dir backend --reload --port 8000

# Terminal 2
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite development server proxies `/api` to FastAPI.

## ETL and checks

Run the pipeline whenever the source workbook changes:

```powershell
python scripts/process_data.py data/data.xlsx --output-dir data/processed
```

The current measured ETL run processed 300,000 rows in 37.233 seconds and produced a 4,337,611-byte Snappy Parquet file. The run writes the original and processed row counts, date parsing counts, numeric quality counts, duplicate counts, and assumptions to `data/processed/metadata.json`.

## API

- `GET /api/health` — service and dataset health.
- `GET /api/meta` — ETL metadata, date range, row counts, and data-quality summary.
- `GET /api/filters` — date range and distinct filter options.
- `GET /api/dashboard` — filtered KPI cards and all chart aggregations. Query parameters include `start_date`, `end_date`, repeated `outlet`, `brand`, `group`, `order_type`, `settlement`, and `granularity=daily|weekly|monthly`.
- `GET /api/export.csv` — filtered line-item export including derived revenue and date fields.

## Tests and production build

```powershell
$env:PYTHONPATH = "backend"
pytest backend/tests -q
cd frontend
npm run build
```

The backend test suite checks independent KPI reconciliation, distinct order behavior, combined filters, empty results, health/meta, and CSV export. The frontend build runs TypeScript validation and the Vite production bundle.

Representative local API checks returned HTTP 200 for health, metadata, filters, full dashboard, combined filters, empty results, and export. The response payload includes the measured DuckDB query duration as `query_ms`; this value is rendered in the dashboard footer.

## Deployment

The repository includes a single-service `Dockerfile` and `render.yaml`. The image builds the frontend, installs the FastAPI runtime, packages the processed Parquet dataset, and serves the Vite build through FastAPI. Render can deploy it as a Docker web service and will provide the assigned `PORT` automatically. The health check is `/api/health`.

```powershell
docker build -t business-analytics-dashboard .
docker run --rm -p 8000:8000 business-analytics-dashboard
```

No deployment credentials or configured hosting account were available in this workspace, so no live URL is claimed. After connecting the repository in Render, select the included `render.yaml` or create the Docker web service and verify `/api/health` before adding the resulting URL here.

## Submission status

- GitHub repository URL: not created in this workspace because GitHub CLI is not installed or authenticated.
- Live application URL: not deployed or claimed.
- The processed Parquet file is intentionally included because the deployed service must load the real dataset without relying on a local Excel file. The original workbook is excluded by `.gitignore` and `.dockerignore`.

## Known limitations

- The dataset is treated as immutable at runtime; reprocessing is an explicit ETL step.
- The cache is per process, which is appropriate for the single-service deployment. A multi-instance deployment would need shared caching or would accept per-instance caches.
- CSV export materializes the selected filtered result server-side before streaming it. Dashboard requests remain aggregated and bounded.
- The source has one brand, so the brand filter is implemented but currently has one option.

