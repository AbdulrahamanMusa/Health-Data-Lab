// The JSON contract: one type per reactive_output in app.py.

export type Shade = "on" | "near" | "far" | null;
export type PageId = "overview" | "districts" | "actions" | "risk" | "connection";

export interface Filters {
  district: string;
  chiefdom: string;
  month: string;
}

export interface Meta {
  source: { host: string; server: string; version: string; data_to: string | null; refreshed_at: string; live: boolean; refreshing: boolean; error: string | null };
  districts: string[];
  chiefdoms: { id: string; name: string; district: string }[];
  months: { id: string; label: string }[];
  outcomes: { id: string; label: string; short: string; question: string; definition: string; threshold: number }[];
  version: number;
}

export interface Kpi {
  id: string;
  label: string;
  value: number | null;
  note: string;
  status: Shade;
  icon: string;
  spark: (number | null)[];
  spark_on: number | null;
}

export interface TrendPoint {
  month: string;
  label: string;
  ANC1: number | null;
  ANC4: number | null;
  PENTA3: number | null;
  MEASLES: number | null;
}

export interface NamedValue {
  name: string;
  value: number | null;
  district?: string;
}

export interface OverviewView {
  page: "overview";
  kpis: Kpi[];
  trend: TrendPoint[];
  penta3_by_district: NamedValue[];
  penta3_target: number;
  findings: { topic: string; text: string }[];
}

export interface ScoreRow {
  id: string;
  district: string;
  chiefdom: string;
  anc1: number | null;
  anc4: number | null;
  anc_dropout: number | null;
  penta3: number | null;
  penta_dropout: number | null;
  measles: number | null;
  reporting: number | null;
  missed: number | null;
  shade: Record<string, Shade>;
}

export interface DistrictsView {
  page: "districts";
  rows: ScoreRow[];
  top_missed: NamedValue[];
  total: Record<"anc1" | "anc4" | "anc_dropout" | "penta3" | "penta_dropout" | "measles" | "reporting" | "missed", number | null> | null;
}

export interface ActionsView {
  page: "actions";
  actions: { topic: string; text: string }[];
  quadrant: { name: string; x: number; y: number; size: number }[];
  reporting_by_district: NamedValue[];
  reporting_target: number;
  penta3_target: number;
  over100: { district: string; chiefdom: string; anc1: number | null; penta1: number | null; penta1_doses: number | null }[];
}

export interface ConnectionView {
  page: "connection";
  source: { host: string; server: string; version: string; data_to: string; refreshed_at: string; live: boolean; rows: number; chiefdoms: number; periods: string; seconds: number };
  catalogue: { code: string; name: string; id: string; area: string; target: number; denominator: string }[];
  rows_by_month: { month: string; label: string; value: number }[];
}

export interface Driver {
  feature: string;
  label: string;
  value: string;
  effect: number;
}

export interface FacilityRisk {
  id: string;
  name: string;
  chiefdom: string;
  district: string;
  type: string;
  lat: number | null;
  lon: number | null;
  risk: number;
  band: "high" | "medium" | "low";
  now: number | null;
  reporting: number | null;
  drivers: Driver[];
}

export interface RiskView {
  page: "risk";
  outcome: string;
  definition: { label: string; short: string; question: string; definition: string; threshold: number };
  scored_on: [string, string];
  summary: { scored: number; high: number; medium: number; expected: number };
  validation: {
    train_rows: number;
    test_rows: number;
    final_rows: number;
    base_rate: number;
    auc: number;
    baseline_auc: number;
    brier: number;
    accuracy: number;
    baseline_accuracy: number;
    top10_precision: number;
    top10_n: number;
    test_window: [string, string];
    calibration: { from: number; to: number; predicted: number; observed: number; n: number }[];
    coefficients: { feature: string; label: string; odds_ratio: number }[];
  };
  facilities: FacilityRisk[];
  map: { id: string; name: string; polygons: number[][][] }[];
}

export type View = OverviewView | DistrictsView | ActionsView | RiskView | ConnectionView;
