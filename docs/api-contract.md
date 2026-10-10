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
       "frost_risk": {"value": 4, "ideal": "<= 5", "unit": "freeze days in season"},
       "rainfall": {"value": 310, "ideal": "350-600", "unit": "mm in season"},
       "local_history": {"value": "Grown in county", "ideal": "Grown locally"}},
     "avg_yield": {"value": 290, "unit": "CWT / ACRE", "level": "county"},
     "price": {"low": 14.5, "high": 22.0, "unit": "$ / CWT"},
     "flags": ["May need supplemental irrigation"]}
  ],
  "warnings": []
}
Rules: crops sorted by score descending; every factor 0-100; any value may be
null if a source failed (and a message is added to warnings).

GET /api/crops/{crop_id}?lat=&lon= -> the same crop object plus:
  "requirements": {raw fields from crops.json},
  "general_guidance": "string",
  "extension_links": [{"title": "string", "url": "string"}],
  "conditions": {same as above}, "location": {same as above}
404 {"detail": "Unknown crop"} for an unknown id.
400 {"detail": "Location must be in Florida"} outside the bounding box.
