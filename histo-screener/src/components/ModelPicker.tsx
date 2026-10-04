import { Lock } from "lucide-react";

import type { ModelInfo } from "@/types";

export function ModelPicker({ models, value, onChange, label = "Model" }: { models: ModelInfo[]; value: string; onChange: (id: string) => void; label?: string }) {
  return (
    <div className="picker" role="radiogroup" aria-label={label}>
      {models.map((m) => (
        <button
          key={m.id}
          role="radio"
          aria-checked={value === m.id}
          disabled={!m.available}
          className={`pick p-${m.provider} ${value === m.id ? "on" : ""}`}
          onClick={() => onChange(m.id)}
          title={m.available ? m.note : `Not configured: add the ${m.provider === "claude" ? "ANTHROPIC_API_KEY" : "GEMINI_API_KEY"} on the server`}
        >
          <span className="pick-dot" />
          <span className="pick-text">
            <b>{m.label}</b>
            <small>{m.available ? m.note : "Not configured"}</small>
          </span>
          {!m.available && <Lock size={12} />}
        </button>
      ))}
    </div>
  );
}

export function firstAvailable(models: ModelInfo[], provider?: string) {
  return (models.find((m) => m.available && (!provider || m.provider === provider)) ?? models.find((m) => !provider || m.provider === provider) ?? models[0])?.id ?? "";
}
