# Florida demo fixtures

These files contain synthetic UI test data, not USDA NASS observations,
measured soil or climate data, or agricultural recommendations. Yield and price
units follow NASS-style conventions. Scores and factor breakdowns are
illustrative; production scores must come from the deterministic backend.

Each location has all 13 crops sorted by descending score. Marianna has a
missing sugarcane yield and one warning. Belle Glade has organic muck,
365 frost-free days, and null frost dates.

Helpers select the nearest demo coordinates using great-circle distance and
return independent copies. Unknown crop IDs throw `Unknown crop`.
Requirements and guidance are synthetic. The Extension link opens the real
UF/IFAS EDIS publication portal.
