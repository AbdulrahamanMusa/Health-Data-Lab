import { ChevronDown, Database, Download, FileSpreadsheet, FileText, Gauge, History, ListChecks, Monitor, Moon, Sun, UserRound, Users, X } from "lucide-react";
import type { ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Data } from "@/components/Data";
import { Enumerators } from "@/components/Enumerators";
import { Log } from "@/components/Log";
import { Readiness } from "@/components/Readiness";
import { Review } from "@/components/Review";
import { EventsProvider, useSend } from "@/events";
import { useShinyBusy, useShinyInitialized, useShinyInput, useShinyMessageHandler, useShinyOutputStatus, useShinyOutputValue } from "@/shiny";
import { type ThemeMode, useTheme } from "@/theme";
import type { FlagList, Overview, ToastMsg } from "@/types";

type Tab = "readiness" | "review" | "log" | "enumerators" | "data";
const NAV: { id: Tab; label: string; icon: ReactNode; blurb: string }[] = [
  { id: "readiness", label: "Readiness", icon: <Gauge size={17} />, blurb: "Is this dataset fit for decisions, and what would raw data have got wrong?" },
  { id: "review", label: "Review flags", icon: <ListChecks size={17} />, blurb: "Decide on every issue: correct, set missing, exclude, or send to the field" },
  { id: "log", label: "Cleaning log", icon: <History size={17} />, blurb: "Append-only audit trail of every change" },
  { id: "enumerators", label: "Enumerators", icon: <Users size={17} />, blurb: "Supervision scorecard for the field teams" },
  { id: "data", label: "Data & privacy", icon: <Database size={17} />, blurb: "Your export, its fingerprint, and what leaves the data team" },
];
const THEMES: { mode: ThemeMode; label: string; icon: ReactNode }[] = [
  { mode: "light", label: "Light", icon: <Sun size={14} /> },
  { mode: "dark", label: "Dark", icon: <Moon size={14} /> },
  { mode: "system", label: "System", icon: <Monitor size={14} /> },
];
const OUTPUT_IDS = ["meta", "overview", "flag_list", "cleaning_log", "enumerator_board", "dataset"];

/** Keep every output subscribed for the page's lifetime (avoids shinyreact 0.1 rebind churn on tab switches). */
function KeepOutputsBound() {
  for (const id of OUTPUT_IDS) useShinyOutputStatus(id); // fixed-length loop: stable hook order
  return null;
}

function ExportMenu() {
  const send = useSend();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const item = (kind: string, icon: ReactNode, title: string, sub: string) => (
    <button
      role="menuitem"
      onClick={() => {
        send("export", { kind });
        setOpen(false);
      }}
    >
      {icon}
      <span>
        <b>{title}</b>
        <small>{sub}</small>
      </span>
    </button>
  );
  return (
    <div className="menu" ref={ref}>
      <button className="btn btn-primary" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Download size={15} /> Export <ChevronDown size={14} />
      </button>
      {open && (
        <div className="menu-pop" role="menu">
          {item("audit", <FileSpreadsheet size={16} />, "Audit pack (.xlsx)", "Clean data, cleaning log, flags, enumerators, indicator impact")}
          {item("csv", <Database size={16} />, "Clean dataset (.csv)", "Analysis records only, no identifiers")}
          {item("html", <FileText size={16} />, "One-page summary (.html)", "For managers and partners; print to PDF")}
        </div>
      )}
    </div>
  );
}

type Toast = ToastMsg & { id: number };

export default function App() {
  const initialized = useShinyInitialized();
  const busy = useShinyBusy();
  const overview = useShinyOutputValue<Overview>("overview");
  const flagList = useShinyOutputValue<FlagList>("flag_list");
  const [reviewer, setReviewer] = useShinyInput<string>("reviewer", "Data manager", { debounceMs: 400 });
  const [tab, setTab] = useState<Tab>("readiness");
  const { mode, setMode, theme } = useTheme();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(0);

  const pushToast = useCallback((t: ToastMsg) => {
    const id = ++nextId.current;
    setToasts((x) => [...x.slice(-3), { ...t, id }]);
    setTimeout(() => setToasts((x) => x.filter((y) => y.id !== id)), 5000);
  }, []);
  useShinyMessageHandler<ToastMsg>("toast", pushToast);
  useShinyMessageHandler<{ filename: string; mime: string; text?: string; b64?: string }>("download", ({ filename, mime, text, b64 }) => {
    const blob = b64 ? new Blob([Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))], { type: mime }) : new Blob([text ?? ""], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: filename });
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  });

  if (!initialized || !overview) {
    return (
      <div className="boot">
        <FileSpreadsheet className="boot-icon" size={38} />
        <span>Preparing the cleaning workbench…</span>
      </div>
    );
  }

  const openFlags = flagList?.counts.open ?? 0;
  const current = NAV.find((n) => n.id === tab)!;
  const verdict = overview.readiness.verdict;

  return (
    <EventsProvider>
      <KeepOutputsBound />
      <div className={`busy-bar ${busy ? "on" : ""}`} />
      <div className="layout" key={theme}>
        <nav className="nav" aria-label="Sections">
          <div className="brand">
            <div className="logo">R→R</div>
            <div>
              <b>Raw → Ready</b>
              <span>Health Data Lab · Week 1</span>
            </div>
          </div>
          {NAV.map((n) => (
            <button key={n.id} className={`nav-item ${tab === n.id ? "on" : ""}`} onClick={() => setTab(n.id)} aria-current={tab === n.id ? "page" : undefined} aria-label={n.label}>
              {n.icon}
              <span>{n.label}</span>
              {n.id === "review" && openFlags > 0 && <i className="nav-badge">{openFlags}</i>}
            </button>
          ))}
          <div className={`nav-verdict v-${verdict === "ready" ? "green" : verdict === "not ready" ? "red" : "amber"}`}>
            <span>Dataset status</span>
            <b>{verdict.charAt(0).toUpperCase() + verdict.slice(1)}</b>
          </div>
          <p className="nav-foot">
            Raw data is never modified.
            <br />
            clean = raw + cleaning log
          </p>
        </nav>

        <div className="content">
          <header className="topbar">
            <div className="page-title">
              <h1>{current.label}</h1>
              <p>{current.blurb}</p>
            </div>
            <div className="toolbar">
              <label className="reviewer" title="Your name is recorded in the cleaning log for every decision">
                <UserRound size={15} />
                <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} aria-label="Reviewer name" placeholder="Your name" />
              </label>
              <ExportMenu />
              <div className="theme-toggle" role="radiogroup" aria-label="Colour theme">
                {THEMES.map((t) => (
                  <button key={t.mode} role="radio" aria-checked={mode === t.mode} aria-label={`${t.label} theme`} title={`${t.label} theme`} className={mode === t.mode ? "on" : ""} onClick={() => setMode(t.mode)}>
                    {t.icon}
                  </button>
                ))}
              </div>
            </div>
          </header>
          <main className="main">
            {tab === "readiness" && <Readiness go={(t) => setTab(t as Tab)} />}
            {tab === "review" && <Review />}
            {tab === "log" && <Log />}
            {tab === "enumerators" && <Enumerators />}
            {tab === "data" && <Data />}
          </main>
        </div>
      </div>

      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.level}`}>
            <div>
              <b>{t.title}</b>
              {t.text && <p>{t.text}</p>}
            </div>
            <button aria-label="Dismiss" onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))}>
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </EventsProvider>
  );
}
