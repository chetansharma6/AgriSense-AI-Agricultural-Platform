GET /api/health -> {"status": "ok"}

GET /api/recommend?lat=<float>&lon=<float> ->
{
  "location": {"lat": 29.71, "lon": -81.50, "county": "St. Johns",
               "county_fips": "12109", "state": "FL"},
  "conditions": {
    "soil_ph": 5.6, "organic_matter_pct": 1.8, "sand_pct": 88,
    "clay_pct": 4, "texture": "sand", "drainage": "Poorly drained",
    "annual_precip_mm": 1290, "frost_free_days": 300,
    "last_spring_frost": "02-10", "first_fall_frost": "12-12",
    "avg_summer_high_c": 32.8, "avg_winter_low_c": 7.9},
  "crops": [
    {"id": "potato", "name": "Potato", "score": 84,
     "season_label": "Spring: plant Jan-Feb, harvest Apr-May",
     "factors": {"soil_ph": 95, "drainage": 70, "season_temp": 90,
                 "frost_risk": 80, "rainfall": 75, "local_history": 100},
     "factor_details": {
       "soil_ph": {"value": 5.6, "ideal": "5.0-6.0", "unit": "pH"},
       "drainage": {"value": "Poorly drained",
                    "ideal": "Well drained to somewhat poorly drained"},
       "season_temp": {"value": 19.5, "ideal": "15-24", "unit": "C avg"},
       "frost_risk": {"value": 1.5, "ideal": "<= 2", "unit": "freeze days in season (light freezes count half)"},
       "rainfall": {"value": 310, "ideal": "350-600", "unit": "mm in season"},
       "local_history": {"value": "Grown in county", "ideal": "Grown locally"}},
     "avg_yield": {"value": 290, "unit": "CWT / ACRE", "level": "county"},
     "price": {"low": 14.5, "high": 22.0, "unit": "$ / CWT"},
     "limited_by": [],
     "flags": ["Likely needs irrigation (310 mm rain expected, 350 mm needed)"]}
  ],
  "warnings": [],
  "scoring": {
    "weights": {"soil_ph": 0.20, "drainage": 0.15, "season_temp": 0.20,
                "frost_risk": 0.15, "rainfall": 0.10, "local_history": 0.20},
    "critical_factors": ["soil_ph", "drainage", "season_temp", "frost_risk"],
    "critical_threshold": 25,
    "critical_cap": 45},
  "provenance": {"mode": "live", "sources": [{"name": "USDA SSURGO", "status": "live", "detail": null}]},
  "confidence": {"level": "high", "available_factors": 6, "total_factors": 6, "notes": []}
}
Rules: crops sorted by score descending, then name ascending; every factor
0-100; any value may be null if a source failed (and a message is added to
warnings).
Score: weighted average of the non-null factors (weights renormalized over
the factors present). If any critical factor scores below critical_threshold,
the score is capped at critical_cap and that factor's key is listed in
limited_by (in critical_factors order), with a "Limited by <factor>" flag.
frost_risk value: weighted freeze days in the growing window. Nights at or
below -2 C count 1, nights between -2 and 0 C count 0.5.
flags: at most 4, deduplicated, most critical first ("Limited by" flags, then
flags of the lowest-scoring factors).
`provenance` identifies live versus saved demo data and lists the source status.
`confidence` reports how many of the six scoring factors had data; it does not
alter the suitability score.

GET /api/crops/{crop_id}?lat=&lon= -> the same crop object plus:
  "requirements": {raw fields from crops.json},
  "general_guidance": "string",
  "extension_links": [{"title": "string", "url": "string"}],
  "conditions": {same as above}, "location": {same as above},
  "scoring": {same as above}
404 {"detail": "Unknown crop"} for an unknown id.
400 {"detail": "Location must be in Florida"} outside the bounding box.
503 {"detail": "Data sources are slow right now. Try again in a moment, or pick a
demo farm."} only in DEMO_MODE, when live data misses the 6 s deadline and no
demo farm is within 25 km. Near a demo farm the saved response is returned
instead, with "Showing cached data for <farm> (<reason>)" as the first warning.
