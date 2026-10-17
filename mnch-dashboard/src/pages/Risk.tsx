// The page the Power BI report doesn't have: which facilities are likely to fall behind next quarter.
import { AlertTriangle, BrainCircuit, CircleDot, Search, ShieldCheck, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Calibration, RiskMap } from "@/charts/Charts";
import { BAND_TEXT, pct } from "@/format";
import { Card } from "@/pages/Report";
import type { FacilityRisk, Meta, RiskView } from "@/types";

const shortLabel = (l: string) => l.replace(", last 3 months", " (3 mo)").replace(", last 6 months", " (6 mo)").replace("Population under 1", "Children under 1").replace("Penta 1 to 3 dropout", "Penta dropout").replace("ANC 1 to 4 dropout", "ANC dropout");

/** The two strongest reasons, counting the 3- and 6-month versions of one measure once. */
const topReasons = (drivers: FacilityRisk["drivers"]) => {
  const seen = new Set<string>();
  return drivers.filter((d) => {
    const base = d.label.replace(/, last \d months/, "");
    if (seen.has(base)) return false;
    seen.add(base);
    return true;
  }).slice(0, 2);
};

function BandChip({ band }: { band: FacilityRisk["band"] }) {
  const icon = band === "high" ? <AlertTriangle size={12} /> : band === "medium" ? <CircleDot size={12} /> : <ShieldCheck size={12} />;
  return (
    <span className={`chip band-${band}`}>
      {icon}
      {BAND_TEXT[band]}
    </span>
  );
}

function RiskBar({ value }: { value: number }) {
  return (
    <span className="riskbar" aria-label={`Risk ${pct(value, 0)}`}>
      <span className="track">
        <span className="fill" style={{ width: `${Math.max(2, value * 100)}%` }} />
      </span>
      <b>{pct(value, 0)}</b>
    </span>
  );
}

