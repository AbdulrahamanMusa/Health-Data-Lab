import { Maximize, Minus, Plus, ScanLine, ShieldCheck, Square } from "lucide-react";
import type { ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import type { Case } from "@/types";

/** A microscope-style slide viewer: wheel zoom around the cursor, drag to pan, fit / 1:1. */
export function Stage({ c, scanning, scanLabels, empty, compact }: { c: Case | null; scanning: boolean; scanLabels: string[]; empty: ReactNode; compact?: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  const [view, setView] = useState({ scale: 1, x: 0, y: 0 });
  const [fit, setFit] = useState(1);
  const drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);

  const fitToBox = useCallback(() => {
    const el = box.current;
    if (!el || !c) return;
    const s = Math.min((el.clientWidth - 48) / c.width, (el.clientHeight - 48) / c.height, 4);
    setFit(s);
    setView({ scale: s, x: (el.clientWidth - c.width * s) / 2, y: (el.clientHeight - c.height * s) / 2 });
  }, [c?.id, c?.width, c?.height]);

  useEffect(() => {
    fitToBox();
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(fitToBox);
    ro.observe(el);
    return () => ro.disconnect();
  }, [fitToBox]);

  const zoomAt = (factor: number, cx?: number, cy?: number) => {
    const el = box.current;
    if (!el) return;
    const px = cx ?? el.clientWidth / 2;
    const py = cy ?? el.clientHeight / 2;
    setView((v) => {
      const scale = Math.min(Math.max(v.scale * factor, fit * 0.5), 8);
      const k = scale / v.scale;
      return { scale, x: px - (px - v.x) * k, y: py - (py - v.y) * k };
    });
  };

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (!c) return;
      e.preventDefault();
      const r = el.getBoundingClientRect();
      zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - r.left, e.clientY - r.top);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  });

  const oneToOne = () => {
    const el = box.current;
    if (!el || !c) return;
    setView({ scale: 1, x: (el.clientWidth - c.width) / 2, y: (el.clientHeight - c.height) / 2 });
  };

  return (
    <div className={`stage ${compact ? "compact" : ""}`}>
      <div
        ref={box}
        className={`stage-view ${drag.current ? "grabbing" : ""}`}
        onPointerDown={(e) => {
          if (!c) return;
          (e.target as Element).setPointerCapture?.(e.pointerId);
          drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
        }}
        onPointerMove={(e) => {
          const d = drag.current;
          if (d) setView((v) => ({ ...v, x: d.vx + e.clientX - d.x, y: d.vy + e.clientY - d.y }));
        }}
        onPointerUp={() => (drag.current = null)}
        onDoubleClick={fitToBox}
        aria-label="Slide viewer. Scroll to zoom, drag to pan, double-click to fit."
      >
        {c ? (
          <img
            src={c.data_url}
            alt={c.name}
            draggable={false}
            style={{ width: c.width, height: c.height, transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})` }}
          />
        ) : (
          <div className="stage-empty">{empty}</div>
        )}
        {c && scanning && (
          <div className="scan" aria-live="polite">
            <div className="scan-band" />
            <div className="scan-label">
              <ScanLine size={15} /> Reading tissue with {scanLabels.join(" and ")}…
            </div>
          </div>
        )}
      </div>
      {c && (
        <>
          <div className="stage-chip">
            <b>{c.name}</b>
            <span>
              {c.width}×{c.height}px
            </span>
            <span className="clean">
              <ShieldCheck size={12} /> metadata removed
            </span>
          </div>
          <div className="stage-tools" role="toolbar" aria-label="Zoom">
            <button onClick={() => zoomAt(1 / 1.3)} aria-label="Zoom out" title="Zoom out">
              <Minus size={16} />
            </button>
            <span className="zoom-read">{Math.round((view.scale / fit) * 100)}%</span>
            <button onClick={() => zoomAt(1.3)} aria-label="Zoom in" title="Zoom in">
              <Plus size={16} />
            </button>
            <i />
            <button onClick={fitToBox} aria-label="Fit to view" title="Fit to view">
              <Maximize size={15} />
            </button>
            <button onClick={oneToOne} aria-label="Actual pixels" title="Actual pixels (1:1)">
              <Square size={14} />
            </button>
          </div>
        </>
      )}
    </div>
  );
}
