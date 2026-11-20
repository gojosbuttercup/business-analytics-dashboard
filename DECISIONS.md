# Engineering Decisions

## Parquet plus DuckDB

The source workbook is convenient for delivery but inefficient as a live query surface. The ETL creates one typed Parquet file with derived fields. DuckDB can scan only the columns needed by each aggregation and keeps the deployment footprint small. A traditional database would be reasonable for high-write workloads, but this dashboard reads a static analytical dataset and benefits from file-based deployment.

## Line-item grain and order identity

Rows are not orders. The dashboard preserves every source line, computes `line_revenue`, and uses `COUNT(DISTINCT BillNo)` for orders and order-level averages. This prevents the common error of treating the 300,000 rows as 300,000 transactions.

## Date interpretation

The supplied workbook stores typed Excel datetimes, so the pipeline does not need to guess the sample's slash format. The string parser still supports both unambiguous month/day slash dates and explicit `DD-MM-YYYY HH:MM:SS`. Ambiguous string values are rejected and counted rather than silently reinterpreted.

## Request shape

One dashboard response contains all KPI and chart aggregates. This avoids a burst of independent browser requests when a user changes a filter. The backend applies one parameterized filtered CTE to each aggregation and returns only summary rows. A bounded in-process TTL cache serves repeated filter combinations without introducing Redis or another operational dependency.

## Deployment shape

A single Render Docker service is the lowest-complexity deployment that still serves the real dataset. The frontend build is copied into FastAPI's static directory, and the processed Parquet file is packaged with the image. The raw workbook is not required at runtime and is excluded from the Docker context.

## Trade-offs

- The dashboard uses a simple bounded process cache instead of distributed caching; this keeps the assessment-sized deployment understandable.
- CSV export is intentionally more permissive than dashboard queries because the user explicitly asks for filtered detail export.
- The UI favors a compact set of decision-useful charts over a dense BI suite, keeping the dashboard responsive and within the stated development window.

