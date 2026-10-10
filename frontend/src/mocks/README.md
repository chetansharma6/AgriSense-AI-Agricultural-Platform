# Demo fixtures

These files are copies of the real backend responses saved in
`backend/data/demo/<farm>.json` (Marianna, Hastings, Plant City, Belle Glade).
Each has `recommend` (the `/api/recommend` response) and `crops` (the
`/api/crops/{id}` response for each of the 13 crops). Refresh them by copying
the backend files again; do not edit them by hand.

Missing measurements stay `null` (for example Belle Glade soil pH). Render them
as "No data". Helpers pick the nearest demo farm by great-circle distance and
return independent copies. Unknown crop IDs throw `Unknown crop`.