export function Risk({ v, meta, outcome, setOutcome }: { v: RiskView; meta: Meta; outcome: string; setOutcome: (o: string) => void }) {
  const [band, setBand] = useState<"all" | FacilityRisk["band"]>("all");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const val = v.validation;
  const nowLabel = v.outcome === "anc_dropout" ? "ANC dropout now" : "Penta 3 now";
  const rows = useMemo(() => {
    const f = q.trim().toLowerCase();
    return v.facilities.filter((r) => (band === "all" || r.band === band) && (!f || r.name.toLowerCase().includes(f) || r.chiefdom.toLowerCase().includes(f) || r.district.toLowerCase().includes(f)));
  }, [v.facilities, band, q]);
  const chosen = v.facilities.find((r) => r.id === sel) ?? null;
  const beats = val.auc >= val.baseline_auc + 0.005;
  const ties = !beats && val.auc >= val.baseline_auc - 0.02;
  return (
    <div className="page risk">
      <div className="risk-head">
        <div className="seg" role="radiogroup" aria-label="Outcome to forecast">
          {meta.outcomes.map((o) => (
            <button key={o.id} role="radio" aria-checked={outcome === o.id} className={outcome === o.id ? "on" : ""} onClick={() => setOutcome(o.id)}>
              {o.label}
            </button>
          ))}
        </div>
        <p className="risk-q">
          <BrainCircuit size={16} /> {v.definition.question} <span className="muted">Forecast for the quarter after {v.scored_on[1]}, from each facility's data up to then.</span>
        </p>
      </div>
      <div className="risk-tiles">
        <article className="rt">
          <span>Facilities scored</span>
          <b>{v.summary.scored.toLocaleString("en-GB")}</b>
          <small>{v.outcome === "low_penta3" ? "Facilities that report Penta doses" : "Facilities with 10+ ANC 1 visits last quarter"}</small>
        </article>
        <article className="rt hot">
          <span>High risk</span>
          <b>{v.summary.high.toLocaleString("en-GB")}</b>
          <small>Risk 60% or more · {v.summary.medium.toLocaleString("en-GB")} more at medium risk</small>
        </article>
        <article className="rt">
          <span>Expected to fall behind</span>
          <b>{Math.round(v.summary.expected).toLocaleString("en-GB")}</b>
          <small>Sum of the risks: the likely number of facilities</small>
        </article>
        <article className="rt">
          <span>Tested on {val.test_window[0]}–{val.test_window[1]}</span>
          <b>
            {pct(val.top10_precision, 0)}
          </b>
          <small>of the top 10% riskiest facilities did fall behind (base rate {pct(val.base_rate, 0)})</small>
        </article>
      </div>
      <div className="risk-grid">
        <Card
          title="Where the risk is"
          sub="Each dot is a facility with map coordinates in DHIS2. Click one for its reasons."
          className="span-map"
          action={
            <div className="map-legend">
              {(["high", "medium", "low"] as const).map((b) => (
                <span key={b}>
                  <i className={`dot b-${b}`} />
                  {BAND_TEXT[b]}
                </span>
              ))}
            </div>
          }
        >
          <RiskMap
            districts={v.map}
            points={v.facilities.map((f) => ({ id: f.id, name: f.name, lat: f.lat, lon: f.lon, band: f.band, risk: f.risk, sub: `${f.chiefdom}, ${f.district}` }))}
            selected={sel}
            onSelect={setSel}
            fill
          />
        </Card>
        <Card
          title="Facilities ranked by risk"
          sub={`${rows.length} of ${v.facilities.length} shown`}
          className="span-list"
          action={
            <label className="search">
              <Search size={14} />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a facility" aria-label="Find a facility" />
            </label>
          }
        >
          <div className="band-filter" role="radiogroup" aria-label="Risk band">
            {(["all", "high", "medium", "low"] as const).map((b) => (
              <button key={b} role="radio" aria-checked={band === b} className={band === b ? "on" : ""} onClick={() => setBand(b)}>
                {b === "all" ? "All" : BAND_TEXT[b]}
              </button>
            ))}
          </div>
          <div className="table-wrap risk-table fill">
            <table className="plain">
              <thead>
                <tr>
                  <th className="txt">Facility</th>
                  <th className="txt">Risk</th>
                  <th>{nowLabel}</th>
                  <th className="txt">Main reasons</th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 300).map((r) => (
                  <tr key={r.id} className={r.id === sel ? "sel" : ""} onClick={() => setSel(r.id)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setSel(r.id)}>
                    <td className="txt">
                      <b>{r.name}</b>
                      <small>
                        {r.chiefdom}, {r.district}
                      </small>
                    </td>
                    <td className="txt">
                      <div className="risk-cell">
                        <RiskBar value={r.risk} />
                        <BandChip band={r.band} />
                      </div>
                    </td>
                    <td className="n">{pct(r.now, 0)}</td>
                    <td className="txt reasons">{r.drivers.length ? topReasons(r.drivers).map((d) => <span key={d.feature}>{shortLabel(d.label)}: {d.value}</span>) : <span className="muted">Close to average</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length > 300 && <p className="muted small pad">Showing the 300 highest. Filter by district or band to see more.</p>}
          </div>
        </Card>
      </div>
      {chosen && (
        <aside className="drawer" aria-label={`Risk details for ${chosen.name}`}>
          <button className="icon-btn close" onClick={() => setSel(null)} aria-label="Close details">
            <X size={16} />
          </button>
          <span className="eyebrow">
            {chosen.type} · {chosen.chiefdom}, {chosen.district}
          </span>
          <h3>{chosen.name}</h3>
          <div className="drawer-risk">
            <RiskBar value={chosen.risk} />
            <BandChip band={chosen.band} />
          </div>
          <p className="muted">
            Chance of {v.definition.label.charAt(0).toLowerCase() + v.definition.label.slice(1)} next quarter. {nowLabel}: <b>{pct(chosen.now, 0)}</b>. Reporting rate: <b>{pct(chosen.reporting, 0)}</b>.
          </p>
          <h4>Why the model rates it this way</h4>
          {chosen.drivers.length ? (
            <ul className="drivers">
              {chosen.drivers.map((d) => (
                <li key={d.feature}>
                  <span>{d.label}</span>
                  <b>{d.value}</b>
                  <i style={{ width: `${Math.min(100, d.effect * 40)}%` }} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No single factor stands out: this facility looks close to average.</p>
          )}
          <p className="small muted">Bars show how much each factor raises the risk compared with an average facility.</p>
        </aside>
      )}
      <Card title="How the forecast works, and how good it is" className="model-card">
        <div className="model-grid">
          <div className="prose">
            <p>
              <b>Outcome.</b> {v.definition.definition}
            </p>
            <p>
              <b>Model.</b> A logistic regression on each facility's last 3 and 6 months from DHIS2 facility-level analytics: {val.coefficients.map((c) => c.label.toLowerCase()).join("; ")}. Every risk can be explained as a sum of
              those factors.
            </p>
            <p>
              <b>Test.</b> Fitted on {val.train_rows.toLocaleString("en-GB")} facility-quarters that ended before {val.test_window[0]}, then checked against what actually happened in {val.test_window[0]}–{val.test_window[1]} at{" "}
              {val.test_rows.toLocaleString("en-GB")} facilities it had never seen. The live forecast is refitted on all {val.final_rows.toLocaleString("en-GB")} known quarters.
            </p>
            <div className={`verdict ${beats ? "good" : ties ? "even" : "weak"}`}>
              <b>{beats ? "Better than the simple rule." : ties ? "About as good as the simple rule." : "Weaker than the simple rule."}</b> Ranking accuracy (AUC) {val.auc.toFixed(2)} against {val.baseline_auc.toFixed(2)} for "same as last quarter";
              correct calls {pct(val.accuracy, 0)} against {pct(val.baseline_accuracy, 0)}.{" "}
              {beats ? "It adds signal beyond the latest figure." : "A facility's recent figure carries most of the signal; the model's value is a calibrated probability and the reasons behind it."}
            </div>
            {v.outcome === "anc_dropout" && (
              <p className="small muted">
                ANC 1 coverage above 100% usually means the facility's population estimate is too low (see Actions). The model still counts it as a warning sign because, in past quarters, those facilities also had higher dropout.
              </p>
            )}
            <p className="small muted">A forecast for planning support visits, not a judgement on any facility. Demo data from the public DHIS2 server.</p>
          </div>
          <div>
            <h4 className="mini-title">Does a 70% risk mean 70%?</h4>
            <Calibration bins={val.calibration} />
            <p className="small muted">Each dot groups facilities by predicted risk (x) against how many actually fell behind (y). On the diagonal = well calibrated.</p>
          </div>
        </div>
      </Card>
    </div>
  );
}
