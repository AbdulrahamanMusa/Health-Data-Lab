import { BrainCircuit, CheckCircle2, ChevronDown, Crosshair, Database, HeartPulse, LayoutGrid, Loader2, MapPin, Menu, Moon, RefreshCw, RotateCcw, Server, Sun, TriangleAlert, X } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { when } from "@/format";
import { Actions, Connection, Districts, Overview } from "@/pages/Report";
import { Risk } from "@/pages/Risk";
import { useSetShinyInput, useShinyInitialized, useShinyMessageHandler, useShinyOutputStatus, useShinyOutputValue } from "@/shiny";
import { useTheme } from "@/theme";
import type { Filters, Meta, PageId, View } from "@/types";

// Same pages, titles and wording as the Power BI report, plus the Risk forecast.
const PAGES: { id: PageId; label: string; icon: ReactNode; isNew?: boolean }[] = [
  { id: "overview", label: "Overview", icon: <LayoutGrid size={18} /> },
  { id: "districts", label: "Districts", icon: <MapPin size={18} /> },
  { id: "actions", label: "Actions", icon: <Crosshair size={18} /> },
  { id: "risk", label: "Risk forecast", icon: <BrainCircuit size={18} />, isNew: true },
  { id: "connection", label: "Connection", icon: <Server size={18} /> },
];
const TITLES: Record<PageId, [string, string]> = {
  overview: ["Maternal and Child Health Overview", "Antenatal care, immunisation and reporting, pulled live from DHIS2 analytics."],
  districts: ["District and Chiefdom Scorecard", "Every chiefdom, with coverage, dropout and reporting. Use the District slicer to focus."],
  actions: ["Actions and Data Quality", "What to do next, which districts to start with, and where the data needs checking first."],
  risk: ["Facility Risk Forecast", "Which health facilities are likely to fall behind next quarter, and why."],
  connection: ["Connection to DHIS2", "Where the data comes from, what is requested, and how to point this report at another DHIS2 server."],
};
const EMPTY: Filters = { district: "All", chiefdom: "All", month: "All" };

type Toast = { id: number; title: string; text: string; level: string };

