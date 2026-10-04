import { CheckCircle2, Cpu, ExternalLink, Eye, EyeOff, KeyRound, Loader2, ShieldCheck, X, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { useSend } from "@/events";
import type { KeyStatus, Meta } from "@/types";

const STORE = "histo-own-keys";
type Provider = "claude" | "gemini";
const INFO: Record<Provider, { name: string; models: string; placeholder: string; url: string; urlLabel: string }> = {
  claude: { name: "Anthropic (Claude)", models: "Claude Opus 5.5 · Sonnet 5.5", placeholder: "sk-ant-…", url: "https://console.anthropic.com/settings/keys", urlLabel: "Get a key at console.anthropic.com" },
  gemini: { name: "Google (Gemini)", models: "Gemini 3.8 Flash · 3.1 Pro", placeholder: "AIza…", url: "https://aistudio.google.com/apikey", urlLabel: "Get a key at aistudio.google.com" },
};

/** The visitor's keys for this page session (memory only; gone on reload unless remembered). */
let sessionKeys: Record<Provider, string> = { claude: "", gemini: "" };
export function setSessionKeys(k: Record<Provider, string>) {
  sessionKeys = { ...k };
}

/** Keys remembered on this device (only if the visitor opted in). */
export function readStoredKeys(): Record<Provider, string> | null {
  try {
    const raw = localStorage.getItem(STORE);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
function storeKeys(keys: Record<Provider, string> | null) {
  try {
    if (keys && (keys.claude || keys.gemini)) localStorage.setItem(STORE, JSON.stringify(keys));
    else localStorage.removeItem(STORE);
  } catch {
    // Storage blocked: keys stay for this session only.
  }
}

function KeyField({ provider, value, onChange, status }: { provider: Provider; value: string; onChange: (v: string) => void; status: KeyStatus }) {
  const send = useSend();
  const [show, setShow] = useState(false);
  const [testing, setTesting] = useState(false);
  const info = INFO[provider];
  useEffect(() => setTesting(false), [status.check]);
  return (
    <div className="keyfield">
      <div className="kf-head">
        <div>
          <b>{info.name}</b>
          <small>{info.models}</small>
        </div>
        {status.source === "you" ? (
          <span className="kf-state you">Your key {status.hint}</span>
        ) : status.server ? (
          <span className="kf-state server">Using the shared demo key</span>
        ) : (
          <span className="kf-state none">No key</span>
        )}
      </div>
      <div className="kf-input">
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={status.source === "you" ? "Saved — paste a new key to replace it" : info.placeholder}
          autoComplete="off"
          spellCheck={false}
          aria-label={`${info.name} API key`}
        />
        <button type="button" className="icon" onClick={() => setShow(!show)} aria-label={show ? "Hide key" : "Show key"} title={show ? "Hide" : "Show"}>
          {show ? <EyeOff size={15} /> : <Eye size={15} />}
        </button>
        <button
          type="button"
          className="btn ghost sm"
          disabled={status.source !== "you" || testing}
          onClick={() => {
            setTesting(true);
            send("test_key", { provider });
          }}
          title={status.source === "you" ? "Check this key with a free request" : "Save the key first"}
        >
          {testing ? <Loader2 size={14} className="spin" /> : null} Test
        </button>
      </div>
      <div className="kf-foot">
        <a href={info.url} target="_blank" rel="noopener noreferrer">
          {info.urlLabel} <ExternalLink size={11} />
        </a>
        {status.check && (
          <span className={status.check.ok ? "ok" : "bad"}>
            {status.check.ok ? <CheckCircle2 size={13} /> : <XCircle size={13} />} {status.check.message}
          </span>
        )}
      </div>
    </div>
  );
}

/** MedGemma needs no key: it runs through Ollama on the machine hosting the app. */
function LocalModelCard({ local }: { local: Meta["local"] }) {
  const [copied, setCopied] = useState(false);
  const cmd = `ollama pull ${local.model}`;
  return (
    <div className="keyfield local">
      <div className="kf-head">
        <div>
          <b>
            <Cpu size={14} /> MedGemma (free, open model)
          </b>
          <small>Google's medical model · runs locally, no key, no cost</small>
        </div>
        {local.ready ? <span className="kf-state you">Ready</span> : <span className="kf-state none">Not set up</span>}
      </div>
      {local.ready ? (
        <p className="local-note">
          <CheckCircle2 size={13} /> <b>{local.model}</b> is running on this computer through Ollama. Images analysed with it never leave the machine. On a computer without a GPU a report can take a few minutes.
        </p>
      ) : !local.host_is_local ? (
        <p className="local-note">The app's server can't reach its MedGemma service right now. Check that Ollama is running at the configured address.</p>
      ) : (
        <ol className="local-steps">
          <li>
            Install Ollama from{" "}
            <a href="https://ollama.com/download" target="_blank" rel="noopener noreferrer">
              ollama.com/download <ExternalLink size={11} />
            </a>{" "}
            {local.reason === "not_downloaded" && <em>(done: Ollama is running)</em>}
          </li>
          <li>
            Download the model (about 3.3 GB):{" "}
            <button
              type="button"
              className="cmd"
              title="Copy command"
              onClick={() => {
                navigator.clipboard?.writeText(cmd).then(() => setCopied(true), () => {});
              }}
            >
              <code>{cmd}</code> <small>{copied ? "copied" : "copy"}</small>
            </button>
          </li>
          <li>Leave Ollama running. This app picks the model up within 15 seconds.</li>
          <li className="muted">On the hosted demo this isn't available: MedGemma runs on the computer that runs the app, so run the app on your own computer to use it.</li>
        </ol>
      )}
    </div>
  );
}

export function KeysDialog({ meta, onClose }: { meta: Meta; onClose: () => void }) {
  const send = useSend();
  const stored = readStoredKeys();
  const [draft, setDraft] = useState<Record<Provider, string>>({ claude: "", gemini: "" });
  const [remember, setRemember] = useState(!!stored);
  const k = meta.keys;
  const hasOwn = k.claude.source === "you" || k.gemini.source === "you";

  const save = () => {
    // An empty box keeps the key already saved for that provider.
    const next = { claude: draft.claude.trim() || sessionKeys.claude, gemini: draft.gemini.trim() || sessionKeys.gemini };
    setSessionKeys(next);
    send("set_keys", next);
    storeKeys(remember ? next : null);
    setDraft({ claude: "", gemini: "" });
  };

  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal keys" role="dialog" aria-modal="true" aria-labelledby="keys-title">
        <button className="modal-x" onClick={onClose} aria-label="Close">
          <X size={16} />
        </button>
        <div className="modal-icon hema">
          <KeyRound size={22} />
        </div>
        <h2 id="keys-title">Use your own API keys</h2>
        <p>Add a key for either provider (or both). Analyses then run on your own account, with no shared limits. Or use MedGemma, the free open model, with no key at all.</p>
        <KeyField provider="claude" value={draft.claude} onChange={(v) => setDraft({ ...draft, claude: v })} status={k.claude} />
        <KeyField provider="gemini" value={draft.gemini} onChange={(v) => setDraft({ ...draft, gemini: v })} status={k.gemini} />
        <LocalModelCard local={meta.local} />
        <label className="check">
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
          <span>
            Remember on this device
            <small>Stored in this browser only. Don't tick this on a shared or public computer.</small>
          </span>
        </label>
        <div className="privacy-note">
          <ShieldCheck size={16} />
          <p>
            Your key travels over the encrypted connection to this app's server and is used only for your requests in this session. It is never stored on the server, written to logs, or shown back on this page. Requests are billed to your account by Anthropic or Google.
          </p>
        </div>
        <div className="modal-actions">
          {hasOwn && (
            <button
              className="btn ghost"
              onClick={() => {
                setSessionKeys({ claude: "", gemini: "" });
                send("set_keys", { claude: "", gemini: "" });
                storeKeys(null);
                setDraft({ claude: "", gemini: "" });
              }}
            >
              Remove my keys
            </button>
          )}
          <button className="btn primary" disabled={!draft.claude.trim() && !draft.gemini.trim() && remember === !!stored} onClick={save}>
            Save keys
          </button>
        </div>
      </div>
    </div>
  );
}
