# Florida demo fixtures

These files contain synthetic UI test data, not USDA NASS observations,
measured soil or climate data, or agricultural recommendations. Yield and price
units follow NASS-style conventions. Scores and factor breakdowns are
illustrative; production scores must come from the deterministic backend.

Each location has all 13 crops sorted by descending score. The fixtures cover
missing-data cases reported in real backend responses:

- Hastings and Plant City have null spring and fall frost dates. This means no
  representative date is available, not that freeze risk is zero.
- Belle Glade has null soil pH, sand and clay percentages, null soil pH factor
  scores and detail values, and a warning. It also retains a missing cotton
  yield with a warning to exercise yield empty states.
- Marianna has an empty warnings array.
- Belle Glade retains organic muck, 365 frost-free days, and null frost dates.

Render missing measurements as "No data" and omit score bars/tone for null
factor scores. Show warnings only when the array contains messages.

Helpers select the nearest demo coordinates using great-circle distance and
return independent copies. Unknown crop IDs throw `Unknown crop`.
Requirements and guidance are synthetic. The Extension link opens the real
UF/IFAS EDIS publication portal.
