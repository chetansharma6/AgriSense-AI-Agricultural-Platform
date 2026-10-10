import type { FactorKey } from "./types";

// Must match backend/app/scoring.py WEIGHTS (percentages shown in the UI).
// If scoring moves to backend/app/scoring/rank.py, keep these in sync there.
export const FACTOR_WEIGHTS: Record<FactorKey, number> = {
  soil_ph: 15,
  drainage: 15,
  season_temp: 20,
  frost_risk: 15,
  rainfall: 10,
  local_history: 25,
};

export const SCORE_EXPLANATION =
  "Score = weighted average of the available factors. Missing factors are excluded and the remaining weights are normalized; there is no critical-factor score cap.";
