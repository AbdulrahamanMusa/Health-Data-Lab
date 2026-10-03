import { X } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import { useEffect } from "react";

import { useShinyOutputError, useShinyOutputStatus } from "@/shiny";

// Chart colours are hex, not CSS variables: Recharts writes them into SVG
// attributes. setChartTheme() swaps them; the app remounts on a theme change.
export type ThemeName = "light" | "dark";
export type Severity = "critical" | "high" | "medium" | "low";

const PALETTES = {
  light: {
    C: { brand: "#0f766e", blue: "#2563eb", violet: "#7c3aed", red: "#dc2626", orange: "#ea580c", amber: "#d97706", green: "#16a34a", grid: "#e5e7eb", axis: "#6b7280", neutral: "#cbd5e1", raw: "#94a3b8" },
    tooltip: { bg: "#ffffff", border: "#e5e7eb", text: "#374151", label: "#111827", cursor: "rgba(15,23,42,0.04)" },
  },
  dark: {
    C: { brand: "#2dd4bf", blue: "#60a5fa", violet: "#a78bfa", red: "#f87171", orange: "#fb923c", amber: "#fbbf24", green: "#4ade80", grid: "#263244", axis: "#8b98a9", neutral: "#475569", raw: "#64748b" },
    tooltip: { bg: "#111827", border: "#334155", text: "#cbd5e1", label: "#f8fafc", cursor: "rgba(148,163,184,0.08)" },
  },
} as const;
type Palette = (typeof PALETTES)[ThemeName];

function chrome(p: Palette) {
  return {
    axisProps: { stroke: p.C.axis, tick: { fill: p.C.axis, fontSize: 11 }, tickLine: false, axisLine: { stroke: p.C.grid } },
    tooltipProps: {
      contentStyle: { background: p.tooltip.bg, border: `1px solid ${p.tooltip.border}`, borderRadius: 8, color: p.tooltip.text, fontSize: 12, boxShadow: "0 8px 24px rgba(15,23,42,0.12)" },
      labelStyle: { color: p.tooltip.label, fontWeight: 600 },
      cursor: { fill: p.tooltip.cursor },
    },
  };
}

export let C: Palette["C"] = PALETTES.light.C;
export let SEV: Record<Severity, string> = { critical: C.red, high: C.orange, medium: C.amber, low: C.blue };
export let axisProps = chrome(PALETTES.light).axisProps;
export let tooltipProps = chrome(PALETTES.light).tooltipProps;

export function setChartTheme(t: ThemeName) {
  const p = PALETTES[t];
  C = p.C;
  SEV = { critical: p.C.red, high: p.C.orange, medium: p.C.amber, low: p.C.blue };
  ({ axisProps, tooltipProps } = chrome(p));
}

export const fmt = {
  int: (n: number | null | undefined) => (n == null ? "–" : Math.round(n).toLocaleString()),
  pct: (n: number | null | undefined, d = 1) => (n == null ? "–" : `${n.toFixed(d)}%`),
  signed: (n: number | null | undefined, d = 1) => (n == null ? "–" : `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toFixed(d)}`),
  time: (iso: string) => (iso ? iso.replace("T", " ").slice(0, 16) : ""),
};

export const ACTION_LABEL: Record<string, string> = {
  corrected: "Corrected",
  "set missing": "Set to missing",
  removed: "Excluded",
  "sent for verification": "Sent to field",
  "kept as valid": "Kept as valid",
  reverted: "Reverted",
};

export function Card({ title, subtitle, output, ready = true, actions, className = "", children }: { title?: ReactNode; subtitle?: ReactNode; output?: string; ready?: boolean; actions?: ReactNode; className?: string; children: ReactNode }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <div>
            {title && <h3>{title}</h3>}
            {subtitle && <p className="muted small">{subtitle}</p>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {output ? (
        <OutputBody output={output} ready={ready}>
          {children}
        </OutputBody>
      ) : (
        children
      )}
    </section>
  );
}

function OutputBody({ output, ready, children }: { output: string; ready: boolean; children: ReactNode }) {
  const status = useShinyOutputStatus(output);
  const error = useShinyOutputError(output);
  if (error) return <div className="output-error">{error.message}</div>;
  if (!ready) return <div className="skeleton" />;
  return <div className={status === "recalculating" ? "recalculating" : "settled"}>{children}</div>;
}

export function Tile({ label, value, sub, tone, icon }: { label: string; value: ReactNode; sub?: ReactNode; tone?: string; icon?: ReactNode }) {
  return (
    <div className="tile" style={{ "--tone": tone ?? C.brand } as CSSProperties}>
      {icon && <div className="tile-icon">{icon}</div>}
      <span className="tile-label">{label}</span>
      <b className="tile-value">{value}</b>
      {sub && <span className="tile-sub">{sub}</span>}
    </div>
  );
}

export function SevBadge({ severity }: { severity: Severity | string }) {
  return (
    <span className="sev" style={{ "--c": SEV[severity as Severity] ?? C.blue } as CSSProperties}>
      {severity}
    </span>
  );
}

export function StatusTag({ status }: { status: string }) {
  const cls = status === "open" ? "danger" : status === "awaiting verification" ? "warn" : "ok";
  return <span className={`tag ${cls}`}>{status}</span>;
}

export function Modal({ title, onClose, children, wide }: { title: ReactNode; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "wide" : ""}`} role="dialog" aria-modal="true" aria-label={typeof title === "string" ? title : undefined}>
        <header>
          <h3>{title}</h3>
          <button className="icon-btn" aria-label="Close" onClick={onClose}>
            <X size={16} />
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}
