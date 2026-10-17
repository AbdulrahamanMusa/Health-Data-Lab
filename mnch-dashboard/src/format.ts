export const pct = (v: number | null | undefined, digits = 1) => (v == null || Number.isNaN(v) ? "–" : `${(v * 100).toFixed(digits)}%`);
export const num = (v: number | null | undefined) => (v == null || Number.isNaN(v) ? "–" : Math.round(v).toLocaleString("en-GB"));
export const compact = (v: number) => (Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(Math.abs(v) >= 10000 ? 0 : 1)}K` : `${Math.round(v)}`);

export function when(iso: string | null | undefined) {
  if (!iso) return "–";
  const d = new Date(iso);
  return d.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export const SHADE_TEXT: Record<string, string> = { on: "At or above target", near: "Within 20 pts of target", far: "More than 20 pts below target" };
export const BAND_TEXT: Record<string, string> = { high: "High", medium: "Medium", low: "Low" };
