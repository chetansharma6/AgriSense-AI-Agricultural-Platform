/** API response fields remain present when source data is unavailable. */
export interface Location {
  lat: number | null;
  lon: number | null;
  county: string | null;
  county_fips: string | null;
  state: string | null;
}

export interface Conditions {
  soil_ph: number | null;
  organic_matter_pct: number | null;
  sand_pct: number | null;
  clay_pct: number | null;
  texture: string | null;
  drainage: string | null;
  annual_precip_mm: number | null;
  frost_free_days: number | null;
  last_spring_frost: string | null;
  first_fall_frost: string | null;
  avg_summer_high_c: number | null;
  avg_winter_low_c: number | null;
}

export type FactorKey =
  | "soil_ph"
  | "drainage"
  | "season_temp"
  | "frost_risk"
  | "rainfall"
  | "local_history";

export interface FactorDetail {
  value: number | string | null;
  ideal: string | null;
  unit?: string | null;
}

export interface Yield {
  value: number | null;
  unit: string | null;
  level: string | null;
}

export interface PriceRange {
  low: number | null;
  high: number | null;
  unit: string | null;
}

export interface CropResult {
  id: string | null;
  name: string | null;
  score: number | null;
  season_label: string | null;
  factors: Record<FactorKey, number | null> | null;
  factor_details: Record<FactorKey, FactorDetail | null> | null;
  avg_yield: Yield | null;
  price: PriceRange | null;
  limited_by: string[] | null;
  flags: string[] | null;
}

export interface ScoringRules {
  weights: Record<FactorKey, number>;
  critical_factors: string[];
  critical_threshold: number;
  critical_cap: number;
}

export interface RecommendResponse {
  location: Location | null;
  conditions: Conditions | null;
  crops: CropResult[] | null;
  warnings: string[] | null;
  scoring: ScoringRules | null;
}

export interface ExtensionLink {
  title: string | null;
  url: string | null;
}

// The contract delegates the requirements schema to crops.json.
type JsonValue = string | number | boolean | null | JsonValue[] | {
  [key: string]: JsonValue;
};

export interface CropDetail extends CropResult {
  requirements: Record<string, JsonValue> | null;
  general_guidance: string | null;
  extension_links: ExtensionLink[] | null;
  conditions: Conditions | null;
  location: Location | null;
  scoring: ScoringRules | null;
}
