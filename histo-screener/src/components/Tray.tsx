import { ImagePlus, Layers } from "lucide-react";
import { useRef, useState } from "react";

import { LABEL } from "@/components/ReportView";
import { useSend } from "@/events";
import type { Meta, Workspace } from "@/types";

function toBase64(buf: ArrayBuffer) {
  let s = "";
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

export function useUpload(maxMb: number) {
  const send = useSend();
  const [error, setError] = useState<string | null>(null);
  const handle = async (file: File | undefined) => {
    setError(null);
    if (!file) return;
    if (!file.type.startsWith("image/") && !/\.(tiff?|jpe?g|png|webp|bmp)$/i.test(file.name)) return setError("Choose an image file (JPG, PNG, TIFF or WebP).");
    if (file.size > maxMb * 1024 * 1024) return setError(`Images up to ${maxMb} MB, please.`);
    send("upload", { name: file.name, b64: toBase64(await file.arrayBuffer()) });
  };
  return { handle, error };
}

export function Tray({ meta, ws }: { meta: Meta; ws: Workspace }) {
  const send = useSend();
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const { handle, error } = useUpload(meta.limits.max_upload_mb);
  const currentId = ws.case?.id;

  return (
    <aside className="tray" aria-label="Specimen tray">
      <div
        className={`drop ${drag ? "drag" : ""}`}
        role="button"
        tabIndex={0}
        onClick={() => input.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          handle(e.dataTransfer.files[0]);
        }}
      >
        <ImagePlus size={20} />
        <b>Add a slide image</b>
        <span>Drop, click, or paste (Ctrl+V)</span>
        <input ref={input} type="file" accept="image/*,.tif,.tiff" hidden onChange={(e) => handle(e.target.files?.[0])} />
      </div>
      {error && <p className="tray-error">{error}</p>}
      <p className="tray-note">No patient identifiers, please. Images stay in this session's memory only.</p>

      <h5>Teaching slides</h5>
      <div className="slides">
        {meta.samples.map((s) => (
          <button key={s.id} className={`slide ${ws.case?.reference && ws.case.name.endsWith(s.site) ? "on" : ""}`} onClick={() => send("select_sample", { id: s.id })} title={`${s.site} — open this teaching slide`}>
            <img src={s.thumb} alt={`Teaching slide: ${s.site}`} />
            <span>{s.site}</span>
          </button>
        ))}
      </div>

      {ws.history.length > 0 && (
        <>
          <h5>
            <Layers size={12} /> This session
          </h5>
          <ul className="history">
            {ws.history.map((h) => (
              <li key={h.id}>
                <button className={h.id === currentId ? "on" : ""} onClick={() => send("open_case", { id: h.id })}>
                  <span className="h-name">{h.name}</span>
                  <span className="h-labels">
                    {h.labels.length === 0 ? (
                      <i className="dot" title="Not analysed yet" />
                    ) : (
                      h.labels.map((l, i) => <i key={i} className={`dot ${LABEL[l].cls}`} title={LABEL[l].text} />)
                    )}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </aside>
  );
}
