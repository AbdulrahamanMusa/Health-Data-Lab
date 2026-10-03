import { Download, History, Lock, RotateCcw } from "lucide-react";
import { useState } from "react";

import { ACTION_LABEL, Card, Modal, Tile, C, fmt } from "@/components/common";
import { useSend } from "@/events";
import { useShinyOutputValue } from "@/shiny";
import type { CleaningLog, LogEntry } from "@/types";

const ACTION_TONE: Record<string, string> = {
  corrected: "ok",
  "set missing": "warn",
  removed: "danger",
  "sent for verification": "warn",
  "kept as valid": "ok",
  reverted: "",
};

function RevertDialog({ e, onClose }: { e: LogEntry; onClose: () => void }) {
  const send = useSend();
  const [reason, setReason] = useState("");
  return (
    <Modal title={`Revert entry #${e.entry}?`} onClose={onClose}>
      <p className="muted">
        The original entry stays in the log, marked as reverted, and a new reversal entry is added. The clean dataset is rebuilt without this decision.
      </p>
      <div className="kv">
        <span>Decision</span>
        <b>{ACTION_LABEL[e.action]}</b>
        <span>Record · variable</span>
        <b>
          row {e.row} · {e.variable}
        </b>
        <span>Reason</span>
        <b>{e.reason}</b>
      </div>
      <form
        className="form"
        onSubmit={(ev) => {
          ev.preventDefault();
          send("revert", { entry: e.entry, reason });
          onClose();
        }}
      >
        <label className="full">
          Why are you reverting it?
          <input value={reason} onChange={(ev) => setReason(ev.target.value)} placeholder="e.g. Supervisor confirmed the interview took place" autoFocus />
        </label>
        <div className="form-actions full">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary">
            <RotateCcw size={15} /> Revert
          </button>
        </div>
      </form>
    </Modal>
  );
}

export function Log() {
  const log = useShinyOutputValue<CleaningLog>("cleaning_log");
  const send = useSend();
  const [showSystem, setShowSystem] = useState(true);
  const [reverting, setReverting] = useState<LogEntry | null>(null);
  if (!log) return <div className="view"><div className="skeleton tall" /></div>;
  const entries = log.entries.filter((e) => showSystem || !e.changed_by.startsWith("system"));

  return (
    <div className="view">
      <div className="callout">
        <Lock size={18} />
        <div>
          <b>An append-only audit trail.</b> Every change to the data is a row here: what changed, from what to what, why, by whom and when. Nothing is ever deleted; undoing a decision adds a reversal entry. Columns follow the standard cleaning-log template, so the export drops straight into your project files.
        </div>
      </div>

      <div className="tiles">
        <Tile label="Total log entries" value={fmt.int(log.total)} tone={C.blue} icon={<History size={15} />} />
        <Tile label="Standard rules (automatic)" value={fmt.int(log.system)} sub="structure, spelling, exact duplicates" tone={C.violet} />
        <Tile label="Reviewer decisions" value={fmt.int(log.user)} sub={Object.entries(log.by_action).map(([a, n]) => `${n} ${ACTION_LABEL[a]?.toLowerCase()}`).join(" · ") || "none yet"} tone={C.brand} />
        <Tile label="Reverted" value={fmt.int(log.reverted)} sub="kept in the log" tone={C.amber} />
      </div>

      <Card
        title="Cleaning log"
        subtitle="Newest decisions first, then the automatic standard rules"
        actions={
          <>
            <label className="switch">
              <input type="checkbox" checked={showSystem} onChange={(e) => setShowSystem(e.target.checked)} />
              <span className="switch-ui" />
              <span>Show automatic rules</span>
            </label>
            <button className="btn btn-primary sm" onClick={() => send("export", { kind: "audit" })}>
              <Download size={14} /> Audit pack (.xlsx)
            </button>
          </>
        }
      >
        <div className="table-wrap tall">
          <table className="table log">
            <thead>
              <tr>
                <th>#</th>
                <th>When · who</th>
                <th>Record</th>
                <th>Variable</th>
                <th>Old → new</th>
                <th>Action</th>
                <th>Reason</th>
                <th>Field</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={`${e.entry}`} className={e.reverted ? "reverted" : ""}>
                  <td className="mono muted">{e.entry > 0 ? e.entry : "auto"}</td>
                  <td>
                    <span className="small">{fmt.time(e.date)}</span>
                    <div className="muted small">{e.changed_by}</div>
                  </td>
                  <td className="mono small">{e.row ? `row ${e.row}` : e.record_id}</td>
                  <td className="mono small">{e.variable}</td>
                  <td className="small">
                    {e.action === "kept as valid" || e.action === "sent for verification" ? (
                      <span className="muted">unchanged{e.old_value ? ` (${e.old_value})` : ""}</span>
                    ) : (
                      <>
                        <span className="old">{e.old_value ?? "—"}</span> → <b>{e.new_value || "missing"}</b>
                      </>
                    )}
                  </td>
                  <td>
                    <span className={`tag ${ACTION_TONE[e.action] ?? ""}`}>{ACTION_LABEL[e.action] ?? e.action}</span>
                    {e.reverted && <span className="tag">reverted</span>}
                  </td>
                  <td className="small reason">{e.reason}</td>
                  <td className="small">{e.verified_by_field || ""}</td>
                  <td>
                    {e.entry > 0 && !e.reverted && e.action !== "reverted" && (
                      <button className="icon-btn" title="Revert this decision" aria-label={`Revert entry ${e.entry}`} onClick={() => setReverting(e)}>
                        <RotateCcw size={15} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      {reverting && <RevertDialog e={reverting} onClose={() => setReverting(null)} />}
    </div>
  );
}
