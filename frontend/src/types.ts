export type Granularity = "daily" | "weekly" | "monthly";

export type FilterState = {
  start_date: string;
  end_date: string;
  outlet: string[];
  brand: string[];
  group: string[];
  order_type: string[];
  settlement: string[];
  granularity: Granularity;
};

export type Meta = {
  source_file: string;
  source_row_count: number;
  processed_row_count: number;
  distinct_orders: number;
  date_min: string;
  date_max: string;
  timestamp_min: string;
  timestamp_max: string;
  parquet_size_bytes: number;
  etl_seconds: number;
  generated_at: string;
};

export type FilterOptions = {
  date_range: { min: string; max: string };
  options: Record<"outlet" | "brand" | "group" | "order_type" | "settlement", string[]>;
};

export type Kpis = {
  total_records: number;
  total_orders: number;
  total_revenue: number;
  units_sold: number;
  average_order_value: number;
  average_units_per_order: number;
};

export type DashboardData = {
  generated_at: string;
  filters: FilterState;
  kpis: Kpis;
  trend: { period: string; revenue: number; orders: number; units: number }[];
  category: { name: string; revenue: number; orders: number; units: number }[];
  order_type: { name: string; revenue: number; orders: number; records: number }[];
  outlets: { name: string; revenue: number; orders: number; units: number }[];
  top_items: { name: string; revenue: number; units: number; records: number }[];
  has_data: boolean;
  query_ms: number;
};

