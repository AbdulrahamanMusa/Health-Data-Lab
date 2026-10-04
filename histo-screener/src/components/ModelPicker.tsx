import { Check, ChevronDown, Lock } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import type { ModelInfo } from "@/types";

const VENDOR: Record<ModelInfo["provider"], string> = { claude: "Anthropic", gemini: "Google", medgemma: "Free · local" };

const lockedNote = (m: ModelInfo) => (m.provider === "medgemma" ? "Not set up on this computer" : "Needs an API key");
const lockedTitle = (m: ModelInfo) =>
  m.provider === "medgemma" ? "Runs locally through Ollama: see API keys at the top for setup" : `Needs a ${m.provider === "claude" ? "Anthropic" : "Google Gemini"} API key: open API keys at the top`;

/** A compact dropdown, so the list of models doesn't push the report down. */
export function ModelPicker({ models, value, onChange, label = "Model" }: { models: ModelInfo[]; value: string; onChange: (id: string) => void; label?: string }) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const btn = useRef<HTMLButtonElement>(null);
  const id = useId();
  const current = models.find((m) => m.id === value) ?? models[0];

  useEffect(() => {
    if (!open) return;
    setActive(Math.max(0, models.findIndex((m) => m.id === value)));
    list.current?.focus();
    const close = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const shut = () => {
    setOpen(false);
    btn.current?.focus();
  };
  const choose = (m: ModelInfo) => {
    if (!m.available) return;
    onChange(m.id);
    shut();
  };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      shut();
    } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const step = e.key === "ArrowDown" ? 1 : -1;
      setActive((i) => (i + step + models.length) % models.length);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      choose(models[active]);
    } else if (e.key === "Tab") {
      setOpen(false);
    }
  };

  if (!current) return null;
  return (
    <div className={`picker ${open ? "open" : ""}`} ref={root}>
      <button
        ref={btn}
        type="button"
        className={`picker-btn p-${current.provider}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        aria-label={`${label}: ${current.label}`}
        onClick={() => setOpen(!open)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            setOpen(true);
          }
        }}
      >
        <span className="pick-dot" />
        <span className="pick-text">
          <b>{current.label}</b>
          <small>{current.available ? current.note : lockedNote(current)}</small>
        </span>
        <ChevronDown size={16} className="chev" />
      </button>
      {open && (
        <ul className="picker-menu" role="listbox" id={id} aria-label={label} tabIndex={-1} ref={list} onKeyDown={onKey} aria-activedescendant={`${id}-${active}`}>
          {models.map((m, i) => (
            <li
              key={m.id}
              id={`${id}-${i}`}
              role="option"
              aria-selected={m.id === value}
              aria-disabled={!m.available}
              className={`pick p-${m.provider} ${m.id === value ? "on" : ""} ${i === active ? "active" : ""} ${m.available ? "" : "locked"}`}
              onMouseEnter={() => setActive(i)}
              onClick={() => choose(m)}
              title={m.available ? m.note : lockedTitle(m)}
            >
              <span className="pick-dot" />
              <span className="pick-text">
                <b>{m.label}</b>
                <small>{m.available ? m.note : lockedNote(m)}</small>
              </span>
              <span className="pick-vendor">{VENDOR[m.provider]}</span>
              {m.id === value ? <Check size={14} className="pick-mark" /> : !m.available ? <Lock size={12} className="pick-mark" /> : <span className="pick-mark" />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function firstAvailable(models: ModelInfo[], provider?: string) {
  return (models.find((m) => m.available && (!provider || m.provider === provider)) ?? models.find((m) => !provider || m.provider === provider) ?? models[0])?.id ?? "";
}
