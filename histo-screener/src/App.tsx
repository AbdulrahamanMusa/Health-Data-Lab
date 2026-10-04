import { AlertTriangle, Columns2, FileDown, GraduationCap, KeyRound, Microscope, Monitor, Moon, ScanSearch, ShieldAlert, Sparkles, Sun, X } from "lucide-react";
import type { ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { KeysDialog, readStoredKeys, setSessionKeys } from "@/components/Keys";
import { Learn } from "@/components/Learn";
import { ModelPicker, firstAvailable } from "@/components/ModelPicker";
import { LABEL, ReportView } from "@/components/ReportView";
import { Stage } from "@/components/Stage";
import { Tray, useUpload } from "@/components/Tray";
import { EventsProvider, useSend } from "@/events";
import { useShinyInitialized, useShinyMessageHandler, useShinyOutputStatus, useShinyOutputValue } from "@/shiny";
import { type ThemeMode, useTheme } from "@/theme";
import type { Meta, ToastMsg, Workspace } from "@/types";

type Mode = "screen" | "compare" | "learn";
const MODES: { id: Mode; label: string; icon: ReactNode }[] = [
  { id: "screen", label: "Screen", icon: <ScanSearch size={15} /> },
  { id: "compare", label: "Compare models", icon: <Columns2 size={15} /> },
  { id: "learn", label: "Learn", icon: <GraduationCap size={15} /> },
];
const THEMES: { mode: ThemeMode; icon: ReactNode; label: string }[] = [
  { mode: "light", icon: <Sun size={14} />, label: "Light" },
  { mode: "dark", icon: <Moon size={14} />, label: "Dark" },
  { mode: "system", icon: <Monitor size={14} />, label: "System" },
];
const ACCEPT_KEY = "histo-disclaimer-accepted";

function KeepOutputsBound() {
  useShinyOutputStatus("meta");
  useShinyOutputStatus("workspace");
  return null;
}

function Disclaimer({ onAccept }: { onAccept: () => void }) {
  const [ok, setOk] = useState(false);
  return (
    <div className="modal-back">
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="disc-title">
        <div className="modal-icon">
          <ShieldAlert size={22} />
        </div>
        <h2 id="disc-title">For research and education only</h2>
        <p>This tool uses general-purpose AI models to describe histology images. Its output is <b>not a diagnosis</b> and must not be used for clinical decisions. Diagnosis requires a qualified pathologist reviewing the full specimen with clinical context.</p>
        <ul>
          <li>Do not upload images containing patient names, numbers or other identifiers.</li>
          <li>Images are processed in memory for your session only and sent to the selected AI provider (Anthropic or Google) for analysis.</li>
          <li>Models can be wrong, including with high confidence.</li>
        </ul>
        <label className="check">
          <input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} />
          <span>I understand and will use this for research or learning only.</span>
        </label>
        <button className="btn primary wide" disabled={!ok} onClick={onAccept}>
          Continue
        </button>
      </div>
    </div>
  );
}

