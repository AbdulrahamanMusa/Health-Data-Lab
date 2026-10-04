# Histopathology Screener

AI-assisted screening of histology images for **research and medical education**.
Two vision models, **Claude** (Anthropic) and **Gemini** (Google), read the same slide
with the same instructions and fill the same structured report, so their answers can
be compared side by side.

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

Keys: `ANTHROPIC_API_KEY` and/or `GEMINI_API_KEY`. A model whose key is missing is shown
as "not configured"; with no keys at all the app runs in demo mode (slides and Learn mode
work, analysis is disabled). Claude requests use structured outputs and server-side
refusal fallbacks (`fallbacks: "default"`).

## Safeguards

- Images are decoded and re-encoded before analysis, which strips EXIF and other embedded
  metadata; nothing is written to disk.
- A first-visit notice must be accepted; every report carries the research-use disclaimer.
- Cost limits for public deployments: `MAX_ANALYSES_PER_SESSION` (default 20) and
  `MAX_ANALYSES_PER_DAY` (default 200).

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
