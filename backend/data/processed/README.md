# USDA NASS data behind AgriSense

These CSVs hold the USDA NASS Quick Stats data that AgriSense uses for local
history, yields and prices, with the same series and filters as the app
(`backend/app/market.py`). Regenerate them with `python -m scripts.export_nass`
from `backend/`; it needs `NASS_API_KEY`.

| File | What it holds | App use |
|---|---|---|
| `nass_acres_county.csv` | Census of Agriculture acres harvested (or bearing, for strawberries) per Florida county, 2012 onwards | Local history factor: is the crop grown in the county, and how much |
| `nass_yield_county.csv` | Survey yields per county, 2014 onwards (mostly field crops; NASS does not survey most vegetables by county) | Average yield, when the county has data |
| `nass_yield_state.csv` | Florida yields, 2014 onwards | Average yield otherwise (mean of the latest 5 years) |
| `nass_price_state.csv` | Florida prices received per marketing year, 2014 onwards | Price range (low and high of the latest 5 years) |

Columns:

- `crop_id`: AgriSense crop id (see `backend/data/crops.json`)
- `level`: `county` or `state`
- `county_fips`: 5-digit FIPS code, e.g. `12109` for St. Johns (empty for state rows)
- `county_name`
- `year`
- `statistic`: NASS statistic category, e.g. `AREA HARVESTED`, `YIELD`, `PRICE RECEIVED`
- `short_desc`: the exact NASS series name
- `unit`: e.g. `ACRES`, `CWT / ACRE`, `$ / LB`
- `value`: the number, empty when NASS withholds or suppresses it
- `value_raw`: the value as NASS reports it, including codes: `(D)` withheld to avoid disclosing a single farm, `(Z)` less than half a unit, `(NA)` not available

Source: USDA National Agricultural Statistics Service, Quick Stats
(https://quickstats.nass.usda.gov).
