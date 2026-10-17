// The four pages that replicate the Power BI report: same measures, same visuals, same layout.
import { AlertTriangle, ArrowDownUp, CalendarCheck, CalendarDays, CheckCircle2, CircleDot, FileText, HeartPulse, Info, List, RefreshCw, Search, Server, Syringe, UserX } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { BarList, Columns, LineChart, Quadrant, Sparkline } from "@/charts/Charts";
import { num, pct, SHADE_TEXT, when } from "@/format";
import type { ActionsView, ConnectionView, DistrictsView, OverviewView, ScoreRow, Shade } from "@/types";

export function Card({ title, sub, children, className = "", action }: { title: string; sub?: string; children: ReactNode; className?: string; action?: ReactNode }) {
  return (
    <section className={`card ${className}`}>
      <header className="card-head">
        <div>
          <h3>{title}</h3>
          {sub && <p>{sub}</p>}
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

const ICONS: Record<string, ReactNode> = {
  heart: <HeartPulse size={16} />,
  calendar: <CalendarCheck size={16} />,
  userx: <UserX size={16} />,
  syringe: <Syringe size={16} />,
  alert: <AlertTriangle size={16} />,
  file: <FileText size={16} />,
};

export function StatusChip({ s }: { s: Shade }) {
  if (!s) return null;
  const icon = s === "on" ? <CheckCircle2 size={12} /> : s === "near" ? <CircleDot size={12} /> : <AlertTriangle size={12} />;
  const text = s === "on" ? "On target" : s === "near" ? "Close" : "Off target";
  return (
    <span className={`chip st-${s}`}>
      {icon}
      {text}
    </span>
  );
}

/** Counts up to the value when it first appears or changes (respects reduced motion). */
function CountUp({ value }: { value: number | null }) {
  const [shown, setShown] = useState<number | null>(value);
  const from = useRef(0);
  useEffect(() => {
    if (value == null || matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(value);
      return;
    }
    const start = performance.now();
    const a = from.current;
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / 700);
      const e = 1 - Math.pow(1 - k, 3);
      setShown(a + (value - a) * e);
      if (k < 1) raf = requestAnimationFrame(tick);
      else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <>{pct(shown)}</>;
}

const SPARK = { on: "var(--s1)", near: "var(--s4)", far: "var(--risk-high)" } as Record<string, string>;

/* ---------------------------------------------------------------- overview */

export function Overview({ v }: { v: OverviewView }) {
  return (
    <div className="page overview">
      <div className="kpis">
        {v.kpis.map((k) => (
          <article key={k.id} className={`kpi st-${k.status ?? "none"}`}>
            <header>
              <span className="kpi-label">{k.label}</span>
              <span className="kpi-icon" aria-hidden>
                {ICONS[k.icon]}
              </span>
            </header>
            <span className="kpi-note" title={k.status ? SHADE_TEXT[k.status] : undefined}>
              {k.note}
            </span>
            <div className="kpi-foot">
              <span className="kpi-value">
                <CountUp value={k.value} />
              </span>
              <Sparkline values={k.spark} highlight={k.spark_on} color={SPARK[k.status ?? "on"] ?? "var(--s1)"} height={30} />
            </div>
          </article>
        ))}
      </div>
      <div className="grid-ov">
        <Card title="Coverage by month" sub="Monthly coverage, annualised the same way as DHIS2" className="span-trend">
          <LineChart
            data={v.trend as unknown as Record<string, number | string | null>[]}
            refValue={1}
            fill
            series={[
              { key: "ANC1", label: "ANC 1", color: "var(--s1)" },
              { key: "ANC4", label: "ANC 4", color: "var(--s2)" },
              { key: "PENTA3", label: "Penta 3", color: "var(--s3)" },
              { key: "MEASLES", label: "Measles", color: "var(--s4)" },
            ]}
          />
        </Card>
        <Card title="Penta 3 coverage by district" sub={`Lowest first. Target ${pct(v.penta3_target, 0)}.`} className="span-side">
          <BarList items={v.penta3_by_district} target={v.penta3_target} color="var(--s1)" rowHeight={33} fill />
        </Card>
        <Card title="What needs attention" className="span-trend">
          {v.findings.length ? (
            <table className="textual">
              <thead>
                <tr>
                  <th className="txt">Finding</th>
                  <th className="txt">What the data says</th>
                </tr>
              </thead>
              <tbody>
                {v.findings.map((f) => (
                  <tr key={f.topic}>
                    <td className="txt">{f.topic}</td>
                    <td className="txt wrap">{f.text}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">No data in this selection.</p>
          )}
        </Card>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- districts */

const COLS: { key: keyof ScoreRow; label: string; kind: "pct" | "num" }[] = [
  { key: "anc1", label: "ANC 1", kind: "pct" },
  { key: "anc4", label: "ANC 4", kind: "pct" },
  { key: "anc_dropout", label: "ANC drop", kind: "pct" },
  { key: "penta3", label: "Penta 3", kind: "pct" },
  { key: "penta_dropout", label: "Penta drop", kind: "pct" },
  { key: "measles", label: "Measles", kind: "pct" },
  { key: "reporting", label: "Reporting", kind: "pct" },
  { key: "missed", label: "Missed Penta 3", kind: "num" },
];

export function ShadeLegend() {
  return (
    <div className="shade-legend">
      {(["on", "near", "far"] as const).map((s) => (
        <span key={s}>
          <i className={`sw sh-${s}`} />
          {SHADE_TEXT[s]}
        </span>
      ))}
      <span className="muted">Dropout: above 10% counts as off target.</span>
    </div>
  );
}

export function Districts({ v }: { v: DistrictsView }) {
  const [sort, setSort] = useState<{ key: keyof ScoreRow; desc: boolean }>({ key: "missed", desc: true });
  const [q, setQ] = useState("");
  const rows = useMemo(() => {
    const f = q.trim().toLowerCase();
    const r = v.rows.filter((x) => !f || x.chiefdom.toLowerCase().includes(f) || x.district.toLowerCase().includes(f));
    const k = sort.key;
    return [...r].sort((a, b) => {
      const av = a[k] as number | string | null;
      const bv = b[k] as number | string | null;
      if (av == null) return 1;
      if (bv == null) return -1;
      const c = typeof av === "string" ? av.localeCompare(bv as string) : (av as number) - (bv as number);
      return sort.desc ? -c : c;
    });
  }, [v.rows, sort, q]);
  const head = (key: keyof ScoreRow, label: string, cls = "") => (
    <th className={cls} aria-sort={sort.key === key ? (sort.desc ? "descending" : "ascending") : "none"}>
      <button onClick={() => setSort({ key, desc: sort.key === key ? !sort.desc : typeof v.rows[0]?.[key] !== "string" })}>
        {label}
        {sort.key === key && <ArrowDownUp size={11} />}
      </button>
    </th>
  );
  return (
    <div className="page districts">
      <Card
        title="Chiefdom scorecard"
        sub="Blue: at or above target. Amber: within 20 pts of target. Red: more than 20 pts below. Dropout red above 10%."
        className="span-main"
        action={
          <label className="search">
            <Search size={14} />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a chiefdom" aria-label="Find a chiefdom or district" />
          </label>
        }
      >
        <div className="table-wrap tall fill">
          <table className="score">
            <thead>
              <tr>
                {head("district", "District", "txt")}
                {head("chiefdom", "Chiefdom", "txt")}
                {COLS.map((c) => head(c.key, c.label))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="txt">{r.district}</td>
                  <td className="txt strong">{r.chiefdom}</td>
                  {COLS.map((c) => (
                    <td key={c.key} className={`n ${c.kind === "pct" ? `sh-${r.shade[c.key as string] ?? "none"}` : ""}`}>
                      {c.kind === "pct" ? pct(r[c.key] as number | null) : num(r[c.key] as number | null)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
            {v.total && (
              <tfoot>
                <tr>
                  <td className="txt" colSpan={2}>
                    Total
                  </td>
                  {COLS.map((c) => (
                    <td key={c.key} className="n">
                      {c.kind === "pct" ? pct(v.total![c.key as keyof NonNullable<DistrictsView["total"]>]) : num(v.total![c.key as keyof NonNullable<DistrictsView["total"]>])}
                    </td>
                  ))}
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </Card>
      <div className="side-stack">
        <Card className="grow" title={`${v.top_missed.length} chiefdoms with most children who missed Penta 3`}>
          <BarList items={v.top_missed.map((t) => ({ name: t.name, value: t.value, sub: t.district }))} format={(x) => (x >= 1000 ? `${(x / 1000).toFixed(1)}K` : num(x))} color="var(--s1)" rowHeight={23} fill />
        </Card>
        <Card title="How to read this page">
          <ul className="notes">
            <li>
              <b>Coverage</b> = doses or visits divided by the annualised target population, the same formula DHIS2 uses.
            </li>
            <li>
              <b>Dropout</b> = share of people who got the first contact (ANC 1, Penta 1) but not the last (ANC 4, Penta 3).
            </li>
            <li>Coverage above 100% usually means the population estimate is too low, not that every child was reached.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- actions */

export function Actions({ v }: { v: ActionsView }) {
  return (
    <div className="page actions">
      <Card title="Recommended actions">
        <table className="textual">
          <thead>
            <tr>
              <th className="txt">Action</th>
              <th className="txt">Why and how many</th>
            </tr>
          </thead>
          <tbody>
            {v.actions.map((a) => (
              <tr key={a.topic}>
                <td className="txt">{a.topic}</td>
                <td className="txt wrap">{a.text}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Districts: Penta 3 coverage against dropout" sub="Top left needs the most help: low coverage and high dropout. Bubble size is children who missed Penta 3.">
        <Quadrant points={v.quadrant} yLimit={0.1} fill />
      </Card>
      <Card title="Reporting rate by district" sub={`Reports received / expected. Lowest first. Target ${pct(v.reporting_target, 0)}.`}>
        <BarList items={v.reporting_by_district} target={v.reporting_target} color="var(--s1)" rowHeight={26} fill />
      </Card>
      <Card className="over100" title="Coverage above 100%: check the population estimate" sub={`${v.over100.length} chiefdoms. Sorted by Penta 1 coverage.`}>
        <div className="table-wrap fill">
          <table className="plain">
            <thead>
              <tr>
                <th className="txt">District</th>
                <th className="txt">Chiefdom</th>
                <th>ANC 1</th>
                <th>Penta 1</th>
                <th>Penta 1 doses</th>
              </tr>
            </thead>
            <tbody>
              {v.over100.map((r) => (
                <tr key={r.district + r.chiefdom}>
                  <td className="txt">{r.district}</td>
                  <td className="txt strong">{r.chiefdom}</td>
                  <td className={`n ${(r.anc1 ?? 0) > 1 ? "flag" : ""}`}>{pct(r.anc1)}</td>
                  <td className={`n ${(r.penta1 ?? 0) > 1 ? "flag" : ""}`}>{pct(r.penta1)}</td>
                  <td className="n">{num(r.penta1_doses)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

/* ---------------------------------------------------------------- connection */

export function Connection({ v }: { v: ConnectionView }) {
  const s = v.source;
  const tiles = [
    { label: "Server", value: s.host, icon: <Server size={15} /> },
    { label: "Version", value: s.version, icon: <FileText size={15} /> },
    { label: "Data up to", value: s.data_to, icon: <CalendarDays size={15} /> },
    { label: "Last refresh", value: `Refreshed ${when(s.refreshed_at)}`, icon: <RefreshCw size={15} /> },
    { label: "Rows loaded", value: s.rows.toLocaleString("en-GB"), icon: <List size={15} />, big: true },
  ];
  return (
    <div className="page connection">
      <div className="src-tiles">
        {tiles.map((t) => (
          <article key={t.label} className="src-tile">
            <header>
              <span>{t.label}</span>
              <i className="kpi-icon">{t.icon}</i>
            </header>
            <b className={t.big ? "big" : ""}>{t.value}</b>
          </article>
        ))}
      </div>
      <Card className="catalogue" title="Indicators requested from DHIS2" sub="Edit CATALOGUE in mnch/dhis2.py to add or change indicators.">
        <div className="table-wrap fill">
          <table className="plain">
            <thead>
              <tr>
                <th className="txt">Indicator</th>
                <th className="txt">DHIS2 ID</th>
                <th className="txt">Denominator</th>
                <th>Target</th>
              </tr>
            </thead>
            <tbody>
              {v.catalogue.map((c) => (
                <tr key={c.code}>
                  <td className="txt strong">{c.name}</td>
                  <td className="txt mono">{c.id}</td>
                  <td className="txt">{c.denominator}</td>
                  <td className="n">{pct(c.target, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card title="How this connection works" className="how">
        <div className="prose">
          <p>
            Python calls the DHIS2 Web API over HTTPS with the same requests as the Power BI model: <code>api/analytics</code> for indicator numerators by chiefdom and month, the same endpoint again for the population
            denominators, <code>api/organisationUnits</code> for names and boundaries, and <code>api/system/info</code> for the version. The same indicators are also pulled by facility for the risk forecast.
          </p>
          <p>Rates are recomputed from numerators and annualised populations, so they stay correct when you combine districts or months, and every figure matches the Power BI report.</p>
          <h4>Point it at another server</h4>
          <p>
            Set <code>DHIS2_BASE_URL</code>, <code>DHIS2_ROOT_ORG_UNIT</code> and <code>DHIS2_PERIODS</code> in the environment, then press <b>Refresh</b>. Update the IDs in the catalogue to match that server's indicators.
          </p>
          <h4>Credentials</h4>
          <p>
            The user name and password come from the <code>DHIS2_USERNAME</code> and <code>DHIS2_PASSWORD</code> environment variables (secrets on the host, or a local <code>.env</code> file). They are never stored in the code and never reach the browser. For a real server, use a read-only account or a personal access token.
          </p>
          <h4>Refresh</h4>
          <p>The app serves its last snapshot instantly, pulls live data when it starts, and pulls again whenever someone presses Refresh: no gateway and no scheduled refresh to set up.</p>
        </div>
      </Card>
      <Card className="rows-month" title="Rows received from DHIS2 by month" sub="A sudden drop usually means missing reports or an analytics run that has not finished.">
        <Columns items={v.rows_by_month} color="var(--s1)" fill />
      </Card>
      <p className="footnote">
        <Info size={13} /> {s.chiefdoms} chiefdoms · periods {s.periods} · {s.live ? `live pull took ${s.seconds} s` : "served from the saved snapshot"}
      </p>
    </div>
  );
}
