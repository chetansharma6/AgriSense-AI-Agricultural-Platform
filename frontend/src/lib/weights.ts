import { factorLabel } from "./format";
import type { FactorKey, ScoringRules } from "./types";

// Must match backend/app/scoring.py WEIGHTS (percentages shown in the UI).
// If scoring moves to backend/app/scoring/rank.py, keep these in sync there.
export const FACTOR_WEIGHTS: Record<FactorKey, number> = {
  soil_ph: 20,
  drainage: 15,
  season_temp: 20,
  frost_risk: 15,
  rainfall: 10,
  local_history: 20,
};

export const SCORE_EXPLANATION =
  "Score = weighted average of the available factors. Missing factors are excluded and the remaining weights are normalized. If soil pH, drainage, season temperature or frost risk scores below 25, the total is capped at 45.";

/** Prefer the weights the backend reports; fall back to the defaults above. */
export function weightsFor(scoring: ScoringRules | null | undefined): Record<FactorKey, number> {
  if (!scoring?.weights) return FACTOR_WEIGHTS;
  const entries = Object.entries(scoring.weights).map(([key, weight]) => [key, Math.round(weight * 100)]);
  return { ...FACTOR_WEIGHTS, ...Object.fromEntries(entries) };
}

export function explanationFor(scoring: ScoringRules | null | undefined): string {
  if (!scoring) return SCORE_EXPLANATION;
  const names = scoring.critical_factors.map((key) => factorLabel(key as FactorKey)).join(", ");
  return `Score = weighted average of the available factors. Missing factors are excluded and the remaining weights are normalized. If any of ${names} scores below ${scoring.critical_threshold}, the total is capped at ${scoring.critical_cap}.`;
}
