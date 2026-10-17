import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { compact, pct } from "@/format";

/* ---------------------------------------------------------------- shared */

export function useWidth<T extends HTMLElement>(fallback = 600): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(200, Math.floor(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

/** Width and height of an element. Charts in "fill" mode size themselves to their card. */
export function useBox<T extends HTMLElement>(fw = 600, fh = 240): [React.RefObject<T | null>, number, number] {
  const ref = useRef<T>(null);
  const [box, setBox] = useState([fw, fh]);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setBox([Math.max(200, Math.floor(e.contentRect.width)), Math.floor(e.contentRect.height)]));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, box[0], box[1]];
}

type Tip = { x: number; y: number; content: ReactNode } | null;

function Tooltip({ tip, width }: { tip: Tip; width: number }) {
  if (!tip) return null;
  const left = Math.min(Math.max(tip.x + 14, 4), width - 190);
  return (
    <div className="tip" style={{ left, top: Math.max(tip.y - 12, 0) }} role="status">
      {tip.content}
    </div>
  );
}

/** A clean tick step (1, 2, 2.5 or 5 x 10^n) for about `count` intervals. */
const niceStep = (v: number, count = 4) => {
  const raw = Math.max(v, 1e-9) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  return ([1, 2, 2.5, 5, 10].find((m) => m * mag >= raw) ?? 10) * mag;
};
const niceMax = (v: number, count = 4) => (v <= 0 ? 1 : Math.ceil(v / niceStep(v, count)) * niceStep(v, count));

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="legend">
      {items.map((i) => (
        <span key={i.label}>
          <i style={{ background: i.color }} />
          {i.label}
        </span>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- sparkline */

export function Sparkline({ values, color = "var(--accent)", highlight, height = 30 }: { values: (number | null)[]; color?: string; highlight?: number | null; height?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>(140);
  const vals = values.filter((v): v is number => v != null);
  if (vals.length < 2) return <div ref={ref} style={{ height }} />;
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const span = hi - lo || 1;
  const X = (i: number) => 2 + (i / (values.length - 1)) * (width - 4);
  const Y = (v: number) => 3 + (1 - (v - lo) / span) * (height - 6);
  const pts = values.map((v, i) => (v == null ? null : [X(i), Y(v)])).filter(Boolean) as number[][];
  const last = highlight ?? values.length - 1;
  const lv = values[last];
  return (
    <div ref={ref} className="spark" aria-hidden>
      <svg width={width} height={height}>
        <path d={`M${pts[0][0]},${height} L${pts.map((p) => p.join(",")).join(" L")} L${pts[pts.length - 1][0]},${height} Z`} fill={color} opacity={0.1} />
        <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke={color} strokeWidth={1.75} strokeLinejoin="round" strokeLinecap="round" />
        {lv != null && <circle cx={X(last)} cy={Y(lv)} r={3.5} fill={color} className="ring" />}
      </svg>
    </div>
  );
}

/* ---------------------------------------------------------------- line chart */

export interface Series {
  key: string;
  label: string;
  color: string;
}

export function LineChart({ data, series, height: fixedH = 240, refValue, fill }: { data: Record<string, number | string | null>[]; series: Series[]; height?: number; refValue?: number; fill?: boolean }) {
  const [ref, width, boxH] = useBox<HTMLDivElement>();
  const height = fill ? Math.max(160, boxH) : fixedH;
  const [hover, setHover] = useState<number | null>(null);
  const pad = { l: 44, r: 92, t: 12, b: 28 };
  const iw = width - pad.l - pad.r;
  const ih = height - pad.t - pad.b;
  const top = Math.max(refValue ?? 0, ...data.flatMap((d) => series.map((s) => (d[s.key] as number) ?? 0)));
  const step = niceStep(top);
  const max = Math.ceil(top / step) * step;
  const x = (i: number) => pad.l + (data.length <= 1 ? iw / 2 : (i / (data.length - 1)) * iw);
  const y = (v: number) => pad.t + ih - (v / max) * ih;
  const ticks = Array.from({ length: Math.round(max / step) + 1 }, (_, i) => i * step);
  // End labels, nudged apart only if they would overlap; dropped when too crowded (legend + tooltip carry them).
  const ends = series
    .map((s) => {
      const last = [...data].reverse().find((d) => d[s.key] != null);
      return last ? { s, v: last[s.key] as number, y: y(last[s.key] as number) } : null;
    })
    .filter(Boolean) as { s: Series; v: number; y: number }[];
  ends.sort((a, b) => a.y - b.y);
  const crowded = ends.some((e, i) => i > 0 && e.y - ends[i - 1].y < 13);
  const onMove = (e: React.MouseEvent<SVGRectElement>) => {
    const r = (e.currentTarget as SVGRectElement).getBoundingClientRect();
    const px = e.clientX - r.left;
    const i = data.length <= 1 ? 0 : Math.round((px / r.width) * (data.length - 1));
    setHover(Math.max(0, Math.min(data.length - 1, i)));
  };
  const h = hover != null ? data[hover] : null;
  return (
    <div className={`chart-stack ${fill ? "fill" : ""}`}>
      <Legend items={series.map((s) => ({ label: s.label, color: s.color }))} />
      <div className={`chart ${fill ? "fill" : ""}`} ref={ref}>
      <svg width={width} height={height} role="img" aria-label={`Line chart of ${series.map((s) => s.label).join(", ")} by month`}>
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={pad.l} x2={pad.l + iw} y1={y(t)} y2={y(t)} />
            <text className="axis" x={pad.l - 8} y={y(t) + 4} textAnchor="end">
              {Math.round(t * 100)}%
            </text>
          </g>
        ))}
        {refValue != null && refValue <= max && (
          <g>
            <line className="refline" x1={pad.l} x2={pad.l + iw} y1={y(refValue)} y2={y(refValue)} />
          </g>
        )}
        {data.map((d, i) => (
          <text key={String(d.label)} className="axis" x={x(i)} y={height - 8} textAnchor="middle">
            {data.length > 8 && width < 560 && i % 2 ? "" : String(d.label)}
          </text>
        ))}
        {hover != null && <line className="crosshair" x1={x(hover)} x2={x(hover)} y1={pad.t} y2={pad.t + ih} />}
        {series.map((s) => {
          const pts = data.map((d, i) => (d[s.key] == null ? null : [x(i), y(d[s.key] as number)])).filter(Boolean) as number[][];
          return (
            <g key={s.key}>
              <polyline fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" points={pts.map((p) => p.join(",")).join(" ")} />
              {pts.map((p, i) => (
                <circle key={i} cx={p[0]} cy={p[1]} r={pts.length === 1 ? 5 : 3.5} fill={s.color} />
              ))}
              {hover != null && h?.[s.key] != null && <circle cx={x(hover)} cy={y(h[s.key] as number)} r={5} fill={s.color} className="ring" />}
            </g>
          );
        })}
        {!crowded &&
          ends.map((e) => (
            <g key={e.s.key}>
              <circle cx={pad.l + iw + 8} cy={e.y} r={4} fill={e.s.color} />
              <text className="endlabel" x={pad.l + iw + 16} y={e.y + 4}>
                {e.s.label} {pct(e.v, 0)}
              </text>
            </g>
          ))}
        <rect x={pad.l} y={pad.t} width={iw} height={ih} fill="transparent" onMouseMove={onMove} onMouseLeave={() => setHover(null)} />
      </svg>
      <Tooltip
        width={width}
        tip={
          h && hover != null
            ? {
                x: x(hover),
                y: pad.t,
                content: (
                  <>
                    <b>{String(h.label)}</b>
                    {series.map((s) => (
                      <span key={s.key} className="tip-row">
                        <i style={{ background: s.color }} />
                        {s.label}
                        <em>{pct(h[s.key] as number | null)}</em>
                      </span>
                    ))}
                  </>
                ),
              }
            : null
        }
      />
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- horizontal bars */

export function BarList({
  items,
  target,
  format = (v: number) => pct(v),
  color = "var(--s1)",
  maxValue,
  targetLabel,
  rowHeight: fixedRow = 26,
  colorFor,
  fill,
}: {
  items: { name: string; value: number | null; sub?: string }[];
  target?: number;
  format?: (v: number) => string;
  color?: string;
  maxValue?: number;
  targetLabel?: string;
  rowHeight?: number;
  colorFor?: (v: number) => string;
  fill?: boolean;
}) {
  const [ref, width, boxH] = useBox<HTMLDivElement>(360);
  const extra = target != null ? 22 : 6;
  // In fill mode the rows share the card's height (within readable limits).
  const rowHeight = fill && boxH > 0 && items.length ? Math.max(18, Math.min(40, (boxH - extra) / items.length)) : fixedRow;
  const [tip, setTip] = useState<Tip>(null);
  const longest = Math.max(...items.map((i) => Math.min(18, i.name.length)), 4);
  const labelW = Math.min(width * 0.42, Math.max(70, longest * 7 + 14));
  const valueW = 58;
  const fit = Math.max(6, Math.floor((labelW - 10) / 6.6)); // characters that fit beside the bars
  const iw = width - labelW - valueW - 8;
  const max = maxValue ?? niceMax(Math.max(target ?? 0, ...items.map((i) => i.value ?? 0)));
  const height = items.length * rowHeight + extra;
  const top = target != null ? 18 : 2;
  const bx = (v: number) => labelW + (Math.max(0, v) / max) * iw;
  return (
    <div className={`chart ${fill ? "fill" : ""}`} ref={ref}>
      <svg width={width} height={height} role="img" aria-label="Bar chart">
        {target != null && (
          <g>
            <line className="refline" x1={bx(target)} x2={bx(target)} y1={top - 6} y2={height} />
            <text className="axis" x={bx(target)} y={11} textAnchor="middle">
              {targetLabel ?? `Target ${pct(target, 0)}`}
            </text>
          </g>
        )}
        {items.map((it, i) => {
          const yy = top + i * rowHeight;
          const bh = Math.min(24, rowHeight - 8);
          const v = it.value ?? 0;
          const w = Math.max(2, bx(v) - labelW);
          return (
            <g
              key={it.name + i}
              onMouseEnter={() => setTip({ x: bx(v), y: yy, content: <><b>{it.name}</b>{it.sub && <span className="tip-row">{it.sub}</span>}<span className="tip-row">{format(v)}</span></> })}
              onMouseLeave={() => setTip(null)}
            >
              <rect x={0} y={yy} width={width} height={rowHeight} fill="transparent" />
              <text className="cat" x={labelW - 8} y={yy + rowHeight / 2 + 4} textAnchor="end">
                {it.name.length > fit ? `${it.name.slice(0, fit - 1)}…` : it.name}
              </text>
              <path d={barPath(labelW, yy + (rowHeight - bh) / 2, w, bh)} fill={colorFor ? colorFor(v) : color} />
              <text className="val" x={labelW + w + 6} y={yy + rowHeight / 2 + 4}>
                {format(v)}
              </text>
            </g>
          );
        })}
      </svg>
      <Tooltip tip={tip} width={width} />
    </div>
  );
}

/** A bar with a 4px rounded data end and a square baseline. */
function barPath(x: number, y: number, w: number, h: number) {
  const r = Math.min(2, w / 2, h / 2);
  return `M${x},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h - r} Q${x + w},${y + h} ${x + w - r},${y + h} H${x} Z`;
}
function colPath(x: number, y: number, w: number, h: number) {
  const r = Math.min(2, w / 2, h / 2);
  return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
}

/* ---------------------------------------------------------------- columns */

export function Columns({ items, height: fixedH = 220, color = "var(--s1)", fill }: { items: { label: string; value: number }[]; height?: number; color?: string; fill?: boolean }) {
  const [ref, width, boxH] = useBox<HTMLDivElement>();
  const height = fill ? Math.max(160, boxH) : fixedH;
  const [tip, setTip] = useState<Tip>(null);
  const pad = { l: 8, r: 8, t: 22, b: 26 };
  const iw = width - pad.l - pad.r;
  const ih = height - pad.t - pad.b;
  const max = niceMax(Math.max(...items.map((i) => i.value), 1));
  const band = iw / Math.max(1, items.length);
  const bw = Math.min(46, band * 0.72);
  return (
    <div className={`chart ${fill ? "fill" : ""}`} ref={ref}>
      <svg width={width} height={height} role="img" aria-label="Column chart">
        <line className="grid" x1={pad.l} x2={pad.l + iw} y1={pad.t + ih} y2={pad.t + ih} />
        {items.map((it, i) => {
          const h = (it.value / max) * ih;
          const cx = pad.l + band * i + band / 2;
          return (
            <g key={it.label} onMouseEnter={() => setTip({ x: cx, y: pad.t + ih - h, content: <><b>{it.label}</b><span className="tip-row">{it.value.toLocaleString("en-GB")} rows</span></> })} onMouseLeave={() => setTip(null)}>
              <rect x={cx - band / 2} y={pad.t} width={band} height={ih} fill="transparent" />
              <path d={colPath(cx - bw / 2, pad.t + ih - h, bw, h)} fill={color} />
              {band > 30 && (
                <text className="val" x={cx} y={pad.t + ih - h - 6} textAnchor="middle">
                  {band >= 36 ? it.value.toLocaleString("en-GB") : compact(it.value)}
                </text>
              )}
              <text className="axis" x={cx} y={height - 8} textAnchor="middle">
                {band < 40 && i % 2 ? "" : it.label}
              </text>
            </g>
          );
        })}
      </svg>
      <Tooltip tip={tip} width={width} />
    </div>
  );
}

/* ---------------------------------------------------------------- quadrant bubble */

export function Quadrant({ points, yLimit, height: fixedH = 300, fill }: { points: { name: string; x: number; y: number; size: number }[]; yLimit: number; height?: number; fill?: boolean }) {
  const [ref, width, boxH] = useBox<HTMLDivElement>();
  const height = fill ? Math.max(200, boxH) : fixedH;
  const [tip, setTip] = useState<Tip>(null);
  const pad = { l: 48, r: 22, t: 16, b: 38 };
  const iw = width - pad.l - pad.r;
  const ih = height - pad.t - pad.b;
  const xmax = niceMax(Math.max(...points.map((p) => p.x), 0.1) * 1.08);
  const ymax = niceMax(Math.max(yLimit, ...points.map((p) => p.y)) * 1.1);
  const smax = Math.max(...points.map((p) => p.size), 1);
  const X = (v: number) => pad.l + (v / xmax) * iw;
  const Y = (v: number) => pad.t + ih - (Math.max(0, v) / ymax) * ih;
  const R = (s: number) => 5 + Math.sqrt(s / smax) * 20;
  const xMid = points.length ? [...points].sort((a, b) => a.x - b.x)[Math.floor(points.length / 2)].x : 0;
  // Label the biggest bubbles, skipping any label that would collide with one already placed.
  const labelled = new Set<string>();
  const zoneTag = [pad.l + 4, Y(yLimit) - 22, pad.l + 120, Y(yLimit) - 4];
  const boxes: number[][] = [zoneTag];
  const circles = points.map((p) => [X(p.x), Y(p.y), R(p.size), p.name] as const);
  for (const p of [...points].sort((a, b) => b.size - a.size).slice(0, 7)) {
    const w = p.name.length * 6.6;
    const box = [X(p.x) - w / 2, Y(p.y) - R(p.size) - 17, X(p.x) + w / 2, Y(p.y) - R(p.size) - 3];
    const hitsLabel = boxes.some((b) => box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1]);
    const hitsBubble = circles.some(([cx, cy, cr, n]) => n !== p.name && cx + cr > box[0] && cx - cr < box[2] && cy + cr > box[1] && cy - cr < box[3]);
    if (hitsLabel || hitsBubble) continue;
    boxes.push(box);
    labelled.add(p.name);
  }
  return (
    <div className={`chart ${fill ? "fill" : ""}`} ref={ref}>
      <svg width={width} height={height} role="img" aria-label="Districts by Penta 3 coverage and dropout">
        <rect className="quad-zone" x={pad.l} y={pad.t} width={X(xMid) - pad.l} height={Y(yLimit) - pad.t} />
        <text className="quad-label" x={pad.l + 8} y={Y(yLimit) - 8}>
          Needs most help
        </text>
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <g key={f}>
            <line className="grid" x1={pad.l} x2={pad.l + iw} y1={Y(ymax * f)} y2={Y(ymax * f)} />
            <text className="axis" x={pad.l - 8} y={Y(ymax * f) + 4} textAnchor="end">
              {Math.round(ymax * f * 100)}%
            </text>
            <text className="axis" x={X(xmax * f)} y={pad.t + ih + 16} textAnchor="middle">
              {Math.round(xmax * f * 100)}%
            </text>
          </g>
        ))}
        <line className="refline" x1={pad.l} x2={pad.l + iw} y1={Y(yLimit)} y2={Y(yLimit)} />
        <text className="axis" x={pad.l + iw} y={Y(yLimit) + 15} textAnchor="end">
          WHO dropout limit {pct(yLimit, 0)}
        </text>
        <line className="refline faint" x1={X(xMid)} x2={X(xMid)} y1={pad.t} y2={pad.t + ih} />
        <text className="axis-title" x={pad.l + iw / 2} y={height - 4} textAnchor="middle">
          Penta 3 coverage →
        </text>
        <text className="axis-title" transform={`translate(12 ${pad.t + ih / 2}) rotate(-90)`} textAnchor="middle">
          Penta 1 to 3 dropout →
        </text>
        {[...points]
          .sort((a, b) => b.size - a.size)
          .map((p) => (
            <g
              key={p.name}
              onMouseEnter={() =>
                setTip({
                  x: X(p.x),
                  y: Y(p.y),
                  content: (
                    <>
                      <b>{p.name}</b>
                      <span className="tip-row">Penta 3 coverage <em>{pct(p.x)}</em></span>
                      <span className="tip-row">Dropout <em>{pct(p.y)}</em></span>
                      <span className="tip-row">Missed Penta 3 <em>{p.size.toLocaleString("en-GB")}</em></span>
                    </>
                  ),
                })
              }
              onMouseLeave={() => setTip(null)}
            >
              <circle cx={X(p.x)} cy={Y(p.y)} r={R(p.size)} className="bubble" />
              {labelled.has(p.name) && (
                <text className="bubble-label" x={X(p.x)} y={Y(p.y) - R(p.size) - 5} textAnchor="middle">
                  {p.name}
                </text>
              )}
            </g>
          ))}
      </svg>
      <Tooltip tip={tip} width={width} />
    </div>
  );
}

