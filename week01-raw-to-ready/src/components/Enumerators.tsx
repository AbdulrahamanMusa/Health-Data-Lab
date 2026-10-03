import type { CSSProperties } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { C, Card, axisProps, tooltipProps } from "@/components/common";
import { useShinyOutputValue } from "@/shiny";
import type { EnumRow } from "@/types";

const STATUS: Record<EnumRow["status"], { label: string; tone: string }> = {
  "act now": { label: "Act now", tone: "danger" },
  watch: { label: "Watch", tone: "warn" },
  good: { label: "Good", tone: "ok" },
};

export function Enumerators() {
  const board = useShinyOutputValue<{ rows: EnumRow[]; team_median: number | null }>("enumerator_board");
  if (!board) return <div className="view"><div className="skeleton tall" /></div>;
  const rows = board.rows;
  const chart = [...rows].sort((a, b) => (a.median_duration ?? 0) - (b.median_duration ?? 0));
  const counts = { "act now": 0, watch: 0, good: 0 } as Record<EnumRow["status"], number>;
  rows.forEach((r) => counts[r.status]++);

  return (
    <div className="view">
      <div className="callout">
        <div>
          <b>Run this daily during fieldwork, not only at the end.</b> Problems are fixable while teams are still in the field. Share it with supervisors as support, not punishment: most patterns point to a training or equipment need.
        </div>
      </div>

      <div className="status-strip">
        {(Object.keys(STATUS) as EnumRow["status"][]).map((s) => (
          <div key={s} className={`strip static s-${STATUS[s].tone}`}>
            <b>{counts[s]}</b>
            <span>{STATUS[s].label}</span>
          </div>
        ))}
      </div>

      <Card title="Median interview length by enumerator" subtitle={`Team median ${board.team_median ?? "–"} min. Interviews far below the line are too short to have covered the questionnaire.`}>
        <div className="chart-260">
          <ResponsiveContainer>
            <BarChart data={chart} margin={{ left: 0, right: 10 }}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="enumerator" {...axisProps} interval={0} angle={-30} textAnchor="end" height={50} />
              <YAxis {...axisProps} width={36} unit="m" />
              <Tooltip {...tooltipProps} formatter={(v) => [`${v} min`, "Median duration"]} />
              {board.team_median && <ReferenceLine y={board.team_median} stroke={C.axis} strokeDasharray="4 3" label={{ value: "team median", fill: C.axis, fontSize: 11, position: "insideTopRight" }} />}
              <Bar dataKey="median_duration" radius={[4, 4, 0, 0]}>
                {chart.map((r) => (
                  <Cell key={r.enumerator} fill={r.status === "act now" ? C.red : r.status === "watch" ? C.amber : C.brand} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card title="Supervision scorecard" subtitle="Sorted by who needs attention first">
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Enumerator</th>
                <th>Status</th>
                <th className="num">Interviews</th>
                <th className="num">Median min</th>
                <th className="w20">Flagged</th>
                <th className="num">Short</th>
                <th className="num">Same GPS spot</th>
                <th className="num">Night</th>
                <th className="num">MUAC rounded</th>
                <th>Recommended follow-up</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.enumerator}>
                  <td className="name">{r.enumerator}</td>
                  <td>
                    <span className={`tag ${STATUS[r.status].tone}`}>{STATUS[r.status].label}</span>
                  </td>
                  <td className="num">{r.interviews}</td>
                  <td className={`num ${r.median_duration != null && r.team_median != null && r.median_duration < r.team_median / 2 ? "bad" : ""}`}>{r.median_duration ?? "–"}</td>
                  <td>
                    <div className="meter-cell">
                      <div className="mini-meter">
                        <div style={{ width: `${r.flagged_pct}%`, background: r.flagged_pct > 30 ? C.red : r.flagged_pct > 10 ? C.amber : C.brand } as CSSProperties} />
                      </div>
                      <span>{r.flagged_pct.toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className={`num ${r.short ? "bad" : ""}`}>{r.short}</td>
                  <td className={`num ${r.desk ? "bad" : ""}`}>{r.desk}</td>
                  <td className="num">{r.night}</td>
                  <td className={`num ${r.muac_rounding != null && r.muac_rounding >= 60 ? "bad" : ""}`}>{r.muac_rounding == null ? "–" : `${r.muac_rounding.toFixed(0)}%`}</td>
                  <td className="small">{r.follow_up.length ? r.follow_up.join(" · ") : <span className="muted">No action needed</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small hint">
          MUAC rounded: share of readings ending in .0 or .5. Around 20% is expected by chance; much higher suggests the tape is not being read to the millimetre.
        </p>
      </Card>
    </div>
  );
}