function ScreenMode({ meta, ws }: { meta: Meta; ws: Workspace }) {
  const send = useSend();
  const [model, setModel] = useState(() => firstAvailable(meta.models));
  const info = meta.models.find((m) => m.id === model);
  // When keys change, move off a model that has just become (or stayed) unavailable.
  useEffect(() => {
    if (!info?.available && meta.models.some((m) => m.available)) setModel(firstAvailable(meta.models));
  }, [meta.models, info?.available]);
  const result = ws.case?.results[model];
  const running = ws.running_models.includes(model);
  const anyReport = ws.case && Object.values(ws.case.results).some((r) => r.report);
  const others = ws.case ? Object.values(ws.case.results).filter((r) => r.model !== model && r.report) : [];

  return (
    <div className="screen">
      <Tray meta={meta} ws={ws} />
      <Stage
        c={ws.case}
        scanning={ws.running_models.length > 0}
        scanLabels={ws.running_models.map((id) => meta.models.find((m) => m.id === id)?.label ?? id)}
        empty={
          <>
            <Microscope size={40} />
            <b>Place a slide on the stage</b>
            <span>Open a teaching slide from the tray, or add your own image.</span>
          </>
        }
      />
      <aside className="panel" aria-label="Analysis">
        <div className="panel-top">
          <h5>Read with</h5>
          <ModelPicker models={meta.models} value={model} onChange={setModel} />
          <button className="btn primary wide" disabled={!ws.case || ws.running || !info?.available} onClick={() => send("analyse", { models: [model] })}>
            <Sparkles size={16} /> {ws.case ? `Analyse with ${info?.label ?? "model"}` : "Choose a slide first"}
          </button>
          <span className="quota">
            {ws.remaining} of {meta.limits.per_session} analyses left this session
          </span>
        </div>
        <div className="panel-body">
          <ReportView result={result} running={running} modelLabel={info?.label} />
          {others.length > 0 && (
            <div className="others">
              <span>Also read by:</span>
              {others.map((o) => (
                <button key={o.model} className={`mini v-${LABEL[o.report!.classification.label].cls}`} onClick={() => setModel(o.model)}>
                  {o.label}: {LABEL[o.report!.classification.label].text}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="panel-foot">
          <button className="btn ghost" disabled={!anyReport} onClick={() => send("export_report", {})}>
            <FileDown size={15} /> Export report
          </button>
          <span className="muted small">Not for clinical use</span>
        </div>
      </aside>
    </div>
  );
}

function CompareMode({ meta, ws }: { meta: Meta; ws: Workspace }) {
  const send = useSend();
  const [a, setA] = useState(() => firstAvailable(meta.models, "claude"));
  const [b, setB] = useState(() => firstAvailable(meta.models, "gemini"));
  const ia = meta.models.find((m) => m.id === a);
  const ib = meta.models.find((m) => m.id === b);
  useEffect(() => {
    const avail = meta.models.filter((m) => m.available);
    if (!ia?.available && avail.length) setA(avail[0].id);
    if (!ib?.available && avail.length) setB((avail.find((m) => m.provider === "gemini") ?? avail[avail.length - 1]).id);
  }, [meta.models, ia?.available, ib?.available]);
  const ra = ws.case?.results[a];
  const rb = ws.case?.results[b];
  const both = ra?.report && rb?.report;
  const agree = both && ra!.report!.classification.label === rb!.report!.classification.label;
  const canRun = ws.case && !ws.running && a !== b && ia?.available && ib?.available;

  return (
    <div className="compare">
      <div className="compare-top">
        <Stage
          c={ws.case}
          scanning={ws.running_models.length > 0}
          scanLabels={ws.running_models.map((id) => meta.models.find((m) => m.id === id)?.label ?? id)}
          empty={
            <>
              <Columns2 size={36} />
              <b>Compare two AI readers on one slide</b>
              <span>Choose a teaching slide or upload one in Screen mode, then run both models here.</span>
            </>
          }
          compact
        />
        <div className="compare-ctl">
          <h2>Two readers, one slide</h2>
          <p className="muted">Each model gets the same image and the same instructions. Agreement builds confidence; disagreement is exactly where a human expert should look.</p>
          <button className="btn primary wide" disabled={!canRun} onClick={() => send("analyse", { models: [a, b] })}>
            <Sparkles size={16} /> Run both readers
          </button>
          {a === b && <p className="warn-text">Pick two different models.</p>}
          {both && (
            <div className={`agree ${agree ? "yes" : "no"}`}>
              {agree ? "The readers agree" : "The readers disagree"}
              <span>
                {LABEL[ra!.report!.classification.label].text} ({ra!.report!.classification.confidence}%) vs {LABEL[rb!.report!.classification.label].text} ({rb!.report!.classification.confidence}%)
              </span>
            </div>
          )}
        </div>
      </div>
      <div className="compare-cols">
        {[
          { id: a, set: setA, info: ia, r: ra, tag: "Reader A" },
          { id: b, set: setB, info: ib, r: rb, tag: "Reader B" },
        ].map((col) => (
          <section key={col.tag} className="col">
            <div className="col-head">
              <span className="col-tag">{col.tag}</span>
              <ModelPicker models={meta.models} value={col.id} onChange={col.set} label={col.tag} />
            </div>
            <ReportView result={col.r} running={ws.running_models.includes(col.id)} modelLabel={col.info?.label} compact />
          </section>
        ))}
      </div>
    </div>
  );
}

type Toast = ToastMsg & { id: number };

const hasOwnKey = (meta: Meta) => meta.keys.claude.source === "you" || meta.keys.gemini.source === "you";

function Shell() {
  const initialized = useShinyInitialized();
  const meta = useShinyOutputValue<Meta>("meta");
  const ws = useShinyOutputValue<Workspace>("workspace");
  const [mode, setMode] = useState<Mode>("screen");
  const { mode: theme, setMode: setTheme } = useTheme();
  const [accepted, setAccepted] = useState(() => {
    try {
      return localStorage.getItem(ACCEPT_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(0);
  const { handle: uploadFile } = useUpload(meta?.limits.max_upload_mb ?? 12);
  const [keysOpen, setKeysOpen] = useState(false);
  const send = useSend();

  // Re-send keys the visitor chose to remember on this device (once, quietly).
  // Wait for the first server output: by then every input binding is live, so the send can't be dropped.
  const restored = useRef(false);
  useEffect(() => {
    if (!initialized || !meta || restored.current) return;
    restored.current = true;
    const stored = readStoredKeys();
    if (stored && (stored.claude || stored.gemini)) {
      setSessionKeys(stored);
      send("set_keys", { ...stored, silent: true });
    }
  }, [initialized, meta, send]);

  const pushToast = useCallback((t: ToastMsg) => {
    const id = ++nextId.current;
    setToasts((x) => [...x.slice(-2), { ...t, id }]);
    setTimeout(() => setToasts((x) => x.filter((y) => y.id !== id)), 6000);
  }, []);
  useShinyMessageHandler<ToastMsg>("toast", pushToast);
  useShinyMessageHandler<{ filename: string; mime: string; text: string }>("download", ({ filename, mime, text }) => {
    const url = URL.createObjectURL(new Blob([text], { type: mime }));
    const el = Object.assign(document.createElement("a"), { href: url, download: filename });
    document.body.appendChild(el);
    el.click();
    el.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  });

  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const file = Array.from(e.clipboardData?.files ?? []).find((f) => f.type.startsWith("image/"));
      if (file) uploadFile(file);
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [uploadFile]);

  if (!initialized || !meta || !ws) {
    return (
      <div className="boot">
        <Microscope className="boot-icon" size={36} />
        <span>Preparing the slide stage…</span>
      </div>
    );
  }
  const noModels = !meta.models.some((m) => m.available);
  const learnModel = firstAvailable(meta.models);

  return (
    <>
      <KeepOutputsBound />
      <header className="bar">
        <div className="brand">
          <span className="mark">
            <Microscope size={18} />
          </span>
          <div>
            <b>Histopathology Screener</b>
            <span>AI-assisted slide reading · Health Data Lab</span>
          </div>
        </div>
        <nav className="modes" aria-label="Mode">
          {MODES.map((m) => (
            <button key={m.id} className={mode === m.id ? "on" : ""} aria-current={mode === m.id ? "page" : undefined} onClick={() => setMode(m.id)}>
              {m.icon}
              <span>{m.label}</span>
            </button>
          ))}
        </nav>
        <div className="bar-right">
          <button className={`keybtn ${hasOwnKey(meta) ? "own" : ""}`} onClick={() => setKeysOpen(true)} title="Use your own Anthropic or Gemini API key">
            <KeyRound size={14} />
            <span>API keys</span>
            <i className={`kdot ${hasOwnKey(meta) ? "on" : noModels ? "off" : ""}`} />
          </button>
          <span className="ruo" title="Research use only">
            <ShieldAlert size={13} /> Research &amp; education only
          </span>
          <div className="themes" role="radiogroup" aria-label="Colour theme">
            {THEMES.map((t) => (
              <button key={t.mode} role="radio" aria-checked={theme === t.mode} aria-label={`${t.label} theme`} title={`${t.label} theme`} className={theme === t.mode ? "on" : ""} onClick={() => setTheme(t.mode)}>
                {t.icon}
              </button>
            ))}
          </div>
        </div>
      </header>
      {noModels && (
        <div className="banner">
          <AlertTriangle size={15} /> To run AI analysis, add your own Anthropic or Gemini API key. You can browse slides and use Learn mode without one.
          <button className="btn primary sm" onClick={() => setKeysOpen(true)}>
            <KeyRound size={14} /> Add API key
          </button>
        </div>
      )}
      <main className={`main m-${mode}`}>
        {mode === "screen" && <ScreenMode meta={meta} ws={ws} />}
        {mode === "compare" && <CompareMode meta={meta} ws={ws} />}
        {mode === "learn" && <Learn meta={meta} ws={ws} model={learnModel} />}
      </main>
      <footer className="credits">
        Teaching slides from Wikimedia Commons:{" "}
        {[...new Set(meta.samples.map((s) => `${s.author} (${s.license})`))].join(" · ")}. AI output may be wrong; not a medical device.
      </footer>
      {keysOpen && <KeysDialog meta={meta} onClose={() => setKeysOpen(false)} />}
      {!accepted && (
        <Disclaimer
          onAccept={() => {
            try {
              localStorage.setItem(ACCEPT_KEY, "1");
            } catch {
              // Non-fatal: the notice will show again next visit.
            }
            setAccepted(true);
          }}
        />
      )}
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
    </>
  );
}

export default function App() {
  return (
    <EventsProvider>
      <Shell />
    </EventsProvider>
  );
}
