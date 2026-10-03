import { AlertTriangle, ArrowRight, CheckCircle2, Fingerprint, Gauge, ListChecks, ShieldCheck, Sparkles, Users, XCircle } from "lucide-react";
import type { CSSProperties } from "react";
import { useState } from "react";

import { ACTION_LABEL, C, Card, Modal, Tile, fmt } from "@/components/common";
import { useSend } from "@/events";
import { useShinyOutputValue } from "@/shiny";
import type { FlagList, Impact, Overview } from "@/types";

const VERDICT = {
  "not ready": { icon: <XCircle size={22} />, title: "Not ready for analysis", tone: "red" },
  "ready with caveats": { icon: <AlertTriangle size={22} />, title: "Ready with caveats", tone: "amber" },
  ready: { icon: <CheckCircle2 size={22} />, title: "Ready for analysis and sharing", tone: "green" },
} as const;

function biasSentence(r: Impact) {
  if (r.bias == null || Math.abs(r.bias) < 0.05) return "No meaningful difference.";
  const raw = r.bias > 0 ? "overstates" : "understates";
  return `Uncleaned data ${raw} this by ${Math.abs(r.bias).toFixed(1)} points.`;
}

function ImpactRow({ r }: { r: Impact }) {
  const harmful = r.bias != null && Math.abs(r.bias) >= 1;
  const max = Math.max(100, r.raw.value ?? 0, r.projected.value ?? 0);
  const scale = r.key === "penta3" || r.key === "anc4" ? 100 : Math.max(25, Math.ceil((Math.max(r.raw.value ?? 0, r.projected.value ?? 0) + 5) / 5) * 5);
  const w = (v: number | null) => `${(100 * (v ?? 0)) / (scale || max)}%`;
  return (
    <div className={`impact ${harmful ? "harmful" : ""}`}>
      <div className="impact-head">
        <div>
          <b>{r.label}</b>
          <span className="muted small">{r.definition}</span>
        </div>
        <span className={`bias ${harmful ? "bad" : ""}`}>{fmt.signed(r.bias)} pts</span>
      </div>
      <div className="impact-bars">
        <div className="ib">
          <span>Raw export</span>
          <div className="track">
            <div className="fill raw" style={{ width: w(r.raw.value) }} />
          </div>
          <b>{fmt.pct(r.raw.value)}</b>
          <small>n={fmt.int(r.raw.den)}</small>
        </div>
        <div className="ib">
          <span>After cleaning</span>
          <div className="track">
            <div className="fill clean" style={{ width: w(r.projected.value) }} />
          </div>
          <b>{fmt.pct(r.projected.value)}</b>
          <small>n={fmt.int(r.projected.den)}</small>
        </div>
      </div>
      <p className="impact-note">{biasSentence(r)}</p>
    </div>
  );
}

