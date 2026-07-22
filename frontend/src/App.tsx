import { useState } from "react";
import { OrganizationProvider } from "./context/OrganizationContext";
import AlertsPage from "./pages/AlertsPage";
import CategoryChartPage from "./pages/CategoryChartPage";
import NarrativeExplorerPage from "./pages/NarrativeExplorerPage";
import OrganizationDetailPage from "./pages/OrganizationDetailPage";
import OrganizationsPage from "./pages/OrganizationsPage";
import OrganizationTrendPage from "./pages/OrganizationTrendPage";
import OverviewPage from "./pages/OverviewPage";
import VolumeChartPage from "./pages/VolumeChartPage";

type PageId =
  | "overview"
  | "alerts"
  | "organizations"
  | "org-detail"
  | "org-trend"
  | "narratives"
  | "categories"
  | "volume";

type NavItem = {
  id: PageId;
  label: string;
};

type NavGroup = {
  label: string;
  items: NavItem[];
};

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Monitor",
    items: [
      { id: "overview", label: "Overview" },
      { id: "alerts", label: "Alerts" },
      { id: "narratives", label: "Narratives" },
    ],
  },
  {
    label: "Watchlist",
    items: [
      { id: "organizations", label: "Organizations" },
      { id: "org-detail", label: "Org Detail" },
      { id: "org-trend", label: "Org Trend" },
    ],
  },
  {
    label: "Analytics",
    items: [
      { id: "categories", label: "Categories" },
      { id: "volume", label: "Volume" },
    ],
  },
];

function AppShell() {
  const [page, setPage] = useState<PageId>("overview");

  return (
    <div className="app-shell">
      <aside className="dashboard-sidebar" aria-label="Dashboard navigation">
        <div className="dashboard-brand">
          <h1>Cyber Narrative Radar</h1>
          <p>Cybersecurity narrative intelligence MVP</p>
        </div>

        <nav className="dashboard-nav">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="nav-group">
              <p className="nav-group-label">{group.label}</p>
              <div className="nav-group-items">
                {group.items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={page === item.id ? "nav-btn active" : "nav-btn"}
                    onClick={() => setPage(item.id)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </nav>
      </aside>

      <div className="dashboard-main">
        <main className="dashboard-content">
          {page === "overview" && <OverviewPage />}
          {page === "alerts" && <AlertsPage />}
          {page === "organizations" && <OrganizationsPage />}
          {page === "org-detail" && <OrganizationDetailPage />}
          {page === "org-trend" && <OrganizationTrendPage />}
          {page === "narratives" && <NarrativeExplorerPage />}
          {page === "categories" && <CategoryChartPage />}
          {page === "volume" && <VolumeChartPage />}
        </main>
      </div>
    </div>
  );
}

function App() {
  return (
    <OrganizationProvider>
      <AppShell />
    </OrganizationProvider>
  );
}

export default App;
