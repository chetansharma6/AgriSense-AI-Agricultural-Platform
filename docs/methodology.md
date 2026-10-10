# AgriSense methodology

AgriSense compares 13 crops for a selected Florida location. Scores are deterministic suitability indices from 0 to 100, not probabilities of success or profit forecasts.

## Data pipeline

- USDA NRCS SSURGO provides mapped soil pH, drainage, organic matter, and texture. Organic matter above 20% is classified as muck.
- NASA POWER provides daily climate history, summarized for crop growing windows.
- County lookup associates the location with USDA NASS county acreage and yield records; prices are state-level. Check the response's reported geographic level for yield fallbacks.
- Crop requirements and Florida growing windows are maintained in `backend/data/crops.json`, with UF/IFAS Extension references.

## Scoring

| Factor | Weight | Comparison |
|---|---|---|
| Soil pH | 20% | Ideal pH range, declining toward crop limits |
| Drainage | 15% | Suitable drainage classes; separate muck suitability rules |
| Season temperature | 20% | Mean temperature against ideal and limiting ranges |
| Frost risk | 15% | Weighted freeze days against crop tolerance |
| Rainfall | 10% | Seasonal rainfall against the crop requirement range |
| Local track record | 20% | Reported county crop acreage |

For each crop, the engine selects the growing window with the highest weighted climate sub-score (temperature, frost, rainfall). It then calculates the weighted mean of all available factors. Missing factors remain null and their weights are excluded and renormalized; missing data does not itself lower the score.

A soil pH, drainage, temperature, or frost factor below 25 caps the overall score at 45. Muck-unsuitable crops receive a drainage score of 15; muck-suitable crops receive 90. Light freezes above -2 C count as half a day; freezes at or below -2 C count fully. Excess weighted freeze days cost 10 points per day.

Local history starts at 60 for reported acreage and rises logarithmically to 100 at 5,000 acres. Withheld acreage for a crop reported grown receives 75; a crop not reported grown receives 30. No available history leaves the factor null.

See [the scoring implementation](../backend/app/scoring.py) and [API contract](api-contract.md) for the precise response and rules.

## Explanations and data availability

The server-side AI receives the calculated crop data and is instructed to explain only supplied facts. It cannot change the calculated scores. A local report is returned when AI is unavailable or its response fails validation; AI wording still requires review.

The frontend can use mock data when `NEXT_PUBLIC_USE_MOCKS=true`. With backend `DEMO_MODE=true`, failed or slow data requests can use a saved nearby demo response, explicitly labeled by a warning. Source caches also reduce repeated requests.

## Limits

Public mapped soil and gridded climate data are not on-field measurements. County and state records are not individual farm yields or sale prices. The score has not been validated as a predictor of farm outcomes and does not model profit, hurricanes, pests, labor, or irrigation infrastructure comprehensively. Review missing-data warnings, confirm conditions with soil tests, and consult county UF/IFAS Extension before planting.
