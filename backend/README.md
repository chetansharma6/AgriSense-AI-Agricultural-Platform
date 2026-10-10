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
the API; the default is `http://localhost:3000`.

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
| soil_ph | 0.15 | pH inside the crop's range (-40 per pH unit outside) |
| drainage | 0.15 | drainage class inside the crop's range (-25 per class); muck is 90 for muck crops, 30 otherwise |
| season_temp | 0.20 | mean temperature in the growing window inside the range (-10 per C) |
| frost_risk | 0.15 | freeze days in the window at or below the crop's limit (-10 per extra day) |
| rainfall | 0.10 | window rainfall inside the range (-1 per % outside) |
| local_history | 0.25 | 5,000+ acres in the county at the latest Census (log scale from 60 at 1 acre; 75 if withheld; 30 if not grown) |

Climate factors are scored for each Florida growing window of the crop and
the best window is reported as `season_label`.

A source that fails never fails the request: its values are null and a
message is added to `warnings`.
