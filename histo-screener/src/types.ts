// The JSON contract: one type per reactive_output in app.py.

export type Label = "benign" | "malignant" | "indeterminate" | "not_assessable";
export type Significance = "favours_benign" | "favours_malignant" | "neutral";

export interface ModelInfo {
  id: string;
  provider: "claude" | "gemini";
  label: string;
  note: string;
  available: boolean;
}

export interface Sample {
  id: string;
  thumb: string;
  reference_diagnosis: string;
  reference_label: "benign" | "malignant";
  site: string;
  author: string;
  license: string;
  license_url: string;
  source_url: string;
}

export interface Meta {
  models: ModelInfo[];
  samples: Sample[];
  limits: { per_session: number; max_upload_mb: number };
}

export interface Report {
  image_assessment: { is_histology: boolean; stain: string; magnification: string; quality: "adequate" | "limited" | "inadequate"; quality_notes: string };
  tissue: { site: string; tissue_type: string; confidence: "low" | "medium" | "high" };
  classification: { label: Label; confidence: number; summary: string };
  features: { name: string; observation: string; significance: Significance }[];
  differential: { diagnosis: string; likelihood: "most_likely" | "possible" | "less_likely"; reason: string }[];
  teaching_points: string[];
  next_steps: string[];
  limitations: string[];
}

export interface Result {
  model: string;
  label: string;
  provider: "claude" | "gemini";
  report?: Report;
  error?: string;
  usage?: { input_tokens?: number; output_tokens?: number; served_by?: string };
  seconds?: number;
  reference_check?: { status: "agrees" | "disagrees" | "uncommitted"; text: string };
}

export interface Case {
  id: string;
  name: string;
  source: "sample" | "upload";
  width: number;
  height: number;
  data_url: string;
  added: string;
  results: Record<string, Result>;
  reference: (Omit<Sample, "id" | "thumb">) | null;
  agreement: { agree: boolean; labels: Label[] } | null;
}

export interface Workspace {
  case: Case | null;
  history: { id: string; name: string; source: string; added: string; labels: Label[] }[];
  running: boolean;
  running_models: string[];
  used: number;
  remaining: number;
}

export interface ToastMsg {
  title: string;
  text: string;
  level: "ok" | "info" | "warn" | "danger";
}