/** A Power BI-style slicer: a white card with a label and a dropdown. */
function Slicer({ label, value, onChange, options, disabled }: { label: string; value: string; onChange: (v: string) => void; options: { id: string; label: string }[]; disabled?: boolean }) {
  const shown = value === "All" ? "All" : (options.find((o) => o.id === value)?.label ?? value);
  return (
    <label className={`slicer ${value !== "All" ? "active" : ""} ${disabled ? "disabled" : ""}`} title={disabled ? `${label} doesn't apply to this page` : undefined}>
      <span className="slicer-label">{label}</span>
      <span className="slicer-box">
        <span>{shown}</span>
        <ChevronDown size={18} />
      </span>
      <select value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled} aria-label={label}>
        <option value="All">All</option>
        {options.map((o) => (
          <option key={o.id} value={o.id}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function App() {
  const initialized = useShinyInitialized();
  const meta = useShinyOutputValue<Meta>("meta");
  const view = useShinyOutputValue<View>("view");
  const viewStatus = useShinyOutputStatus("view");
  const { mode, setMode } = useTheme();

  const [page, setPageState] = useState<PageId>(() => {
    const h = location.hash.replace("#", "") as PageId;
    return PAGES.some((p) => p.id === h) ? h : "overview";
  });
  const [filters, setFiltersState] = useState<Filters>(EMPTY);
  const [outcome, setOutcomeState] = useState("low_penta3");
  const [navOpen, setNavOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 4);
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  const sendPage = useSetShinyInput<string>("page", page, { debounceMs: 0 });
  const sendFilters = useSetShinyInput<Filters>("filters", EMPTY, { debounceMs: 0 });
  const sendOutcome = useSetShinyInput<string>("outcome", "low_penta3", { debounceMs: 0 });
  const sendRefresh = useSetShinyInput<number | null>("refresh", null, { debounceMs: 0, priority: "event" });

  const setPage = (p: PageId) => {
    setPageState(p);
    sendPage(p);
    setNavOpen(false);
    history.replaceState(null, "", `#${p}`);
    window.scrollTo({ top: 0 });
  };
  const setFilters = (f: Filters) => {
    setFiltersState(f);
    sendFilters(f);
  };
  const setOutcome = (o: string) => {
    setOutcomeState(o);
    sendOutcome(o);
  };

  const [toasts, setToasts] = useState<Toast[]>([]);
  const tid = useRef(0);
  useShinyMessageHandler<Omit<Toast, "id">>("toast", (t) => {
    const id = ++tid.current;
    setToasts((ts) => [...ts, { ...t, id }]);
    setTimeout(() => setToasts((ts) => ts.filter((x) => x.id !== id)), 6000);
  });

  const chiefdoms = useMemo(() => (meta ? meta.chiefdoms.filter((c) => filters.district === "All" || c.district === filters.district).map((c) => ({ id: c.id, label: c.name })) : []), [meta, filters.district]);
  useEffect(() => {
    document.title = `${PAGES.find((p) => p.id === page)?.label} · DHIS2 MNCH`;
  }, [page]);

  if (!initialized || !meta) {
    return (
      <div className="boot">
        <span className="brand-icon lg">
          <HeartPulse size={26} />
        </span>
        <b>DHIS2 MNCH Dashboard</b>
        <span>Live maternal and child health data from DHIS2</span>
      </div>
    );
  }

  const src = meta.source;
  const ready = view && view.page === page;
  const busy = viewStatus === "recalculating" || !ready;
  const monthless = page === "risk" || page === "connection";
  const anyFilter = filters.district !== "All" || filters.chiefdom !== "All" || filters.month !== "All";
  const [title, subtitle] = TITLES[page];

  return (
    <div className={`layout ${navOpen ? "nav-open" : ""}`}>
      <aside className="rail" aria-label="Pages">
        <div className="brand">
          <span className="brand-icon">
            <HeartPulse size={20} />
          </span>
          <div>
            <b>DHIS2 MNCH</b>
            <span>Live from the DHIS2 Web API</span>
          </div>
          <button className="rail-close" onClick={() => setNavOpen(false)} aria-label="Close menu">
            <X size={18} />
          </button>
        </div>
        <span className="rail-label">Pages</span>
        <nav className="rail-nav">
          {PAGES.map((p) => (
            <button key={p.id} className={page === p.id ? "on" : ""} aria-current={page === p.id ? "page" : undefined} onClick={() => setPage(p.id)}>
              {p.icon}
              <span>{p.label}</span>
              {p.isNew && <em className="new">New</em>}
            </button>
          ))}
        </nav>
        <div className="rail-bottom">
          <div className="connected">
            <span className="rail-label sm">Connected to</span>
            <div className="connected-host">
              <span className="host-icon">
                <Database size={18} />
              </span>
              <div>
                <b title={src.server}>{src.host}</b>
                <span>DHIS2 {src.version}</span>
              </div>
            </div>
            <button className="refreshed" onClick={() => sendRefresh(Date.now())} disabled={src.refreshing} title="Pull fresh data from DHIS2">
              {src.refreshing ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />}
              {src.refreshing ? "Refreshing…" : `Refreshed ${when(src.refreshed_at)}`}
              <i className={`live-dot ${src.live ? "on" : ""}`} title={src.live ? "Live data" : "Saved snapshot"} />
            </button>
          </div>
          <div className="rail-foot">
            <b>DHIS2 public demo (Sierra Leone)</b>
            <span>Demo data resets nightly. For learning only.</span>
          </div>
          <button className="theme-toggle" onClick={() => setMode(mode === "dark" ? "light" : "dark")}>
            {mode === "dark" ? <Sun size={14} /> : <Moon size={14} />}
            {mode === "dark" ? "Light mode" : "Dark mode"}
          </button>
        </div>
      </aside>
      <div className="scrim" onClick={() => setNavOpen(false)} />

      <div className="content">
        <header className={`head ${scrolled ? "scrolled" : ""}`}>
          <button className="menu-btn" onClick={() => setNavOpen(true)} aria-label="Open menu">
            <Menu size={20} />
          </button>
          <div className="head-text">
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          <div className="head-source">
            <Server size={15} />
            <span>
              DHIS2 {src.version} · data to {src.data_to} · refreshed {when(src.refreshed_at)}
            </span>
          </div>
        </header>
        {src.error && (
          <div className="banner">
            <TriangleAlert size={15} /> Couldn't refresh from DHIS2: {src.error} Showing the last data loaded.
          </div>
        )}

        <main className={`main ${busy ? "busy" : ""}`} aria-busy={busy}>
          {page !== "connection" && (
            <div className="slicers">
              <Slicer label="District" value={filters.district} options={meta.districts.map((d) => ({ id: d, label: d }))} onChange={(d) => setFilters({ ...filters, district: d, chiefdom: "All" })} />
              <Slicer label="Chiefdom" value={filters.chiefdom} options={chiefdoms} onChange={(c) => setFilters({ ...filters, chiefdom: c })} />
              <Slicer label="Month" value={filters.month} options={meta.months} onChange={(m) => setFilters({ ...filters, month: m })} disabled={monthless} />
              <button className="clear" onClick={() => setFilters(EMPTY)} disabled={!anyFilter}>
                <RotateCcw size={16} /> Clear filters
              </button>
            </div>
          )}
          <div className="loadbar" />
          {!ready ? (
            <div className="skeleton">
              <div />
              <div />
              <div />
            </div>
          ) : view.page === "overview" ? (
            <Overview v={view} />
          ) : view.page === "districts" ? (
            <Districts v={view} />
          ) : view.page === "actions" ? (
            <Actions v={view} />
          ) : view.page === "risk" ? (
            <Risk v={view} meta={meta} outcome={outcome} setOutcome={setOutcome} />
          ) : (
            <Connection v={view} />
          )}
        </main>
      </div>

      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.level}`}>
            {t.level === "ok" ? <CheckCircle2 size={16} /> : <TriangleAlert size={16} />}
            <div>
              <b>{t.title}</b>
              {t.text && <span>{t.text}</span>}
            </div>
            <button className="toast-x" onClick={() => setToasts((ts) => ts.filter((x) => x.id !== t.id))} aria-label="Dismiss">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
