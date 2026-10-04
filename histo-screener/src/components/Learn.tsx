import { ArrowRight, CheckCircle2, GraduationCap, RotateCcw, Sparkles, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { ReportView } from "@/components/ReportView";
import { Stage } from "@/components/Stage";
import { useSend } from "@/events";
import type { Meta, Workspace } from "@/types";

const ATLAS = [
  { name: "Circumscription", benign: "Smooth, well-defined border; often a capsule.", malignant: "Irregular, infiltrative edge that blends into surrounding tissue." },
  { name: "Architecture", benign: "Orderly, recognisable organisation of the tissue of origin.", malignant: "Loss of normal organisation: sheets, cords or disorganised glands." },
  { name: "Nuclear pleomorphism", benign: "Nuclei uniform in size and shape.", malignant: "Nuclei vary markedly in size, shape and staining." },
  { name: "Nucleus-to-cytoplasm ratio", benign: "Normal, with ample cytoplasm.", malignant: "Increased: large nuclei crowd a thin rim of cytoplasm." },
  { name: "Hyperchromasia", benign: "Fine, even chromatin.", malignant: "Dark, coarse, clumped chromatin." },
  { name: "Mitoses", benign: "Rare and normal-looking.", malignant: "Frequent, sometimes atypical (tripolar, bizarre) figures." },
  { name: "Necrosis", benign: "Usually absent.", malignant: "Tumour necrosis, often central in fast-growing lesions." },
  { name: "Invasion", benign: "Respects tissue boundaries (e.g. basement membrane).", malignant: "Breaches boundaries into stroma, vessels or nerves." },
];

export function Learn({ meta, ws, model }: { meta: Meta; ws: Workspace; model: string }) {
  const send = useSend();
  const [idx, setIdx] = useState(0);
  const [guess, setGuess] = useState<"benign" | "malignant" | null>(null);
  const [score, setScore] = useState({ right: 0, total: 0 });
  const order = useMemo(() => [...meta.samples].sort(() => Math.random() - 0.5), [meta.samples]);
  const sample = order[idx % order.length];
  const modelInfo = meta.models.find((m) => m.id === model);

  useEffect(() => {
    send("select_sample", { id: sample.id });
    setGuess(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sample.id]);

  const c = ws.case && ws.case.reference?.reference_diagnosis === sample.reference_diagnosis ? ws.case : null;
  const ai = c ? Object.values(c.results).find((r) => r.model === model) ?? Object.values(c.results)[0] : undefined;
  const running = ws.running && ws.running_models.length > 0;

  const answer = (g: "benign" | "malignant") => {
    if (guess) return;
    setGuess(g);
    setScore((s) => ({ right: s.right + (g === sample.reference_label ? 1 : 0), total: s.total + 1 }));
  };

  return (
    <div className="learn">
      <div className="learn-main">
        <Stage c={c} scanning={running} scanLabels={running ? [modelInfo?.label ?? "the model"] : []} empty={<span>Loading slide…</span>} compact />
        <div className="quiz">
          <div className="quiz-head">
            <span className="kicker">
              <GraduationCap size={14} /> Slide {(idx % order.length) + 1} of {order.length}
            </span>
            <span className="score">
              Score <b>{score.right}</b>/{score.total}
            </span>
          </div>
          <h2>Benign or malignant?</h2>
          <p className="muted">Study the slide: zoom in on the nuclei, then look at the border and architecture. Site: {sample.site}.</p>
          <div className="answers">
            {(["benign", "malignant"] as const).map((g) => (
              <button
                key={g}
                className={`answer a-${g} ${guess === g ? "picked" : ""} ${guess && sample.reference_label === g ? "correct" : ""}`}
                onClick={() => answer(g)}
                disabled={!!guess}
              >
                {g === "benign" ? "Benign" : "Malignant"}
              </button>
            ))}
          </div>
          {guess && (
            <div className={`reveal ${guess === sample.reference_label ? "right" : "wrong"}`}>
              {guess === sample.reference_label ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
              <div>
                <b>{guess === sample.reference_label ? "Correct." : "Not quite."}</b> Reference diagnosis: <b>{sample.reference_diagnosis}</b> ({sample.reference_label}).
                <small>
                  Image: {sample.author}, {sample.license}, via Wikimedia Commons.
                </small>
              </div>
            </div>
          )}
          <div className="quiz-actions">
            {guess && !ai && (
              <button className="btn primary" disabled={running || !modelInfo?.available} onClick={() => send("analyse", { models: [model] })} title={modelInfo?.available ? "" : "Model not configured on this server"}>
                <Sparkles size={15} /> Ask {modelInfo?.label ?? "the AI"} to explain
              </button>
            )}
            <button className="btn ghost" onClick={() => setIdx((i) => i + 1)}>
              Next slide <ArrowRight size={15} />
            </button>
            {score.total > 0 && (
              <button className="btn ghost" onClick={() => setScore({ right: 0, total: 0 })} title="Reset score">
                <RotateCcw size={14} />
              </button>
            )}
          </div>
        </div>
      </div>
      {guess && (ai || running) && (
        <div className="learn-ai">
          <ReportView result={ai} running={running && !ai} modelLabel={modelInfo?.label} compact />
        </div>
      )}
      <section className="atlas">
        <h2>Feature atlas</h2>
        <p className="muted">The morphological clues pathologists weigh when separating benign from malignant lesions. No single feature decides; the pattern does.</p>
        <div className="atlas-grid">
          {ATLAS.map((a) => (
            <div key={a.name} className="atlas-card">
              <h3>{a.name}</h3>
              <p>
                <span className="sig sig-benign">Benign</span> {a.benign}
              </p>
              <p>
                <span className="sig sig-malignant">Malignant</span> {a.malignant}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
