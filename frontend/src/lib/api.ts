/** Shared API client for Cyber Narrative Radar backend endpoints. */

/** Deployed API origin; local fallback is the FastAPI default. */
const API_BASE_URL = (
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ||
  "http://localhost:8000"
).replace(/\/$/, "");

function apiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

/** Absolute URL for the SSE notification stream. */
export function eventsStreamUrl(): string {
  return apiUrl("/api/events/stream");
}

export type HealthResponse = {
  status: string;
  service: string;
  version: string;
};

export type EvidencePost = {
  id: string;
  source: string;
  title: string;
  url: string | null;
  published_at: string;
  severity_score?: number;
  narrative_type?: string | null;
  cve_ids?: string[];
};

export type Alert = {
  id: string;
  title: string;
  narrative_type: string;
  organization: string;
  sector: string;
  severity: string;
  score: number;
  summary: string;
  why_flagged: string[];
  evidence: EvidencePost[];
};

export type Organization = {
  id: string;
  slug?: string;
  name: string;
  sector: string;
  tickers: string[];
  alert_count: number;
  top_narrative_types: string[];
  risk_score: number;
  post_count?: number;
  max_score?: number;
};

export type NarrativeTopPost = {
  id: string;
  title: string;
  source: string;
  url: string | null;
  narrative_type: string | null;
  severity_score: number;
  published_at: string | null;
};

/** Rule-based (future LLM-ready) narrative cluster summary. */
export type NarrativeClusterSummary = {
  summary: string;
  organizations: string[];
  categories: string[];
  provider: string;
  post_count: number;
};

/** Clustered narrative from TF-IDF + KMeans `/api/narratives`. */
export type NarrativeCluster = {
  id: string;
  title: string;
  count: number;
  top_posts: NarrativeTopPost[];
  keywords: string[];
  summary?: NarrativeClusterSummary | null;
};

/** @deprecated Prefer NarrativeCluster — kept for transitional overview typing. */
export type Narrative = NarrativeCluster;

export type CategoryCount = {
  category: string;
  count: number;
};

export type CategoryMetricsResponse = {
  total_posts: number;
  categories: CategoryCount[];
};

export type SourceCount = {
  source: string;
  count: number;
  share: number;
};

export type SourceMetricsResponse = {
  total_posts: number;
  sources: SourceCount[];
};

export type VolumePoint = {
  date: string;
  count: number;
};

export type VolumeMetricsResponse = {
  total_posts: number;
  points: VolumePoint[];
};

export type RelatedPost = {
  id: string;
  title: string;
  source: string;
  url: string | null;
  narrative_type: string | null;
  severity_score: number;
  published_at: string | null;
};

export type RelatedAlert = {
  id: string;
  title: string;
  narrative_type: string;
  severity: string;
  score: number;
  summary: string;
};

export type OrganizationActivitySummary = {
  top_category: string | null;
  top_source: string | null;
  summary: string;
  post_count: number;
};

export type OrganizationDrilldown = {
  organization: Organization;
  related_posts: RelatedPost[];
  related_alerts: RelatedAlert[];
  summary: OrganizationActivitySummary;
};

export type OrganizationTimeseriesPoint = {
  date: string;
  count: number;
  max_score: number;
};

export type OrganizationTimeseriesResponse = {
  organization_slug: string;
  organization_name: string;
  total_posts: number;
  points: OrganizationTimeseriesPoint[];
};

export type OrganizationRiskBrief = {
  organization_name: string;
  organization_slug: string;
  sector: string;
  risk_level: string;
  risk_score_0_100: number;
  executive_summary: string;
  volume_24h: number;
  baseline_7d_daily_avg: number;
  volume_ratio: number;
  top_narratives: Array<{
    narrative_type: string;
    count: number;
    share: number;
  }>;
  open_alert_count: number;
  highest_alert_severity: string | null;
  cve_ids: string[];
  evidence: Array<{
    id: string;
    title: string;
    source: string;
    url: string | null;
    published_at: string | null;
    severity_score: number;
    cve_ids: string[];
  }>;
  caveats: string[];
  generated_at: string;
};

async function getJson<T>(path: string): Promise<T> {
  const url = apiUrl(path);
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Request failed (${response.status}) for ${url}`);
  }

  return (await response.json()) as T;
}

export function fetchHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/api/health");
}

export type AlertFilters = {
  search?: string;
  category?: string;
  organization?: string;
  source?: string;
};

export function fetchAlerts(filters: AlertFilters = {}): Promise<Alert[]> {
  const params = new URLSearchParams();
  if (filters.search) {
    params.set("search", filters.search);
  }
  if (filters.category) {
    params.set("category", filters.category);
  }
  if (filters.organization) {
    params.set("organization", filters.organization);
  }
  if (filters.source) {
    params.set("source", filters.source);
  }
  const query = params.toString();
  return getJson<Alert[]>(query ? `/api/alerts?${query}` : "/api/alerts");
}

export type OrganizationFilters = {
  search?: string;
  sector?: string;
};

/** Stable API path key: prefer slug, fall back to id. */
export function organizationRef(org: Pick<Organization, "id" | "slug">): string {
  return org.slug || org.id;
}

export function fetchOrganizations(
  filters: OrganizationFilters = {},
): Promise<Organization[]> {
  const params = new URLSearchParams();
  if (filters.search) {
    params.set("search", filters.search);
  }
  if (filters.sector) {
    params.set("sector", filters.sector);
  }
  const query = params.toString();
  return getJson<Organization[]>(
    query ? `/api/organizations?${query}` : "/api/organizations",
  );
}

export function fetchOrganizationDrilldown(
  organizationRefValue: string,
): Promise<OrganizationDrilldown> {
  return getJson<OrganizationDrilldown>(
    `/api/organizations/${organizationRefValue}/drilldown`,
  );
}

export type OrganizationDetail = OrganizationDrilldown;

export function fetchOrganizationDetail(
  organizationSlug: string,
): Promise<OrganizationDetail> {
  return getJson<OrganizationDetail>(`/api/organizations/${organizationSlug}`);
}

export function fetchNarratives(): Promise<NarrativeCluster[]> {
  return getJson<NarrativeCluster[]>("/api/narratives");
}

export function fetchCategoryMetrics(): Promise<CategoryMetricsResponse> {
  return getJson<CategoryMetricsResponse>("/api/metrics/categories");
}

export function fetchSourceMetrics(): Promise<SourceMetricsResponse> {
  return getJson<SourceMetricsResponse>("/api/metrics/sources");
}

export function fetchVolumeMetrics(days = 14): Promise<VolumeMetricsResponse> {
  return getJson<VolumeMetricsResponse>(`/api/metrics/volume?days=${days}`);
}

export function fetchOrganizationTimeseries(
  organizationSlug: string,
  days = 14,
): Promise<OrganizationTimeseriesResponse> {
  return getJson<OrganizationTimeseriesResponse>(
    `/api/organizations/${organizationSlug}/timeseries?days=${days}`,
  );
}

export function fetchOrganizationRiskBrief(
  organizationSlug: string,
): Promise<OrganizationRiskBrief> {
  return getJson<OrganizationRiskBrief>(
    `/api/organizations/${organizationSlug}/risk-brief`,
  );
}
