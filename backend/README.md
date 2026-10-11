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
`https://agrisense-ai-cyan.vercel.app`. Do not use `*`, a `*.vercel.app` wildcard, or
preview URLs unless each exact preview origin is intentionally added.

## Deployment settings

Set `DEMO_MODE=true` for the labelled demo fallback and `CORS_ORIGINS` to the
exact public Vercel URL. Market history defaults to the committed USDA NASS
CSV exports (`NASS_USE_SNAPSHOT=true`), eliminating five cold network requests.
Their actual year range and historical/cached status appear in provenance.
To query live NASS instead, set `NASS_USE_SNAPSHOT=false` and configure
`NASS_API_KEY` as a secret. Missing/invalid exports also try the live path.
Vercel requires the server-side `ANTHROPIC_API_KEY` only for the optional report
route; `ANTHROPIC_MODEL` is optional. Never prefix these secrets with
`NEXT_PUBLIC_`, commit `.env` files, or expose them in browser code. Missing
keys degrade safely: live NASS data becomes unavailable with a warning and the
report route uses its local fallback. Production debug mode is not enabled.

## How a recommendation is built

1. County (FCC), soil (USDA SSURGO), 2016-2025 daily weather (NASA POWER), and
   a nearby FAWN station's minimum temperatures are fetched in parallel.
   County market history starts as soon as FCC completes, without waiting
   for soil or weather. Historical market exports are loaded locally.
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

A source that fails produces null values and a warning instead of a server
error. Live provider fetching has a six-second budget by default, configurable
with `RECOMMENDATION_DEADLINE_S`; scoring/serialization adds some CPU time.
At most eight distinct live builds run concurrently. Repeated requests for
the same point share provider work, but each gets isolated acreage/coordinates.
Memory-cache and saved-demo hits remain available while live builds are full;
new uncached locations receive a controlled 503 when overloaded. Health checks
do not wait for a worker thread. Missing daily rain/minimum observations are
not treated as zero rainfall or frost-free days.

Crop-detail responses also expose beginner-facing water, soil-health, and
rotation guidance. Water status is derived from the same committed crop
rainfall thresholds and selected-window factor flags used by scoring; it does
not add forecasts or alter suitability formulas. Soil-health steps and rotation
notes come from committed crop guidance and link back to UF/IFAS.

## Performance verification

Run `python -m scripts.benchmark_backend` for a repeatable, network-free
benchmark with controlled provider delays. `--mode live --samples 1` checks
Tampa against the real APIs with an empty temporary disk cache and an empty
response cache, then checks a memory hit. Timings include scoring and should
not be confused with hosting startup time or a production latency guarantee.
The benchmark validates the response contract and stable scores on repeat.

The judging narrative is: AgriSense does not ask an AI model to guess what a
farmer should plant. It gathers public agricultural data, applies visible
agronomic rules, shows missing data and limitations, and uses AI only to explain
the calculated result in beginner-friendly language.

## Offline test/demo mode

Set `DEMO_MODE=true` when exercising the four official coordinates from
`app.config.DEMO_FARMS` (Marianna, Hastings, Plant City, and Belle Glade).
An exact official coordinate is served from the committed JSON fixture in
`data/demo/` before any provider client is called. This path is deterministic,
contains 13 ranked crops, and is intended for offline tests and demonstrations.
Coordinates other than those four exact points retain the existing live path;
`DEMO_MODE` only applies the bounded fallback/deadline behavior to them.

## Judge demo evaluation

Run the committed demos without network access:

```bash
cd backend
.venv/bin/python -m scripts.evaluate_demos
```

The evaluator runs all four official locations twice and reports response
latency, crop count, score range and ordering, missing factors, source status,
deterministic repeatability, and NaN/infinity checks. It forbids provider calls
and exits nonzero if any demo is slow (one second or more), malformed,
nondeterministic, out of order, missing crops or provenance, or contains a
non-finite number. Judges can use its exit status directly in CI or a shell.
