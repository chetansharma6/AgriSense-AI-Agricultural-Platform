# AgriSense backend

FastAPI service that scores 13 crops for a Florida location. API shape:
[docs/api-contract.md](../docs/api-contract.md).

## Run

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
echo "NASS_API_KEY=your_key" > .env   # free key from quickstats.nass.usda.gov
.venv/bin/uvicorn app.main:app --reload   # http://localhost:8000/api/health
.venv/bin/pytest
```

`CORS_ORIGINS` (comma-separated, in `.env`) sets which browser origins may call
the API; the default is `http://localhost:3000`. Set this explicitly in Render
to the exact Vercel production URL, for example
`https://agrisense.vercel.app`. Do not use `*`, a `*.vercel.app` wildcard, or
preview URLs unless each exact preview origin is intentionally added.

## Deployment settings

Render requires `NASS_API_KEY` as a secret and should use `DEMO_MODE=true` for
the bounded demo fallback. Set `CORS_ORIGINS` to the exact public Vercel URL.
Vercel requires the server-side `ANTHROPIC_API_KEY` only for the optional report
route; `ANTHROPIC_MODEL` is optional. Never prefix these secrets with
`NEXT_PUBLIC_`, commit `.env` files, or expose them in browser code. Missing
keys degrade safely: NASS data becomes unavailable with a warning and the
report route uses its local fallback. Production debug mode is not enabled.

## How a recommendation is built

1. County (FCC), soil (USDA SSURGO) and 2015-2024 daily weather (NASA POWER)
   are fetched in parallel; NASS county and state data follow.
2. Every source is cached as JSON in `data/cache/`, so each location hits
   each API once. Cached data for the four demo farms is committed, so the
   demo works offline.
3. Each crop in `data/crops.json` gets six factor scores (0-100), and the crop
   score is their weighted mean (factors with no data are skipped):

| Factor | Weight | 100 when |
|---|---|---|
| soil_ph | 0.15 | pH inside the crop's ideal range; falls linearly to 0 at its hard limit (`ph_min`/`ph_max`) |
| drainage | 0.15 | drainage class inside the crop's range (-25 per class); muck is 90 for muck crops, 30 otherwise |
| season_temp | 0.20 | mean temperature in the growing window inside the ideal range; falls linearly to 0 at `temp_min_c`/`temp_max_c` |
| frost_risk | 0.15 | freeze days in the window at or below the crop's limit (-10 per extra day) |
| rainfall | 0.10 | window rainfall inside the range (-1 per % outside) |
| local_history | 0.25 | 5,000+ acres in the county at the latest Census (log scale from 60 at 1 acre; 75 if withheld; 30 if not grown) |

Climate factors are scored for each Florida growing window of the crop and
the best window is reported as `season_label`.

A source that fails never fails the request: its values are null and a
message is added to `warnings`.

## Offline test/demo mode

Set `DEMO_MODE=true` when exercising the four official coordinates from
`app.config.DEMO_FARMS` (Marianna, Hastings, Plant City, and Belle Glade).
An exact official coordinate is served from the committed JSON fixture in
`data/demo/` before any provider client is called. This path is deterministic,
contains 13 ranked crops, and is intended for offline tests and demonstrations.
Coordinates other than those four exact points retain the existing live path;
`DEMO_MODE` only applies the bounded fallback/deadline behavior to them.
