import type { DashboardData, FilterOptions, FilterState, Meta } from "./types";

const apiUrl = (path: string) => path;

export function queryString(filters: FilterState): string {
  const params = new URLSearchParams();
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);
  params.set("granularity", filters.granularity);
  for (const [key, values] of Object.entries(filters)) {
    if (["start_date", "end_date", "granularity"].includes(key)) continue;
    for (const value of values as string[]) params.append(key, value);
  }
  return params.toString();
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const getMeta = () => getJson<Meta>(apiUrl("/api/meta"));
export const getFilters = () => getJson<FilterOptions>(apiUrl("/api/filters"));
export const getDashboard = (filters: FilterState, signal?: AbortSignal) =>
  getJson<DashboardData>(`${apiUrl("/api/dashboard")}?${queryString(filters)}`, signal);

export function exportUrl(filters: FilterState): string {
  return `${apiUrl("/api/export.csv")}?${queryString(filters)}`;
}