/* ---------------------------------------------------------------- calibration */

export function Calibration({ bins, height = 220 }: { bins: { from: number; to: number; predicted: number; observed: number; n: number }[]; height?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>(320);
  const [tip, setTip] = useState<Tip>(null);
  const pad = { l: 40, r: 14, t: 12, b: 34 };
  const iw = width - pad.l - pad.r;
  const ih = height - pad.t - pad.b;
  const X = (v: number) => pad.l + v * iw;
  const Y = (v: number) => pad.t + ih - v * ih;
  return (
    <div className="chart" ref={ref}>
      <svg width={width} height={height} role="img" aria-label="Calibration: predicted against observed rate">
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line className="grid" x1={pad.l} x2={pad.l + iw} y1={Y(f)} y2={Y(f)} />
            <text className="axis" x={pad.l - 6} y={Y(f) + 4} textAnchor="end">
              {f * 100}%
            </text>
            <text className="axis" x={X(f)} y={pad.t + ih + 15} textAnchor="middle">
              {f * 100}%
            </text>
          </g>
        ))}
        <line className="refline faint" x1={X(0)} y1={Y(0)} x2={X(1)} y2={Y(1)} />
        <text className="axis-title" x={pad.l + iw / 2} y={height - 4} textAnchor="middle">
          Predicted risk
        </text>
        <polyline fill="none" stroke="var(--s1)" strokeWidth={2} points={bins.map((b) => `${X(b.predicted)},${Y(b.observed)}`).join(" ")} />
        {bins.map((b) => (
          <circle
            key={b.from}
            cx={X(b.predicted)}
            cy={Y(b.observed)}
            r={Math.max(4, Math.min(9, 3 + Math.sqrt(b.n) / 2))}
            fill="var(--s1)"
            className="ring"
            onMouseEnter={() => setTip({ x: X(b.predicted), y: Y(b.observed), content: <><b>{pct(b.from, 0)}–{pct(b.to, 0)} predicted</b><span className="tip-row">Average prediction <em>{pct(b.predicted, 0)}</em></span><span className="tip-row">Actually happened <em>{pct(b.observed, 0)}</em></span><span className="tip-row">Facilities <em>{b.n}</em></span></> })}
            onMouseLeave={() => setTip(null)}
          />
        ))}
      </svg>
      <Tooltip tip={tip} width={width} />
    </div>
  );
}

