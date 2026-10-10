# Demo fixtures

These files are copies of the real backend responses saved in
`backend/data/demo/<farm>.json` (Marianna, Hastings, Plant City, Belle Glade).
Each has `recommend` (the `/api/recommend` response) and `crops` (the
`/api/crops/{id}` response for each of the 13 crops). Refresh them with the script below; do not edit them by hand.

Missing measurements stay `null` (for example Belle Glade soil pH). Render them
as "No data". Helpers pick the nearest demo farm by great-circle distance and
return independent copies. Unknown crop IDs throw `Unknown crop`.

Run `python frontend/scripts/refresh-acreage-mocks.py` from the repository root
to refresh the contract fields and saved acreage variants using backend crop
requirements and Python acreage helpers. Rates are copied from backend data,
never calculated in the browser. Acreage mocks support the quick-pick sample
sizes (0.5, 3, 10, 50 and 100 acres); other sizes require the live API.