function ApplyAll({ onClose }: { onClose: () => void }) {
  const list = useShinyOutputValue<FlagList>("flag_list");
  const send = useSend();
  const groups = (list?.groups ?? []).filter((g) => g.open > 0);
  return (
    <Modal title="Apply recommended actions" onClose={onClose} wide>
      <p className="muted">Each open flag gets the action your cleaning protocol recommends. Every change is logged under your name with its reason, and any of them can be reverted from the cleaning log.</p>
      <table className="table compact">
        <thead>
          <tr>
            <th>Issue</th>
            <th>Open</th>
            <th>Recommended action</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((g) => (
            <tr key={g.check}>
              <td>{g.label}</td>
              <td className="num">{g.open}</td>
              <td>
                <b>{ACTION_LABEL[g.rec_action]}</b>
                <div className="muted small">{g.rec_reason}</div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="form-actions">
        <button className="btn btn-ghost" onClick={onClose}>
          Cancel
        </button>
        <button
          className="btn btn-primary"
          onClick={() => {
            send("decide", { check: "__all__", action: "recommended" });
            onClose();
          }}
        >
          <Sparkles size={15} /> Apply to {groups.reduce((a, g) => a + g.open, 0)} flags
        </button>
      </div>
    </Modal>
  );
}

export function Readiness({ go }: { go: (tab: string) => void }) {
  const o = useShinyOutputValue<Overview>("overview");
  const [confirm, setConfirm] = useState(false);
  if (!o) return <div className="view"><div className="skeleton tall" /></div>;
  const r = o.readiness;
  const v = VERDICT[r.verdict];
  const openTotal = Object.values(r.open).reduce((a, b) => a + b, 0);
  const finalN = o.funnel[o.funnel.length - 1]?.n ?? 0;
  const maxIssue = Math.max(1, ...o.issues.map((i) => i.total));

  return (
    <div className="view">
      <section className={`verdict v-${v.tone}`}>
        <div className="verdict-icon">{v.icon}</div>
        <div className="verdict-text">
          <span className="eyebrow">Data readiness · {o.form}</span>
          <h2>{v.title}</h2>
          <p>{r.reason}</p>
          <div className="progress">
            <div style={{ width: `${r.score}%` }} />
          </div>
          <span className="muted small">
            {r.score.toFixed(0)}% of issues decided (weighted by severity) · {o.decisions} decisions logged
          </span>
        </div>
        <div className="verdict-actions">
          {openTotal > 0 ? (
            <button className="btn btn-primary" onClick={() => go("review")}>
              <ListChecks size={15} /> Review {openTotal} open flags
            </button>
          ) : r.waiting > 0 ? (
            <button className="btn btn-primary" onClick={() => go("review")}>
              <ListChecks size={15} /> Record field results ({r.waiting})
            </button>
          ) : (
            <button className="btn btn-primary" onClick={() => go("log")}>
              <ListChecks size={15} /> View the cleaning log
            </button>
          )}
          {openTotal > 0 && (
            <button className="btn btn-ghost" onClick={() => setConfirm(true)}>
              <Sparkles size={15} /> Apply recommendations
            </button>
          )}
        </div>
      </section>

      <div className="tiles">
        <Tile label="Records received" value={fmt.int(o.raw_rows)} sub={`${o.raw_cols} columns`} tone={C.blue} />
        <Tile label="Final analysis records" value={fmt.int(finalN)} sub={`${fmt.int(o.raw_rows - finalN)} removed or excluded`} tone={C.brand} />
        <Tile label="Open issues" value={fmt.int(openTotal)} sub={`${r.open.critical} critical · ${r.open.high} high`} tone={openTotal ? C.red : C.green} />
        <Tile label="Awaiting field verification" value={fmt.int(r.waiting)} sub="call-backs in progress" tone={C.amber} />
      </div>

      <Card
        title="Why cleaning matters: the same survey, before and after"
        subtitle="Indicators computed on the raw export versus the cleaned data (all recommended decisions applied). This is the error decision-makers would inherit without data management."
        output="overview"
      >
        <div className="impacts">
          {o.impact.map((r) => (
            <ImpactRow key={r.key} r={r} />
          ))}
        </div>
      </Card>

      <div className="grid-2">
        <Card title="Where the records went" subtitle="Received → removed or excluded (by reason) → final dataset. Excluded records remain in the raw file.">
          <ol className="funnel">
            {o.funnel.map((s, i) => (
              <li key={i} className={s.final ? "final" : i === 0 ? "first" : "minus"}>
                <span>{s.label}</span>
                <div className="fbar">
                  <div style={{ width: `${(100 * Math.abs(s.n)) / o.raw_rows}%` }} />
                </div>
                <b>{i === 0 || s.final ? fmt.int(s.n) : `−${fmt.int(Math.abs(s.n))}`}</b>
              </li>
            ))}
          </ol>
          {o.projected_funnel.length !== o.funnel.length && (
            <p className="muted small hint">
              Applying the remaining recommendations would give a final dataset of <b>{fmt.int(o.projected_funnel[o.projected_funnel.length - 1].n)}</b> records.
            </p>
          )}
        </Card>

        <Card title="Issues found" subtitle="Total flags by check; the dark segment is still open">
          <div className="issues">
            {o.issues.map((i) => (
              <div key={i.label} className="issue-row">
                <span>{i.label}</span>
                <div className="ibar" title={`${i.open} open of ${i.total}`}>
                  <div className="done" style={{ width: `${(100 * (i.total - i.open)) / maxIssue}%` }} />
                  <div className="open" style={{ width: `${(100 * i.open) / maxIssue}%` }} />
                </div>
                <b>{i.total}</b>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid-2">
        <Card title="Supervision needed now" subtitle="Enumerators whose data shows patterns that need action this week" actions={<button className="link" onClick={() => go("enumerators")}>Full scorecard <ArrowRight size={13} /></button>}>
          {o.attention.length === 0 ? (
            <p className="muted">No enumerator needs urgent follow-up.</p>
          ) : (
            <ul className="attention">
              {o.attention.map((e) => (
                <li key={e.enumerator}>
                  <span className="avatar">
                    <Users size={14} />
                  </span>
                  <div>
                    <b>{e.enumerator}</b> <span className="muted small">· {e.flagged_pct}% of interviews flagged</span>
                    <ul>
                      {e.follow_up.map((f) => (
                        <li key={f}>{f}</li>
                      ))}
                    </ul>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Raw data integrity" subtitle="Proof that the original export was never changed">
          <div className="integrity">
            <div className="integrity-row">
              <Fingerprint size={18} />
              <div>
                <span className="muted small">SHA-256 fingerprint of the raw file</span>
                <code className="hash">{o.sha256}</code>
              </div>
            </div>
            <div className="integrity-row">
              <ShieldCheck size={18} />
              <div>
                <span className="muted small">Direct identifiers kept out of the analysis copy</span>
                <b>{o.identifiers.length ? o.identifiers.join(", ") : "none detected"}</b>
              </div>
            </div>
            <div className="integrity-row">
              <Gauge size={18} />
              <div>
                <span className="muted small">Source</span>
                <b>
                  {o.filename} · {o.source === "sample" ? "synthetic sample" : "your upload (this session only)"}
                </b>
              </div>
            </div>
            <p className="muted small">Every number on this page is recomputed as <b>clean = raw + cleaning log</b>. Re-running the log on the same raw file always gives the same result.</p>
          </div>
        </Card>
      </div>

      <Card title="Data quality by LGA" subtitle="Share of records with at least one flag">
        <div className="lga-grid">
          {o.by_lga.map((l) => (
            <div key={l.lga} className={`lga ${l.unmapped ? "unmapped" : ""}`} style={{ "--p": `${Math.min(100, l.flagged_pct * 2)}%` } as CSSProperties}>
              <span>{l.lga}</span>
              <b>{l.flagged_pct.toFixed(0)}%</b>
              <small>{l.records} records{l.unmapped ? " · not in master list" : ""}</small>
            </div>
          ))}
        </div>
      </Card>

      {confirm && <ApplyAll onClose={() => setConfirm(false)} />}
    </div>
  );
}