/* ---------------------------------------------------------------- map */

export function RiskMap({
  districts,
  points,
  selected,
  onSelect,
  height: fixedH = 420,
  fill,
}: {
  districts: { id: string; name: string; polygons: number[][][] }[];
  points: { id: string; name: string; lat: number | null; lon: number | null; band: string; risk: number; sub: string }[];
  selected?: string | null;
  onSelect?: (id: string) => void;
  height?: number;
  fill?: boolean;
}) {
  const [ref, width, boxH] = useBox<HTMLDivElement>();
  const height = fill ? Math.max(300, boxH) : fixedH;
  const [tip, setTip] = useState<Tip>(null);
  const proj = useMemo(() => {
    const all = districts.flatMap((d) => d.polygons.flat());
    if (!all.length) return null;
    const lons = all.map((p) => p[0]);
    const lats = all.map((p) => p[1]);
    const [x0, x1, y0, y1] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)];
    const k = Math.cos((((y0 + y1) / 2) * Math.PI) / 180);
    const sx = (width - 20) / ((x1 - x0) * k);
    const sy = (height - 20) / (y1 - y0);
    const s = Math.min(sx, sy);
    const ox = (width - (x1 - x0) * k * s) / 2;
    const oy = (height - (y1 - y0) * s) / 2;
    return (lon: number, lat: number) => [ox + (lon - x0) * k * s, oy + (y1 - lat) * s];
  }, [districts, width, height]);
  if (!proj) return <div className="chart empty-chart" ref={ref}>No map geometry from DHIS2.</div>;
  const order = { low: 0, medium: 1, high: 2 } as Record<string, number>;
  const pts = points.filter((p) => p.lat != null && p.lon != null).sort((a, b) => order[a.band] - order[b.band] || a.risk - b.risk);
  return (
    <div className={`chart ${fill ? "fill" : ""}`} ref={ref}>
      <svg width={width} height={height} role="img" aria-label="Map of facility risk">
        {districts.map((d) => (
          <g key={d.id}>
            {d.polygons.map((ring, i) => (
              <path key={i} className="district" d={"M" + ring.map(([lon, lat]) => proj(lon, lat).map((v) => v.toFixed(1)).join(",")).join("L") + "Z"} />
            ))}
          </g>
        ))}
        {districts.map((d) => {
          const ring = d.polygons.reduce((a, b) => (b.length > a.length ? b : a), [] as number[][]);
          if (!ring.length) return null;
          const c = ring.reduce((acc, [lon, lat]) => [acc[0] + lon / ring.length, acc[1] + lat / ring.length], [0, 0]);
          const [x, y] = proj(c[0], c[1]);
          return (
            <text key={d.id + "l"} className="district-label" x={x} y={y} textAnchor="middle">
              {d.name}
            </text>
          );
        })}
        {pts.map((p) => {
          const [x, y] = proj(p.lon as number, p.lat as number);
          return (
            <circle
              key={p.id}
              cx={x}
              cy={y}
              r={p.id === selected ? 8 : p.band === "high" ? 5.5 : 4.5}
              className={`pt b-${p.band} ${p.id === selected ? "sel" : ""}`}
              onMouseEnter={() => setTip({ x, y, content: <><b>{p.name}</b><span className="tip-row">{p.sub}</span><span className="tip-row">Risk <em>{pct(p.risk, 0)}</em></span></> })}
              onMouseLeave={() => setTip(null)}
              onClick={() => onSelect?.(p.id)}
            />
          );
        })}
      </svg>
      <Tooltip tip={tip} width={width} />
    </div>
  );
}
