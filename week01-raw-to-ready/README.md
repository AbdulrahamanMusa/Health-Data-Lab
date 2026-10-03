# Raw → Ready: an audit-ready cleaning workbench

**Health Data Lab, week 1: never overwrite raw data — the cleaning log.**

Survey data arrives with duplicates, rushed interviews, impossible values and,
sometimes, fabricated records. Raw → Ready shows decision-makers what that does
to their indicators, and gives data managers a disciplined way to fix it:

- **Readiness**: a clear verdict (not ready / ready with caveats / ready), the
  record funnel, and indicators computed on the raw export versus the cleaned
  data. In the sample, raw data overstates Penta3 coverage by 4.2 points and
  hides part of the dropout and malnutrition problem.
- **Review flags**: 14 standard checks with a recommended action for each
  (correct, set missing, exclude, or send for field verification). Decide one
  at a time or apply the protocol in bulk.
- **Cleaning log**: an append-only audit trail in the standard template
  columns (record, variable, old → new, reason, action, verified, who, when).
  Undo adds a reversal entry; nothing is erased.
- **Enumerators**: a supervision scorecard (short interviews, repeated GPS
  points, night-time entry, MUAC rounding) with suggested follow-up.
- **Data & privacy**: upload a KoboToolbox/ODK export (.xlsx or .csv); the raw
  file is fingerprinted with SHA-256 and never modified; names and phone
  numbers are kept out of every export; household GPS is excluded from
  exports by default.

Exports: audit pack (.xlsx: clean data, cleaning log, flags, enumerators,
indicator impact), shareable clean dataset (.csv), one-page summary (.html).

## The rule behind it

```
clean = apply(prepare(raw), cleaning_log)
```

The raw export is never changed. Every number is recomputed from the raw file
plus the log, so any result can be reproduced and audited.

## Layout

```
app.py            Shiny server: reactive outputs and event handlers
rtr/sample.py     synthetic child-health Kobo export (fictional Demo State) with realistic defects
rtr/pipeline.py   preparation, checks, decisions, indicators, scorecard, readiness
rtr/report.py     audit pack, shareable CSV, one-page HTML summary
src/              React client (TypeScript) → built to www/
tests/            pytest: pipeline rules and the server's event flow
```

## Develop

```bash
pip install -r requirements.txt
python -m shiny run app.py           # http://127.0.0.1:8000
npm install && npm run build         # after changing anything in src/
python -m pytest
```

Uploaded files are held in the session's memory only and are never written to
disk. All bundled data is synthetic.
