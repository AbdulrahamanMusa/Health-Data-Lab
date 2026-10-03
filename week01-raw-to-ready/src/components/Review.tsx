import { Check, ClipboardCheck, Filter, PhoneCall, Search, SlidersHorizontal, Wand2 } from "lucide-react";
import { useState } from "react";

import { ACTION_LABEL, Card, Empty, Modal, SevBadge, StatusTag } from "@/components/common";
import { useSend } from "@/events";
import { useShinyInput, useShinyOutputValue } from "@/shiny";
import type { Flag, FlagFilter, FlagList } from "@/types";

const MANUAL_ACTIONS = ["corrected", "set missing", "removed", "sent for verification", "kept as valid"] as const;

function DecideDialog({ flag, onClose }: { flag: Flag; onClose: () => void }) {
  const send = useSend();
  const [action, setAction] = useState<string>(flag.rec_action);
  const [value, setValue] = useState(flag.rec_new_value ?? "");
  const [reason, setReason] = useState(flag.rec_reason);
  const valid = reason.trim() && (action !== "corrected" || value.trim());
  return (
    <Modal title={`Decide: ${flag.label}`} onClose={onClose} wide>
      <div className="kv">
        <span>Record</span>
        <b className="mono">
          row {flag.row} · {flag.record_id.slice(0, 18)}
        </b>
        <span>Variable</span>
        <b>{flag.variable}</b>
        <span>Current value</span>
        <b>{flag.value ?? "—"}</b>
        <span>Enumerator · LGA</span>
        <b>
          {flag.enumerator ?? "—"} · {flag.lga ?? "—"}
        </b>
      </div>
      <p className="detail-line">{flag.detail}</p>
      <form
        className="form"
        onSubmit={(e) => {
          e.preventDefault();
          if (!valid) return;
          send("decide", { flag_ids: [flag.flag_id], action, new_value: value, reason });
          onClose();
        }}
      >
        <div className="full field-group" role="group" aria-label="Decision">
          <span className="field-label">Decision</span>
          <div className="choices">
            {MANUAL_ACTIONS.map((a) => (
              <button type="button" key={a} className={`choice ${action === a ? "on" : ""}`} onClick={() => setAction(a)}>
                {ACTION_LABEL[a]}
                {a === flag.rec_action && <small>recommended</small>}
              </button>
            ))}
          </div>
        </div>
        {action === "corrected" && (
          <label>
            New value
            <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="Corrected value" autoFocus />
          </label>
        )}
        <label className="full">
          Reason (goes into the cleaning log)
          <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
        <div className="form-actions full">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={!valid}>
            <Check size={15} /> Log decision
          </button>
        </div>
      </form>
    </Modal>
  );
}

function VerifyDialog({ flag, onClose }: { flag: Flag; onClose: () => void }) {
  const send = useSend();
  const [outcome, setOutcome] = useState<"confirmed" | "corrected" | "excluded">("confirmed");
  const [value, setValue] = useState("");
  const [note, setNote] = useState("");
  const valid = outcome !== "corrected" || value.trim();
  return (
    <Modal title="Record the field verification result" onClose={onClose}>
      <p className="muted small">
        {flag.label}: {flag.detail}. Current value: <b>{flag.value ?? "—"}</b>
      </p>
      <form
        className="form"
        onSubmit={(e) => {
          e.preventDefault();
          if (!valid) return;
          send("verify", { flag_id: flag.flag_id, outcome, new_value: value, note });
          onClose();
        }}
      >
        <div className="full field-group" role="group" aria-label="Field verification result">
          <span className="field-label">What did the field team find?</span>
          <div className="choices">
            <button type="button" className={`choice ${outcome === "confirmed" ? "on" : ""}`} onClick={() => setOutcome("confirmed")}>
              Value confirmed
            </button>
            <button type="button" className={`choice ${outcome === "corrected" ? "on" : ""}`} onClick={() => setOutcome("corrected")}>
              Corrected value
            </button>
            <button type="button" className={`choice ${outcome === "excluded" ? "on" : ""}`} onClick={() => setOutcome("excluded")}>
              Could not confirm: exclude
            </button>
          </div>
        </div>
        {outcome === "corrected" && (
          <label>
            Corrected value
            <input value={value} onChange={(e) => setValue(e.target.value)} autoFocus />
          </label>
        )}
        <label className="full">
          Note
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Supervisor called household on 3 Oct" />
        </label>
        <div className="form-actions full">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={!valid}>
            <ClipboardCheck size={15} /> Save result
          </button>
        </div>
      </form>
    </Modal>
  );
}

