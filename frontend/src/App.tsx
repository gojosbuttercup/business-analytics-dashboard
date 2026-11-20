import { useEffect, useMemo, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  BarChart3, CalendarDays, Check, ChevronDown, CircleAlert, Download,
  Filter, LayoutDashboard, RefreshCw, RotateCcw, Search, TrendingUp,
} from "lucide-react";
import { exportUrl, getDashboard, getFilters, getMeta } from "./api";
import type { DashboardData, FilterOptions, FilterState, Meta } from "./types";

const palette = ["#0f766e", "#2f9e92", "#6cb9ad", "#a4d5ca", "#d5ebe6", "#3f8f87", "#86c9bb"];
const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const number = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const oneDecimal = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 });

function dateLabel(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function initialFilters(meta?: Meta): FilterState {
  return {
    start_date: meta?.date_min ?? "",
    end_date: meta?.date_max ?? "",
    outlet: [], brand: [], group: [], order_type: [], settlement: [], granularity: "daily",
  };
}

function formatXAxis(value: string, granularity: FilterState["granularity"]) {
  const date = new Date(value.includes("T") ? value : `${value}T00:00:00`);
  return granularity === "monthly"
    ? date.toLocaleDateString("en-IN", { month: "short", year: "2-digit" })
    : date.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>;
}

function ChartHeader({ title, subtitle, action }: { title: string; subtitle: string; action?: React.ReactNode }) {
  return <div className="mb-5 flex items-start justify-between gap-3">
    <div><h2 className="text-[15px] font-semibold text-ink">{title}</h2><p className="mt-1 text-xs text-slate-500">{subtitle}</p></div>
    {action}
  </div>;
}

function Skeleton({ className = "" }: { className?: string }) { return <div className={`animate-pulse rounded-xl bg-slate-100 ${className}`} />; }

function MultiSelect({ label, values, options, onChange }: { label: string; values: string[]; options: string[]; onChange: (values: string[]) => void }) {
  const [open, setOpen] = useState(false);
  const summary = values.length ? `${values.length} selected` : "All";
  return <div className="relative min-w-[145px] flex-1">
    <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">{label}</label>
    <button type="button" onClick={() => setOpen(!open)} className="filter-control flex w-full items-center justify-between gap-2 text-left">
      <span className="truncate">{summary}</span><ChevronDown size={15} className={open ? "rotate-180 transition" : "transition"} />
    </button>
    {open && <>
      <button className="fixed inset-0 z-20 cursor-default" aria-label="Close filter" onClick={() => setOpen(false)} />
      <div className="absolute left-0 top-[64px] z-30 max-h-64 w-full min-w-[190px] overflow-auto rounded-xl border border-slate-200 bg-white p-2 shadow-xl">
        {options.map((option) => <label key={option} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm text-slate-700 hover:bg-slate-50">
          <input type="checkbox" checked={values.includes(option)} onChange={(event) => onChange(event.target.checked ? [...values, option] : values.filter((v) => v !== option))} className="h-4 w-4 rounded border-slate-300 accent-mint" />
          <span className="truncate">{option}</span>
        </label>)}
      </div>
    </>}
  </div>;
}

function Kpi({ icon: Icon, label, value, helper, accent }: { icon: typeof TrendingUp; label: string; value: string; helper: string; accent: string }) {
  return <div className="kpi-card">
    <div className="flex items-start justify-between"><div className={`icon-box ${accent}`}><Icon size={17} /></div><span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-400">Filtered</span></div>
    <p className="mt-5 text-xs font-medium text-slate-500">{label}</p><p className="mt-1 text-[25px] font-semibold tracking-tight text-ink">{value}</p><p className="mt-1 text-xs text-slate-400">{helper}</p>
  </div>;
}

function EmptyState({ message = "No records match the selected filters." }: { message?: string }) {
  return <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/50 text-center"><Search size={24} className="text-slate-300" /><p className="mt-3 text-sm font-medium text-slate-500">{message}</p><p className="mt-1 text-xs text-slate-400">Try widening the date range or clearing a filter.</p></div>;
}

function App() {
  const [meta, setMeta] = useState<Meta>();
  const [filterOptions, setFilterOptions] = useState<FilterOptions>();
  const [filters, setFilters] = useState<FilterState>(initialFilters());
  const [data, setData] = useState<DashboardData>();
  const [loading, setLoading] = useState(true);
  const [bootError, setBootError] = useState<string>();
  const [dashboardError, setDashboardError] = useState<string>();
  const [updatedAt, setUpdatedAt] = useState<Date>();

  useEffect(() => {
    Promise.all([getMeta(), getFilters()]).then(([nextMeta, nextFilters]) => {
      setMeta(nextMeta); setFilterOptions(nextFilters); setFilters(initialFilters(nextMeta));
    }).catch((error: Error) => setBootError(error.message));
  }, []);

  useEffect(() => {
    if (!filters.start_date || !filters.end_date) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true); setDashboardError(undefined);
      getDashboard(filters, controller.signal).then((next) => { setData(next); setUpdatedAt(new Date()); }).catch((error: Error) => { if (error.name !== "AbortError") setDashboardError(error.message); }).finally(() => setLoading(false));
    }, 250);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [filters]);

  const activeFilterCount = filters.outlet.length + filters.brand.length + filters.group.length + filters.order_type.length + filters.settlement.length;
  const filterLabel = useMemo(() => activeFilterCount ? `${activeFilterCount} active filter${activeFilterCount > 1 ? "s" : ""}` : "All records", [activeFilterCount]);
  const update = <K extends keyof FilterState>(key: K, value: FilterState[K]) => setFilters((current) => ({ ...current, [key]: value }));
  const clearFilters = () => setFilters(initialFilters(meta));
  const download = () => { const link = document.createElement("a"); link.href = exportUrl(filters); link.download = "business-analytics-export.csv"; link.click(); };

  const kpis = data?.kpis;
  const busy = loading || !data;

  return <div className="min-h-screen bg-cloud text-slate-900">
    <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1480px] items-center justify-between px-5 py-4 lg:px-8">
        <div className="flex items-center gap-3"><div className="brand-mark"><BarChart3 size={19} /></div><div><p className="text-sm font-bold tracking-tight text-ink">Business Analytics</p><p className="text-[11px] text-slate-500">Sales and Order Performance Overview</p></div></div>
        <div className="hidden items-center gap-5 text-right sm:flex"><div><p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-400">Dataset window</p><p className="mt-0.5 text-xs font-medium text-slate-700">{meta ? `${dateLabel(meta.date_min)} – ${dateLabel(meta.date_max)}` : "Loading dataset…"}</p></div><div className="h-7 w-px bg-slate-200" /><div><p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-400">Last updated</p><p className="mt-0.5 text-xs font-medium text-slate-700">{updatedAt ? updatedAt.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "—"}</p></div></div>
      </div>
    </header>
    <main className="mx-auto max-w-[1480px] px-5 py-7 lg:px-8 lg:py-9">
      <div className="mb-7 flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><div className="mb-2 flex items-center gap-2 text-xs font-semibold text-mint"><LayoutDashboard size={14} /> Operational snapshot</div><h1 className="text-[27px] font-semibold tracking-tight text-ink sm:text-[31px]">Revenue and order performance</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">A focused view of what is selling, where revenue is coming from, and how customers are ordering.</p></div><div className="flex items-center gap-2"><button className="button-secondary" onClick={clearFilters}><RotateCcw size={15} /> Clear filters</button><button className="button-primary" onClick={download}><Download size={15} /> Export CSV</button></div></div>
      {bootError && <div className="mb-6 flex items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"><CircleAlert size={17} /> Unable to load dataset metadata: {bootError}</div>}
      <Card className="mb-6"><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2 text-sm font-semibold text-ink"><Filter size={16} className="text-mint" /> Filters <span className="ml-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500">{filterLabel}</span></div><div className="flex items-center gap-2 text-xs text-slate-400"><CalendarDays size={14} /> Date range includes both endpoints</div></div>
        <div className="flex flex-col gap-3 xl:flex-row"><div className="grid flex-1 grid-cols-2 gap-3 lg:grid-cols-4 xl:grid-cols-2"><div><label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">From</label><input type="date" value={filters.start_date} min={meta?.date_min} max={filters.end_date || meta?.date_max} onChange={(e) => update("start_date", e.target.value)} className="filter-control w-full" /></div><div><label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">To</label><input type="date" value={filters.end_date} min={filters.start_date || meta?.date_min} max={meta?.date_max} onChange={(e) => update("end_date", e.target.value)} className="filter-control w-full" /></div></div><div className="grid flex-[3] grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"><MultiSelect label="Outlet" values={filters.outlet} options={filterOptions?.options.outlet ?? []} onChange={(v) => update("outlet", v)} /><MultiSelect label="Brand" values={filters.brand} options={filterOptions?.options.brand ?? []} onChange={(v) => update("brand", v)} /><MultiSelect label="Category" values={filters.group} options={filterOptions?.options.group ?? []} onChange={(v) => update("group", v)} /><MultiSelect label="Order type" values={filters.order_type} options={filterOptions?.options.order_type ?? []} onChange={(v) => update("order_type", v)} /><MultiSelect label="Settlement" values={filters.settlement} options={filterOptions?.options.settlement ?? []} onChange={(v) => update("settlement", v)} /></div></div>
      </Card>
      {dashboardError && <div className="mb-6 flex items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"><CircleAlert size={17} /> {dashboardError}</div>}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">{busy ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[165px]" />) : <> <Kpi icon={BarChart3} label="Total records" value={number.format(kpis?.total_records ?? 0)} helper="Line-item records" accent="bg-teal-50 text-mint" /><Kpi icon={TrendingUp} label="Total orders" value={number.format(kpis?.total_orders ?? 0)} helper="Distinct BillNo values" accent="bg-blue-50 text-blue-700" /><Kpi icon={TrendingUp} label="Total revenue" value={money.format(kpis?.total_revenue ?? 0)} helper="Price × quantity" accent="bg-amber-50 text-amber-700" /><Kpi icon={BarChart3} label="Units sold" value={number.format(kpis?.units_sold ?? 0)} helper="Sum of quantities" accent="bg-violet-50 text-violet-700" /><Kpi icon={TrendingUp} label="Average order value" value={money.format(kpis?.average_order_value ?? 0)} helper="Revenue ÷ distinct orders" accent="bg-rose-50 text-rose-700" /><Kpi icon={BarChart3} label="Average units / order" value={oneDecimal.format(kpis?.average_units_per_order ?? 0)} helper="Units ÷ distinct orders" accent="bg-sky-50 text-sky-700" /></>}</div>
      {!busy && !data?.has_data ? <EmptyState /> : <div className="space-y-6">
        <Card><ChartHeader title="Revenue trend" subtitle="Revenue and distinct orders over the selected period" action={<div className="segmented">{(["daily", "weekly", "monthly"] as const).map((option) => <button key={option} onClick={() => update("granularity", option)} className={filters.granularity === option ? "active" : ""}>{option[0].toUpperCase() + option.slice(1)}</button>)}</div>} />
          <div className="h-[300px]">{busy ? <Skeleton className="h-full" /> : <ResponsiveContainer width="100%" height="100%"><AreaChart data={data?.trend} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}><defs><linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#0f766e" stopOpacity={0.22} /><stop offset="100%" stopColor="#0f766e" stopOpacity={0.02} /></linearGradient></defs><CartesianGrid stroke="#e8edf2" vertical={false} /><XAxis dataKey="period" tickFormatter={(v) => formatXAxis(v, filters.granularity)} tick={{ fontSize: 11, fill: "#8491a5" }} axisLine={false} tickLine={false} minTickGap={30} /><YAxis tickFormatter={(v) => `₹${(v / 100000).toFixed(0)}L`} tick={{ fontSize: 11, fill: "#8491a5" }} axisLine={false} tickLine={false} width={45} /><Tooltip formatter={(value: number, name: string) => [name === "revenue" ? money.format(value) : number.format(value), name === "revenue" ? "Revenue" : "Orders"]} labelFormatter={(label) => formatXAxis(String(label), filters.granularity)} /><Area type="monotone" dataKey="revenue" stroke="#0f766e" strokeWidth={2.5} fill="url(#revenueFill)" dot={false} activeDot={{ r: 4, strokeWidth: 0 }} /></AreaChart></ResponsiveContainer>}</div>
        </Card>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2"><Card><ChartHeader title="Revenue by category" subtitle="Sorted by revenue from matching line items" /><div className="h-[300px]">{busy ? <Skeleton className="h-full" /> : <ResponsiveContainer width="100%" height="100%"><BarChart data={data?.category} layout="vertical" margin={{ top: 0, right: 20, left: 14, bottom: 0 }}><CartesianGrid stroke="#e8edf2" horizontal={false} /><XAxis type="number" tickFormatter={(v) => `₹${(v / 100000).toFixed(0)}L`} tick={{ fontSize: 11, fill: "#8491a5" }} axisLine={false} tickLine={false} /><YAxis dataKey="name" type="category" width={72} tick={{ fontSize: 11, fill: "#57667a" }} axisLine={false} tickLine={false} /><Tooltip formatter={(value: number) => [money.format(value), "Revenue"]} /><Bar dataKey="revenue" fill="#2f9e92" radius={[0, 5, 5, 0]} barSize={19} /></BarChart></ResponsiveContainer>}</div></Card>
          <Card><ChartHeader title="Order type distribution" subtitle="Revenue mix across service channels" /><div className="flex h-[300px] items-center">{busy ? <Skeleton className="h-full w-full" /> : <><div className="h-full flex-1"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={data?.order_type} dataKey="revenue" nameKey="name" cx="50%" cy="50%" innerRadius={67} outerRadius={103} paddingAngle={3}>{data?.order_type.map((entry, index) => <Cell key={entry.name} fill={palette[index]} />)}</Pie><Tooltip formatter={(value: number) => [money.format(value), "Revenue"]} /></PieChart></ResponsiveContainer></div><div className="w-40 space-y-3 pr-2">{data?.order_type.map((entry, index) => <div key={entry.name} className="flex items-center justify-between gap-3 text-xs"><div className="flex min-w-0 items-center gap-2"><span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: palette[index] }} /><span className="truncate text-slate-600">{entry.name}</span></div><span className="font-semibold text-ink">{money.format(entry.revenue)}</span></div>)}</div></>}</div></Card></div>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2"><Card><ChartHeader title="Outlet performance" subtitle="Revenue, distinct orders and units by outlet" /><div className="h-[320px]">{busy ? <Skeleton className="h-full" /> : <ResponsiveContainer width="100%" height="100%"><BarChart data={data?.outlets} margin={{ top: 5, right: 15, left: 0, bottom: 35 }}><CartesianGrid stroke="#e8edf2" vertical={false} /><XAxis dataKey="name" angle={-25} textAnchor="end" interval={0} tick={{ fontSize: 10, fill: "#8491a5" }} axisLine={false} tickLine={false} /><YAxis tickFormatter={(v) => `₹${(v / 100000).toFixed(0)}L`} tick={{ fontSize: 11, fill: "#8491a5" }} axisLine={false} tickLine={false} width={44} /><Tooltip formatter={(value: number, name: string) => [name === "revenue" ? money.format(value) : number.format(value), name === "revenue" ? "Revenue" : name === "orders" ? "Orders" : "Units"]} /><Bar dataKey="revenue" fill="#0f766e" radius={[5, 5, 0, 0]} barSize={35} /></BarChart></ResponsiveContainer>}</div></Card>
          <Card><ChartHeader title="Top-selling items" subtitle="Highest revenue contribution in the active view" /><div className="overflow-x-auto">{busy ? <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-8" />)}</div> : <div className="min-w-[420px]">{data?.top_items.map((item, index) => <div key={item.name} className="flex items-center gap-3 border-b border-slate-100 py-3 last:border-0"><span className="w-5 text-xs font-semibold text-slate-400">{String(index + 1).padStart(2, "0")}</span><div className="min-w-0 flex-1"><div className="flex items-center justify-between gap-3"><p className="truncate text-sm font-medium text-slate-700">{item.name}</p><p className="text-sm font-semibold text-ink">{money.format(item.revenue)}</p></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-mint" style={{ width: `${Math.max(8, (item.revenue / (data?.top_items[0]?.revenue || 1)) * 100)}%` }} /></div><p className="mt-1 text-[11px] text-slate-400">{number.format(item.units)} units · {number.format(item.records)} lines</p></div></div>)}</div>}</div></Card></div>
      </div>}
      <footer className="mt-9 flex flex-col justify-between gap-2 border-t border-slate-200 pt-4 text-xs text-slate-400 sm:flex-row"><span>Data refresh: {meta ? new Date(meta.generated_at).toLocaleString("en-IN") : "—"}</span><span className="flex items-center gap-1.5"><Check size={13} className="text-mint" /> Server-side DuckDB aggregation · {data?.query_ms ? `${data.query_ms} ms query` : "ready"}</span></footer>
    </main>
  </div>;
}

export default App;

