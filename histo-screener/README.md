# Histopathology Screener

AI-assisted screening of histology images for **research and medical education**.
Vision models read the same slide with the same instructions and fill the same
structured report, so their answers can be compared side by side: **Claude**
(Anthropic) and **Gemini** (Google) through their APIs, and **MedGemma**, Google's free
open medical model, running locally with no API key.

> Not a medical device. Output is not a diagnosis and must not be used for clinical
> decisions. Diagnosis requires a qualified pathologist reviewing the full specimen.

## What it does

- **Screen**: open a teaching slide or upload an image (drop, click or paste), zoom and pan
  on the slide stage, and get a structured report: benign / malignant / indeterminate with
  a confidence score, specimen and image-quality assessment, morphological features (each
  marked as favouring benign or malignant), differential diagnosis, teaching points,
  next steps and limitations. Export the report as printable HTML.
- **Compare models**: run two readers on the same slide. Agreement builds confidence;
  disagreement is where a human expert should look.
- **Learn**: a benign-or-malignant quiz on the teaching slides with a running score, the
  reference diagnosis, an optional AI explanation, and a feature atlas.

Teaching slides carry a reference diagnosis, so every AI read of them is checked against it.

## Models

| Option | Default model ID | Environment variable to override |
|---|---|---|
| Claude Opus 5.5 | `claude-opus-5-5` | `CLAUDE_MODEL` |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | `CLAUDE_FAST_MODEL` |
| Gemini 3.8 Flash | `gemini-3.8-flash` | `GEMINI_MODEL` |
| Gemini 3.1 Pro (preview) | `gemini-3.1-pro-preview` | `GEMINI_PRO_MODEL` |
| MedGemma 4B (local) | `medgemma:4b` | `MEDGEMMA_MODEL` |

### MedGemma: free and local

[MedGemma](https://huggingface.co/collections/google/medgemma-release) runs through
[Ollama](https://ollama.com) on the machine that runs the app, so slides never leave that
machine and there is no per-call cost:

```bash
ollama pull medgemma:4b      # about 3.3 GB, once
python -m shiny run app.py   # MedGemma appears as ready within 15 seconds
```

Ollama is expected at `http://127.0.0.1:11434`; set `OLLAMA_HOST` to use another machine
(for example a GPU server). On a CPU-only computer a report takes a few minutes; a GPU makes
it seconds. Free web hosts such as Render's free plan don't have the memory to run it, so on
the hosted demo the option shows setup steps instead. MedGemma is a 4B model: expect weaker
answers than the large API models, and treat it, like them, as a teaching aid.
Its use is governed by Google's
[Health AI Developer Foundations terms](https://developers.google.com/health-ai-developer-foundations/terms).

### API keys

Visitors can paste their own Anthropic and/or Gemini key under **API keys** in the top
bar. Each key can be checked with **Test** and is used only for that visitor's session:
it is never written to disk or logs and is never sent back to the page (only the last
four characters are shown). Ticking **Remember on this device** keeps it in that
browser's localStorage. Analyses on a visitor's own key don't count toward the limits below.

The host can also set `ANTHROPIC_API_KEY` and/or `GEMINI_API_KEY` as fallback keys. With
no key from either source, a model is locked and the app runs in demo mode (slides and
Learn mode work; analysis is disabled). Claude requests use structured outputs and server-side
refusal fallbacks (`fallbacks: "default"`).

## Safeguards

- Images are decoded and re-encoded before analysis, which strips EXIF and other embedded
  metadata; nothing is written to disk.
- A first-visit notice must be accepted; every report carries the research-use disclaimer.
- Cost limits apply only to the host's own API keys (visitor keys and MedGemma are
  unlimited): `MAX_ANALYSES_PER_SESSION` (default 20) and `MAX_ANALYSES_PER_DAY` (default 200).

## Teaching slides

From Wikimedia Commons: Mikael Häggström, M.D. (CC0); Ed Uthman (CC BY 2.0); CoRus13
(CC BY-SA 4.0). Sources and licences per image are in `samples/samples.json`.

## Develop

```bash
pip install -r requirements.txt
ANTHROPIC_API_KEY=... GEMINI_API_KEY=... python -m shiny run app.py
npm install && npm run build      # after changing anything in src/
python -m pytest                  # uses fake SDK clients; no API calls
```