export function Review() {
  const list = useShinyOutputValue<FlagList>("flag_list");
  const [filter, setFilter] = useShinyInput<FlagFilter>("flag_filter", { check: "all", severity: "all", status: "open", enumerator: "all", q: "" }, { debounceMs: 250 });
  const send = useSend();
  const [deciding, setDeciding] = useState<Flag | null>(null);
  const [verifying, setVerifying] = useState<Flag | null>(null);
  const set = (k: keyof FlagFilter) => (v: string) => setFilter({ ...filter, [k]: v });
  if (!list) return <div className="view"><div className="skeleton tall" /></div>;
  const c = list.counts;

  return (
    <div className="view">
      <div className="status-strip">
        {(["open", "awaiting verification", "resolved"] as const).map((s) => (
          <button key={s} className={`strip ${filter.status === s ? "on" : ""} s-${s.split(" ")[0]}`} onClick={() => set("status")(filter.status === s ? "all" : s)}>
            <b>{c[s]}</b>
            <span>{s === "open" ? "Open: need a decision" : s === "awaiting verification" ? "Awaiting field verification" : "Resolved"}</span>
          </button>
        ))}
      </div>

      <div className="review-layout">
        <Card title="Issue types" subtitle="Apply the protocol's recommended action to every open flag of a type">
          <ul className="groups">
            {list.groups.map((g) => (
              <li key={g.check} className={filter.check === g.check ? "on" : ""}>
                <button className="group-main" onClick={() => set("check")(filter.check === g.check ? "all" : g.check)}>
                  <SevBadge severity={g.severity} />
                  <span className="group-label">{g.label}</span>
                  <span className="group-count">
                    {g.open}/{g.total}
                  </span>
                </button>
                <div className="group-rec">
                  <span className="muted small">→ {ACTION_LABEL[g.rec_action]}</span>
                  {g.open > 0 && (
                    <button className="btn btn-ghost sm" onClick={() => send("decide", { check: g.check, action: "recommended" })}>
                      <Wand2 size={13} /> Apply to {g.open}
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Card>

        <Card
          title={`Flags (${list.shown}${list.shown > list.items.length ? `, first ${list.items.length} shown` : ""})`}
          subtitle="Nothing is changed until you log a decision. Suspicious-but-possible values go to the field team, not into the bin."
          output="flag_list"
          actions={
            <div className="filters">
              <span className="muted small">
                <Filter size={13} />
              </span>
              <select value={filter.severity} onChange={(e) => set("severity")(e.target.value)} aria-label="Severity">
                {["all", "critical", "high", "medium", "low"].map((s) => (
                  <option key={s} value={s}>
                    {s === "all" ? "All severities" : s}
                  </option>
                ))}
              </select>
              <select value={filter.enumerator} onChange={(e) => set("enumerator")(e.target.value)} aria-label="Enumerator">
                <option value="all">All enumerators</option>
                {list.enumerators.map((e) => (
                  <option key={e}>{e}</option>
                ))}
              </select>
              <div className="search">
                <Search size={14} />
                <input placeholder="Record, LGA, detail…" value={filter.q} onChange={(e) => set("q")(e.target.value)} />
              </div>
            </div>
          }
        >
          {list.items.length === 0 ? (
            <Empty>
              <ClipboardCheck size={22} /> No flags match these filters.
            </Empty>
          ) : (
            <div className="table-wrap tall">
              <table className="table flags">
                <thead>
                  <tr>
                    <th>Severity</th>
                    <th>Issue</th>
                    <th>Record</th>
                    <th>Value</th>
                    <th>Recommended</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {list.items.map((f) => (
                    <tr key={f.flag_id}>
                      <td>
                        <SevBadge severity={f.severity} />
                      </td>
                      <td>
                        <b>{f.label}</b>
                        <div className="muted small">{f.detail}</div>
                      </td>
                      <td>
                        <span className="mono">row {f.row}</span>
                        <div className="muted small">
                          {f.enumerator} · {f.lga}
                        </div>
                      </td>
                      <td className="mono">{f.value ?? "—"}</td>
                      <td>
                        <span className="rec">{ACTION_LABEL[f.rec_action]}</span>
                        {f.rec_new_value && <span className="muted small"> → {f.rec_new_value}</span>}
                      </td>
                      <td>
                        <StatusTag status={f.status} />
                        {f.decision && <div className="muted small">{ACTION_LABEL[f.decision.action]} · {f.decision.by}</div>}
                      </td>
                      <td className="row-actions">
                        {f.status === "open" && (
                          <>
                            <button className="btn btn-primary sm" onClick={() => send("decide", { flag_ids: [f.flag_id], action: "recommended" })} title={f.rec_reason}>
                              <Check size={13} /> Accept
                            </button>
                            <button className="icon-btn" title="Choose another decision" aria-label="Choose another decision" onClick={() => setDeciding(f)}>
                              <SlidersHorizontal size={15} />
                            </button>
                          </>
                        )}
                        {f.status === "awaiting verification" && (
                          <button className="btn btn-ghost sm" onClick={() => setVerifying(f)}>
                            <PhoneCall size={13} /> Field result
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
      {deciding && <DecideDialog flag={deciding} onClose={() => setDeciding(null)} />}
      {verifying && <VerifyDialog flag={verifying} onClose={() => setVerifying(null)} />}
    </div>
  );
}
