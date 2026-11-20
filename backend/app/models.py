from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


Granularity = Literal["daily", "weekly", "monthly"]


class DashboardFilters(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    outlet: list[str] = Field(default_factory=list)
    brand: list[str] = Field(default_factory=list)
    group: list[str] = Field(default_factory=list)
    order_type: list[str] = Field(default_factory=list)
    settlement: list[str] = Field(default_factory=list)
    granularity: Granularity = "daily"

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class Kpis(BaseModel):
    total_records: int = 0
    total_orders: int = 0
    total_revenue: float = 0.0
    units_sold: float = 0.0
    average_order_value: float = 0.0
    average_units_per_order: float = 0.0


class DashboardResponse(BaseModel):
    generated_at: str
    filters: DashboardFilters
    kpis: Kpis
    trend: list[dict]
    category: list[dict]
    order_type: list[dict]
    outlets: list[dict]
    top_items: list[dict]
    has_data: bool
    query_ms: float

