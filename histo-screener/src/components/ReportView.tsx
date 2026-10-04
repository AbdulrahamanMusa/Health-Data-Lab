import { AlertTriangle, BookOpen, CheckCircle2, CircleHelp, Microscope, XCircle } from "lucide-react";

import type { Label, Report, Result } from "@/types";

export const LABEL: Record<Label, { text: string; cls: string }> = {
  benign: { text: "Benign", cls: "benign" },
  malignant: { text: "Malignant", cls: "malignant" },
  indeterminate: { text: "Indeterminate", cls: "indeterminate" },
  not_assessable: { text: "Not assessable", cls: "na" },
};
const SIG = { favours_benign: ["Favours benign", "benign"], favours_malignant: ["Favours malignant", "malignant"], neutral: ["Neutral", "neutral"] } as const;
const LIKELY = { most_likely: "Most likely", possible: "Possible", less_likely: "Less likely" } as const;

function Ring({ value, cls }: { value: number; cls: string }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 64 64" className={`ring ${cls}`} role="img" aria-label={`${value}% confidence`}>
      <circle cx="32" cy="32" r={r} className="ring-track" />
      <circle cx="32" cy="32" r={r} className="ring-fill" strokeDasharray={`${(c * value) / 100} ${c}`} transform="rotate(-90 32 32)" />
      <text x="32" y="36" textAnchor="middle">
        {value}
      </text>
    </svg>
  );
}

function Body({ rep }: { rep: Report }) {
  const ia = rep.image_assessment;
  return (
    <>
      <section className="rp-sec">
        <h4>Specimen</h4>
        <dl className="kv">
          <dt>Site</dt>
          <dd>
            {rep.tissue.site} <span className="muted">({rep.tissue.confidence} confidence)</span>
          </dd>
          <dt>Tissue</dt>
          <dd>{rep.tissue.tissue_type}</dd>
          <dt>Stain · magnification</dt>
          <dd>
            {ia.stain} · {ia.magnification}
          </dd>
          <dt>Image quality</dt>
          <dd>
            <span className={`q q-${ia.quality}`}>{ia.quality}</span> {ia.quality_notes}
          </dd>
        </dl>
      </section>
      {rep.features.length > 0 && (
        <section className="rp-sec">
          <h4>Morphological features</h4>
          <ul className="features">
            {rep.features.map((f, i) => (
              <li key={i}>
                <div>
                  <b>{f.name}</b>
                  <span className={`sig sig-${SIG[f.significance][1]}`}>{SIG[f.significance][0]}</span>
                </div>
                <p>{f.observation}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
      {rep.differential.length > 0 && (
        <section className="rp-sec">
          <h4>Differential diagnosis</h4>
          <ol className="ddx">
            {rep.differential.map((d, i) => (
              <li key={i}>
                <b>{d.diagnosis}</b> <span className={`lk lk-${d.likelihood}`}>{LIKELY[d.likelihood]}</span>
                <p>{d.reason}</p>
              </li>
            ))}
          </ol>
        </section>
      )}
      {rep.teaching_points.length > 0 && (
        <section className="rp-sec teach">
          <h4>
            <BookOpen size={13} /> Teaching points
          </h4>
          <ul>
            {rep.teaching_points.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </section>
      )}
      {rep.next_steps.length > 0 && (
        <section className="rp-sec">
          <h4>What a pathologist would do next</h4>
          <ul>
            {rep.next_steps.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </section>
      )}
      {rep.limitations.length > 0 && (
        <section className="rp-sec limits">
          <h4>Limitations of this read</h4>
          <ul>
            {rep.limitations.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

export function ReportView({ result, running, modelLabel, compact }: { result?: Result; running?: boolean; modelLabel?: string; compact?: boolean }) {
  if (running) {
    return (
      <div className="report pending">
        <div className="rp-wait">
          <Microscope size={26} />
          <b>{modelLabel} is reading the slide…</b>
          <span className="muted">This usually takes 10–40 seconds.</span>
          <div className="shimmer-lines">
            <i />
            <i />
            <i />
          </div>
        </div>
      </div>
    );
  }
  if (!result) {
    return (
      <div className="report empty">
        <Microscope size={26} />
        <b>No report yet</b>
        <span className="muted">Choose a model and press Analyse.</span>
      </div>
    );
  }
  if (result.error) {
    return (
      <div className="report errored">
        <AlertTriangle size={22} />
        <b>{result.label}</b>
        <p>{result.error}</p>
      </div>
    );
  }
  const rep = result.report!;
  const l = LABEL[rep.classification.label];
  const ref = result.reference_check;
  return (
    <article className={`report ${compact ? "compact" : ""}`}>
      <header className={`rp-head v-${l.cls}`}>
        <div>
          <span className="rp-kicker">AI screening impression</span>
          <h3>{l.text}</h3>
          <span className="rp-model">
            {result.label}
            {result.seconds != null && <> · {result.seconds}s</>}
            {result.usage?.served_by && result.usage.served_by !== result.model && <> · answered by {result.usage.served_by}</>}
          </span>
        </div>
        <Ring value={rep.classification.confidence} cls={l.cls} />
      </header>
      <p className="rp-summary">{rep.classification.summary}</p>
      {ref && (
        <div className={`refcheck rc-${ref.status}`}>
          {ref.status === "agrees" ? <CheckCircle2 size={15} /> : ref.status === "disagrees" ? <XCircle size={15} /> : <CircleHelp size={15} />}
          {ref.text}
        </div>
      )}
      {!rep.image_assessment.is_histology && <div className="refcheck rc-disagrees">The model does not think this is a histology image.</div>}
      <Body rep={rep} />
    </article>
  );
}
