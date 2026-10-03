import { Database, Download, FileSpreadsheet, Fingerprint, ShieldAlert, ShieldCheck, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

import { Card } from "@/components/common";
import { useSend } from "@/events";
import { useShinyInput, useShinyOutputValue } from "@/shiny";
import type { Dataset } from "@/types";

const ROLE_LABEL: Record<string, string> = {
  enumerator: "Enumerator",
  consent: "Consent",
  lga: "LGA",
  ward: "Ward",
  hh_id: "Household ID",
  lat: "GPS latitude",
  lon: "GPS longitude",
  age_months: "Child age (months)",
  muac: "MUAC (cm)",
  oedema: "Oedema",
  penta1: "Penta1",
  penta3: "Penta3",
  anc_attended: "Attended ANC",
  anc_visits: "ANC visits",
};

function toBase64(buf: ArrayBuffer) {
  let s = "";
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

export function Data() {
  const d = useShinyOutputValue<Dataset>("dataset");
  const [includeGps, setIncludeGps] = useShinyInput<boolean>("include_gps", false, { debounceMs: 0 });
  const send = useSend();
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  if (!d) return <div className="view"><div className="skeleton tall" /></div>;

  const handle = async (file: File | undefined) => {
    setError(null);
    if (!file) return;
    if (!/\.(csv|xlsx|xls)$/i.test(file.name)) return setError("Upload a KoboToolbox or ODK export as .xlsx or .csv.");
    if (file.size > d.max_mb * 1024 * 1024) return setError(`The file is larger than ${d.max_mb} MB.`);
    send("upload", { name: file.name, b64: toBase64(await file.arrayBuffer()) });
  };

  return (
    <div className="view">
      <div className="grid-2">
        <Card title="Current dataset" subtitle="The raw file is fingerprinted on arrival and never modified">
          <div className="dataset-card">
            <div className="ds-icon">
              <Database size={20} />
            </div>
            <div>
              <b>{d.filename}</b>
              <div className="muted small">
                {d.source === "sample" ? "Synthetic sample survey" : "Your upload"} · {d.rows.toLocaleString()} rows × {d.cols} columns · received {d.received.replace("T", " ").slice(0, 16)}
              </div>
            </div>
          </div>
          <div className="integrity-row">
            <Fingerprint size={18} />
            <div>
              <span className="muted small">SHA-256 fingerprint. Re-hash your copy of the file: if the value matches, it is the same raw data.</span>
              <code className="hash">{d.sha256}</code>
            </div>
          </div>
          <div className="row">
            <button className="btn btn-ghost sm" onClick={() => send("use_sample", {})}>
              <FileSpreadsheet size={14} /> Load the sample survey
            </button>
            <button className="btn btn-ghost sm" onClick={() => send("export", { kind: "sample" })}>
              <Download size={14} /> Download sample export
            </button>
          </div>
        </Card>

        <Card title="Check your own export" subtitle="KoboToolbox or ODK export, .xlsx or .csv">
          <div
            className={`drop ${drag ? "drag" : ""}`}
            role="button"
            tabIndex={0}
            onClick={() => input.current?.click()}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              handle(e.dataTransfer.files[0]);
            }}
          >
            <UploadCloud size={26} />
            <b>Drop your export here, or click to choose</b>
            <span className="muted small">Group prefixes like "child/muac_cm" are handled. Checks run on the fields they recognise.</span>
            <input ref={input} type="file" accept=".csv,.xlsx,.xls" hidden onChange={(e) => handle(e.target.files?.[0])} />
          </div>
          {error && <p className="error">{error}</p>}
          <div className="privacy">
            <ShieldAlert size={16} />
            <p>
              <b>Before uploading real data:</b> files are processed in this browser session's memory only and are never saved, but they are sent to the app's server. Under the Nigeria Data Protection Act, upload identifiable health data only with your organisation's approval, or de-identify it first.
            </p>
          </div>
        </Card>
      </div>

      <div className="grid-2">
        <Card title="Fields recognised" subtitle="Which standard checks can run on this export">
          <div className="roles">
            {Object.entries(ROLE_LABEL).map(([role, label]) => (
              <div key={role} className={`role ${d.roles[role] ? "found" : ""}`}>
                <span>{label}</span>
                <code>{d.roles[role] ?? "not found"}</code>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Privacy in exports" subtitle="Data minimisation: share only what the analysis needs">
          <div className="integrity-row">
            <ShieldCheck size={18} />
            <div>
              <span className="muted small">Direct identifiers detected: kept in raw only, never in the analysis copy or any export</span>
              <b>{d.identifiers.length ? d.identifiers.join(", ") : "none detected"}</b>
            </div>
          </div>
          <label className="switch">
            <input type="checkbox" checked={includeGps} onChange={(e) => setIncludeGps(e.target.checked)} />
            <span className="switch-ui" />
            <span>Include household GPS in exports</span>
          </label>
          <p className="muted small">Household coordinates can identify a family. Leave this off for anything shared outside the data team; aggregate to ward instead.</p>
        </Card>
      </div>

      <Card title="Column profile of the raw export" subtitle="Missing values per column, as received">
        <div className="table-wrap tall">
          <table className="table">
            <thead>
              <tr>
                <th>Column</th>
                <th className="w30">Missing</th>
                <th className="num">Unique values</th>
                <th>Example</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {d.profile.map((c) => (
                <tr key={c.column}>
                  <td className="mono small">{c.column}</td>
                  <td>
                    <div className="meter-cell">
                      <div className="mini-meter">
                        <div style={{ width: `${c.missing_pct}%` }} />
                      </div>
                      <span>{c.missing_pct.toFixed(1)}%</span>
                    </div>
                  </td>
                  <td className="num">{c.unique.toLocaleString()}</td>
                  <td className="small muted">{c.identifier ? "•••• hidden ••••" : c.example ?? "—"}</td>
                  <td>
                    {c.identifier && <span className="tag danger">identifier</span>}
                    {c.system && <span className="tag">system</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
