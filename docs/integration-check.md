# Backend/frontend integration check

Checked on October 10, 2026, starting from `fcde6a3` and incorporating PR #48 (`abc9888`), which disables mocks in the example frontend environment.

## Setup and scope

The local backend ran at `http://localhost:8000` with `DEMO_MODE=false`. The frontend ran at `http://localhost:3000` with `NEXT_PUBLIC_API_URL=http://localhost:8000` and `NEXT_PUBLIC_USE_MOCKS=false`. Existing private environment files were not changed or committed.

All four example locations used the normal source pipeline with existing source caches; this was not a cold, uncached availability test of the external services. Backend logs confirmed FAWN station minimum temperatures were used for freeze calculations. The checks cover local integration, not the deployed Vercel/Render environments.

## Contract results

`python -m scripts.check_contract` passed all 356 checks against the local HTTP API. The checks include recommendation and top-crop detail responses, required fields and types, units, 13 unique crops, score ordering, and rounding. Response shapes were also compared with `frontend/src/lib/types.ts` and `docs/api-contract.md`; no contract mismatch was found.

| Location | Missing field | Wrong type | Wrong unit | Unexpected null | Result |
|---|---|---|---|---|---|
| Marianna | None | None | None | None | PASS |
| Hastings | None | None | None | None | PASS |
| Plant City | None | None | None | None | PASS |
| Belle Glade | None | None | None | None | PASS |

Expected nulls were retained rather than replaced with fabricated numbers:

- Hastings: first fall frost date.
- Plant City: last spring and first fall frost dates.
- Belle Glade: soil pH, sand/clay percentages, and both frost dates. The response warns that the soil survey reports no pH and the pH factor is skipped.

Null frost dates can reflect an absence of observed freezes in the relevant period. Null soil fields reflect unavailable survey properties and require care when interpreting suitability.

Observed top crops were watermelon (94) in Marianna, snap bean (97) in Hastings, strawberry (93) in Plant City, and snap bean (98) in Belle Glade. These are captured results, not guaranteed rankings for future data updates.

## Browser checks

Headless Chromium checked the actual frontend against the local API:

- All four locations render 13 crop cards and readable, rounded numbers.
- The home map loads; selecting Plant City and clicking **Analyze my land** opens the results.
- The strawberry crop page renders its factor chart and report section.
- The About page renders.
- Results fit a 390px phone-width viewport without horizontal page overflow.
- A deliberately delayed recommendation shows the loading state and slow-server message.
- A deliberately failed recommendation shows the friendly connection error and **Try again** button.
- No browser runtime errors or CORS-policy console errors were observed in the completed check.

The report rendering check does not establish AI provider availability or validate report prose. A deliberately aborted request produces an expected network failure in the browser; it is not a CORS failure.

## Required checks

- Backend: `python -m pytest -q` — 211 passed, one dependency deprecation warning.
- Frontend: `npm run build` — passed compilation, TypeScript checks, and static page generation.
- Contract: 356 passed, zero failed.

The first backend suite run overlapped a production build and two demo tests exceeded their 0.3-second test deadline. The suite passed when rerun without the concurrent build; these short timing assertions remain sensitive to machine load. Production's deadline was not changed.

## Changes

No API or CORS implementation change was needed. README setup now explains the integrated default and optional offline mock mode. The recording script now includes the required **Analyze my land** click after selecting Plant City or Belle Glade.
