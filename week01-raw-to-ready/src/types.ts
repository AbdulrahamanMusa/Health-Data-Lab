// The JSON contract: one type per reactive_output in app.py.
import type { Severity } from "@/components/common";

export interface Stat {
  num: number;
  den: number;
  value: number | null;
}

export interface Impact {
  key: string;
  label: string;
  definition: string;
  better: "up" | "down";
  raw: Stat;
  clean: Stat;
  projected: Stat;
  bias: number | null;
}

export interface Readiness {
  verdict: "not ready" | "ready with caveats" | "ready";
  reason: string;
  score: number;
  open: Record<Severity, number>;
  waiting: number;
  total: number;
}

export interface FunnelStep {
  label: string;
  n: number;
  final?: boolean;
}

export interface EnumRow {
  enumerator: string;
  interviews: number;
  median_duration: number | null;
  team_median: number | null;
  flagged_pct: number;
  short: number;
  desk: number;
  night: number;
  muac_rounding: number | null;
  follow_up: string[];
  status: "act now" | "watch" | "good";
}

export interface Overview {
  form: string;
  source: "sample" | "upload";
  filename: string;
  sha256: string;
  received: string;
  raw_rows: number;
  raw_cols: number;
  readiness: Readiness;
  funnel: FunnelStep[];
  projected_funnel: FunnelStep[];
  impact: Impact[];
  issues: { label: string; total: number; open: number }[];
  by_lga: { lga: string; records: number; flagged_pct: number; unmapped: boolean }[];
  decisions: number;
  attention: EnumRow[];
  identifiers: string[];
}

export interface Flag {
  flag_id: string;
  row: number;
  record_id: string;
  check: string;
  label: string;
  severity: Severity;
  variable: string;
  value: string | null;
  detail: string;
  rec_action: string;
  rec_new_value: string | null;
  rec_reason: string;
  enumerator: string | null;
  lga: string | null;
  status: "open" | "awaiting verification" | "resolved";
  decision: { action: string; new_value: string | null; reason: string; by: string; entry: number } | null;
}

export interface FlagList {
  items: Flag[];
  shown: number;
  groups: { check: string; label: string; severity: Severity; total: number; open: number; rec_action: string; rec_reason: string }[];
  enumerators: string[];
  counts: Record<"open" | "awaiting verification" | "resolved", number>;
}

export interface LogEntry {
  entry: number;
  row: number | null;
  record_id: string;
  flag_id: string | null;
  check: string;
  check_label: string | null;
  variable: string;
  old_value: string | null;
  new_value: string | null;
  reason: string;
  action: string;
  verified_by_field: string;
  changed_by: string;
  date: string;
  reverted: boolean;
}

export interface CleaningLog {
  entries: LogEntry[];
  total: number;
  system: number;
  user: number;
  reverted: number;
  by_action: Record<string, number>;
}

export interface Dataset {
  filename: string;
  source: "sample" | "upload";
  sha256: string;
  received: string;
  rows: number;
  cols: number;
  profile: { column: string; missing_pct: number; unique: number; example: string | null; identifier: boolean; system: boolean }[];
  roles: Record<string, string | null>;
  identifiers: string[];
  max_mb: number;
}

export interface ToastMsg {
  title: string;
  text: string;
  level: "ok" | "info" | "warn" | "danger";
}

export type FlagFilter = { check: string; severity: string; status: string; enumerator: string; q: string };
