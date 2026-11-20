from __future__ import annotations

import io
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.models import DashboardFilters
from app.services.data_store import DataStore


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    store = DataStore(resolved)
    app = FastAPI(title=resolved.app_name, version="1.0.0")
    app.state.store = store
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    def get_store() -> DataStore:
        return app.state.store

    @app.get("/api/health")
    def health(store: DataStore = Depends(get_store)):
        return {"status": "ok", "dataset": store.data_path.name, "records": store.metadata.get("processed_row_count")}

    @app.get("/api/meta")
    def meta(store: DataStore = Depends(get_store)):
        return store.metadata

    @app.get("/api/filters")
    def filters(store: DataStore = Depends(get_store)):
        metadata = store.metadata
        return {
            "date_range": {"min": metadata.get("date_min"), "max": metadata.get("date_max")},
            "options": store.filter_options(),
        }

    def make_filters(
        start_date: date | None = Query(None),
        end_date: date | None = Query(None),
        outlet: list[str] = Query(default=[]),
        brand: list[str] = Query(default=[]),
        group: list[str] = Query(default=[]),
        order_type: list[str] = Query(default=[]),
        settlement: list[str] = Query(default=[]),
        granularity: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    ) -> DashboardFilters:
        return DashboardFilters(
            start_date=start_date,
            end_date=end_date,
            outlet=outlet,
            brand=brand,
            group=group,
            order_type=order_type,
            settlement=settlement,
            granularity=granularity,  # type: ignore[arg-type]
        )

    @app.get("/api/dashboard")
    def dashboard(
        dashboard_filters: DashboardFilters = Depends(make_filters),
        store: DataStore = Depends(get_store),
    ):
        try:
            return store.dashboard(dashboard_filters)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/export.csv")
    def export_csv(
        dashboard_filters: DashboardFilters = Depends(make_filters),
        store: DataStore = Depends(get_store),
    ):
        frame = store.export_frame(dashboard_filters)
        buffer = io.StringIO()
        frame.to_csv(buffer, index=False)
        buffer.seek(0)
        headers = {"Content-Disposition": 'attachment; filename="business-analytics-export.csv"'}
        return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers=headers)

    static_dir = resolved.static_dir.resolve()
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found")
            candidate = static_dir / full_path
            if candidate.is_file() and static_dir in candidate.resolve().parents:
                return FileResponse(candidate)
            index = static_dir / "index.html"
            if index.exists():
                return FileResponse(index)
            raise HTTPException(status_code=404, detail="Not found")

    return app


app = create_app()

