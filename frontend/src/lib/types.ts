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

export interface CropScale {
  fit: "good" | "small" | "too_small" | null;
  min_practical_acres: number;
  note: string | null;
}

export interface GrossValue {
  low: number;
  high: number;
  label: "Rough gross value before costs";
}

export interface NutrientPlan {
  n_lb_per_acre: number | null;
  soil_test_first: true;
  lime_note: string | null;
  practices: string[];
  sources: { title: string; url: string }[];
}

export interface ActionPlan {
  check_before_planting: string;
  first_test: string;
  planting_window: string;
  major_risk: string;
  uf_ifas_follow_up: ExtensionLink;
}

export interface WaterPlan {
  ideal_monthly_low_mm: number;
  ideal_monthly_high_mm: number;
  season_status: string;
  irrigation_sensitivity: string;
  note: string;
  source: ExtensionLink;
}

export interface ManagementGuidance {
  soil_health_practices: string[];
  rotation_guidance: string;
  source: ExtensionLink;
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
  scale: CropScale;
  est_gross_value: GrossValue | null;
  limited_by: string[] | null;
  flags: string[] | null;
  action_plan?: ActionPlan | null;
  risk_notes?: string[] | null;
}

export interface ScoringRules {
  weights: Record<FactorKey, number>;
  critical_factors: string[];
  critical_threshold: number;
  critical_cap: number;
}

export interface SourceStatus {
  name: string;
  status: string;
  detail: string | null;
  url?: string;
  data_period?: string;
  data_status?: string;
  geographic_level?: string;
  limitations?: string[];
}

export interface Provenance {
  mode: string;
  sources: SourceStatus[];
  fawn_station: FawnStation | null;
}

export interface FawnStation {
  name: string;
  distance_km: number;
}

export interface Confidence {
  level: string;
  available_factors: number;
  total_factors: number;
  available_factor_names?: string[];
  missing_factor_names?: string[];
  data_status?: string;
  county_history_status?: string;
  partial?: boolean;
  notes: string[];
}

export interface RecommendResponse {
  location: Location | null;
  conditions: Conditions | null;
  crops: CropResult[] | null;
  warnings: string[] | null;
  scoring: ScoringRules | null;
  provenance?: Provenance | null;
  confidence?: Confidence | null;
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
  nutrient_plan: NutrientPlan;
  water_plan?: WaterPlan | null;
  management_guidance?: ManagementGuidance | null;
  requirements: Record<string, JsonValue> | null;
  general_guidance: string | null;
  extension_links: ExtensionLink[] | null;
  conditions: Conditions | null;
  location: Location | null;
  scoring: ScoringRules | null;
  provenance?: Provenance | null;
  confidence?: Confidence | null;
}
