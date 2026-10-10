/**
 * Deterministic fertilizer-category recommendations for a crop detail page.
 *
 * Everything here is rule-based and explainable. It recommends fertilizer
 * CATEGORIES, never brands, prices, deficiencies or application rates.
 * Estimated regional soil properties are never treated as soil-test results.
 */
import type { Conditions, CropDetail } from "./types";

export type FilterId = "eco" | "cost" | "organic" | "low_maintenance" | "small_space";
export type AcreBand = "unknown" | "backyard" | "small" | "medium" | "large";
export type Level = 0 | 1 | 2 | 3;
export type Rating = "low" | "adequate" | "high";

export interface SoilTest { n?: Rating; p?: Rating; k?: Rating }
export interface Source { title: string; url: string; supports: string }

export const FILTERS: { id: FilterId; label: string; hint: string; basis: string }[] = [
  { id: "eco", label: "Eco-Friendly", hint: "Lower runoff and leaching risk",
    basis: "Shows options rated for lower leaching and runoff risk, based on how fast nutrients release and how easily they wash out. Being organic does not count by itself. Sandy soil in the regional data lowers the rating of soluble products." },
  { id: "cost", label: "Cost-Effective", hint: "Affordable nutrient delivery",
    basis: "Shows options in the lowest relative cost category ($), an AgriSense estimate of cost per unit of nutrient delivered. These are not retail prices." },
  { id: "organic", label: "Organic", hint: "Organic-based materials",
    basis: "Shows organic-based materials only. Organic products can still cause runoff if over-applied." },
  { id: "low_maintenance", label: "Low Maintenance", hint: "Fewer applications, easier handling",
    basis: "Shows options that typically need fewer applications and simpler handling, such as slow- or controlled-release products." },
  { id: "small_space", label: "Small-Space Friendly", hint: "Practical for backyards and small lots",
    basis: "Shows options practical for under 1 acre: small packages and hand spreading. Hidden for 100+ acre plots." },
];

const SRC = {
  cv002: { title: "UF/IFAS: Standardized Nutrient Recommendations for Vegetable Crop Production in Florida (CV002)", url: "https://edis.ifas.ufl.edu/publication/CV002" },
  cv296: { title: "UF/IFAS: Fertilizer Management for Vegetable Production in Florida (CV296)", url: "https://edis.ifas.ufl.edu/cv296" },
  cv101: { title: "UF/IFAS: Soil and Fertilizer Management for Vegetable Production in Florida (CV101)", url: "https://edis.ifas.ufl.edu/cv101" },
  ss163: { title: "UF/IFAS: Standardized Fertilization Recommendations for Agronomic Crops (SS163)", url: "https://edis.ifas.ufl.edu/publication/SS163" },
  ag496: { title: "UF/IFAS: Controlled-Release Potassium Fertilization in Peanut Production in Florida (AG496)", url: "https://ask.ifas.ufl.edu/publication/AG496" },
  ss661: { title: "UF/IFAS: Raising Soil Organic Matter Content to Improve Water Holding Capacity (SS661)", url: "https://ask.ifas.ufl.edu/publication/SS661" },
  epa: { title: "EPA: Sources and Solutions: Agriculture", url: "https://www.epa.gov/nutrientpollution/sources-and-solutions-agriculture" },
};
type SourceKey = keyof typeof SRC;
/** What each verified source supports; shown beside the link so citations match the claim. */
const SUPPORTS: Record<SourceKey, string> = {
  cv002: "Soil-test-based P and K, splitting applications, and leaching of N and K in Florida vegetable production",
  cv296: "P and K supplied based on soil test results; controlled- or slow-release fertilizers to reduce leaching for preplant N and K",
  cv101: "Controlled-release fertilizer can reduce leaching but costs more; organic materials decompose quickly in warm sandy soil and should be analyzed",
  ss163: "Soil testing for phosphorus and potassium in Florida agronomic crops",
  ag496: "Potassium for peanut is based on soil-test potassium; controlled-release potassium",
  ss661: "Organic amendments, including compost, can raise soil organic matter and water holding capacity in Florida sandy soils",
  epa: "Unused fertilizer nitrogen and phosphorus can reach water; apply the right amount at the right time and place",
};
const source = (key: SourceKey): Source => ({ ...SRC[key], supports: SUPPORTS[key] });

interface Catalog {
  id: string;
  name: string;
  /** Typical-grade description only; real grades come from the product label. */
  npk: string;
  organic: boolean;
  cost: 1 | 2 | 3;
  /** Environmental performance (0 poor .. 3 good), before local soil adjustment. */
  eco: Level;
  /** Ease: few applications and simple handling. */
  ease: Level;
  /** Practicality by acreage band. */
  scale: Record<Exclude<AcreBand, "unknown">, Level>;
  /** Needs a soil test to justify the nutrients it supplies. */
  soilTestDependent: boolean;
  /** Supplies meaningful nitrogen. */
  nitrogen: boolean;
  /** Why the relative cost category was assigned. */
  costBasis: string;
  /** Verified sources and the crop types each applies to. */
  sources: { key: SourceKey; scope: "any" | "veg" | "agronomic" | "peanut" }[];
  bestFor: string[];
  environment: string;
  drawbacks: string[];
}

const CATALOG: Catalog[] = [
  { id: "compost", name: "Compost", npk: "Low and variable; not a reliable N-P-K source. Check the supplier's analysis.",
    organic: true, cost: 1, eco: 2, ease: 1, scale: { backyard: 3, small: 3, medium: 1, large: 0 }, soilTestDependent: false, nitrogen: false,
    costBasis: "Usually inexpensive per bag or load, but it supplies little nutrient per dollar.",
    sources: [{ key: "ss661", scope: "any" }, { key: "cv101", scope: "any" }],
    bestFor: ["Small backyard gardens", "Improving soil organic matter"],
    environment: "Organic amendments such as compost can raise soil organic matter and water holding capacity in sandy soil (UF/IFAS). UF/IFAS also notes organic materials break down quickly in warm sandy Florida soil, so nutrients may not last, and heavy repeated use can add phosphorus that is not needed.",
    drawbacks: ["Nutrient composition varies between batches", "Bulky to haul and spread on larger plots", "Rarely supplies enough nitrogen alone for heavy feeders"] },
  { id: "organic_granular", name: "Organic-Based Granular Fertilizer", npk: "Set by the product label; often lower analysis than synthetic fertilizer.",
    organic: true, cost: 3, eco: 2, ease: 2, scale: { backyard: 3, small: 2, medium: 1, large: 0 }, soilTestDependent: false, nitrogen: true,
    costBasis: "Organic nutrient sources generally cost more per unit of nutrient than conventional fertilizer (AgriSense estimate).",
    sources: [{ key: "cv101", scope: "any" }],
    bestFor: ["Small backyard gardens", "Growers who prefer organic inputs"],
    environment: "Nutrients release as the material breaks down, which depends on warmth and moisture. Organic does not automatically mean low runoff: over-application can still leach or run off.",
    drawbacks: ["Higher cost per unit of nutrient", "Release timing is unpredictable", "Nutrient composition varies by product; analyze or read the label"] },
  { id: "slow_release_balanced", name: "Slow-Release Balanced Fertilizer", npk: "Balanced grade set by the label. Choose a grade based on a soil test.",
    organic: false, cost: 2, eco: 3, ease: 3, scale: { backyard: 3, small: 3, medium: 2, large: 1 }, soilTestDependent: true, nitrogen: true,
    costBasis: "UF/IFAS notes controlled-release materials cost more than conventional fertilizer.",
    sources: [{ key: "cv101", scope: "any" }, { key: "cv296", scope: "veg" }, { key: "epa", scope: "any" }],
    bestFor: ["Low-maintenance growing", "Small backyard gardens", "Sandy Florida soils where leaching is a concern"],
    environment: "Coated or slowly soluble nutrients release over time, which can reduce leaching losses compared with fully soluble products.",
    drawbacks: ["Release rate varies with temperature and moisture", "Costs more per unit of nutrient than soluble fertilizer", "May add phosphorus the soil does not need"] },
  { id: "balanced_soluble", name: "Balanced NPK Granular Fertilizer", npk: "Balanced grade set by the label. Choose a grade based on a soil test.",
    organic: false, cost: 1, eco: 1, ease: 1, scale: { backyard: 2, small: 3, medium: 3, large: 2 }, soilTestDependent: true, nitrogen: true,
    costBasis: "Soluble conventional fertilizer is generally the cheapest per unit of nutrient (AgriSense estimate).",
    sources: [{ key: "cv002", scope: "veg" }, { key: "epa", scope: "any" }],
    bestFor: ["Small farms watching cost", "Soils where a test shows more than one nutrient is needed"],
    environment: "Readily soluble nutrients can leach in sandy soil or run off in heavy rain, especially if applied all at once or ahead of storms.",
    drawbacks: ["Usually needs split applications", "Over-application raises runoff and leaching risk", "Phosphorus is often unnecessary where soil already tests adequate"] },
  { id: "controlled_release_n", name: "Controlled-Release Nitrogen Fertilizer", npk: "Nitrogen-focused; grade set by the label.",
    organic: false, cost: 2, eco: 3, ease: 3, scale: { backyard: 2, small: 3, medium: 3, large: 2 }, soilTestDependent: false, nitrogen: true,
    costBasis: "UF/IFAS notes controlled-release materials cost more than conventional fertilizer.",
    sources: [{ key: "cv101", scope: "any" }, { key: "cv296", scope: "veg" }, { key: "epa", scope: "any" }],
    bestFor: ["Nitrogen-hungry crops", "Fewer applications through the season", "Sandy soils prone to nitrogen leaching"],
    environment: "Controlled-release products can reduce leaching losses when the release pattern matches the crop's uptake. Matching nitrogen to crop demand limits runoff.",
    drawbacks: ["Higher cost than soluble nitrogen", "Release can speed up in hot, wet conditions", "Does not supply phosphorus or potassium"] },
  { id: "nitrogen_soluble", name: "Nitrogen-Focused Fertilizer (Split Applications)", npk: "Nitrogen-focused; grade set by the label.",
    organic: false, cost: 1, eco: 1, ease: 1, scale: { backyard: 1, small: 2, medium: 3, large: 3 }, soilTestDependent: false, nitrogen: true,
    costBasis: "Soluble nitrogen is generally the cheapest nitrogen source per unit (AgriSense estimate).",
    sources: [{ key: "cv002", scope: "veg" }, { key: "epa", scope: "any" }],
    bestFor: ["Larger agricultural plots", "Cost-conscious growers who can apply several times"],
    environment: "Soluble nitrogen is easily lost to leaching in sandy soils. Splitting applications and avoiding over-irrigation reduces losses.",
    drawbacks: ["Needs several timed applications", "High leaching and runoff risk if over-applied", "Requires accurate spreading"] },
  { id: "potassium_focused", name: "Potassium-Focused Fertilizer", npk: "Potassium-focused; grade set by the label.",
    organic: false, cost: 2, eco: 2, ease: 2, scale: { backyard: 2, small: 3, medium: 3, large: 3 }, soilTestDependent: true, nitrogen: false,
    costBasis: "Mid-range cost per unit of nutrient (AgriSense estimate).",
    sources: [{ key: "cv296", scope: "veg" }, { key: "ss163", scope: "agronomic" }, { key: "ag496", scope: "peanut" }, { key: "epa", scope: "any" }],
    bestFor: ["Fields where a soil test shows low potassium"],
    environment: "Targets one nutrient, which avoids adding nitrogen or phosphorus that is not needed. Potassium can still leach in very sandy soils.",
    drawbacks: ["Only useful if a soil test shows potassium is needed", "Does not supply nitrogen", "Some sources add salt or chloride"] },
  { id: "pk_no_nitrogen", name: "Phosphorus and Potassium Without Nitrogen", npk: "Nitrogen-free (0 N); P and K amounts set by the label.",
    organic: false, cost: 2, eco: 2, ease: 2, scale: { backyard: 2, small: 3, medium: 3, large: 3 }, soilTestDependent: true, nitrogen: false,
    costBasis: "Mid-range cost per unit of nutrient (AgriSense estimate).",
    sources: [{ key: "cv296", scope: "veg" }, { key: "ss163", scope: "agronomic" }, { key: "ag496", scope: "peanut" }, { key: "epa", scope: "any" }],
    bestFor: ["Crops where UF/IFAS data suggests no routine nitrogen", "Fields where a soil test shows P or K is low"],
    environment: "Skips nitrogen when it is supplied separately or not needed. Phosphorus should only be added when a soil test indicates it, because excess phosphorus can reach waterways.",
    drawbacks: ["Only appropriate when a soil test shows P or K is needed", "Phosphorus over-application is a water-quality concern", "Does not meet a crop's nitrogen needs"] },
];

export interface FertilizerContext {
  cropId: string;
  /** UF/IFAS suggested N from crop data; 0 means no routine N is suggested, null means unknown. */
  nPerAcre: number | null | undefined;
  vegetable: boolean;
  acres?: number;
  /** Regional estimates only. Never treat these as soil-test results. */
  conditions?: Pick<Conditions, "texture" | "drainage" | "sand_pct" | "soil_ph" | "organic_matter_pct"> | null;
  /** Only real soil-test values belong here; regional estimates must not. */
  soilTest?: SoilTest;
  phIdeal?: [number, number] | null;
}

export interface FertilizerRecommendation {
  id: string;
  name: string;
  npk: string;
  cost: "$" | "$$" | "$$$";
  costBasis: string;
  organic: boolean;
  traits: Record<FilterId, boolean>;
  score: number;
  whyRecommended: string;
  whyAgriSense: string[];
  bestFor: string[];
  environment: string;
  drawbacks: string[];
  /** Non-null when the option should not be used without a soil test or professional advice. */
  conditional: string | null;
  sources: Source[];
}

export function acreBand(acres: number | undefined): AcreBand {
  if (acres === undefined || !Number.isFinite(acres) || acres <= 0) return "unknown";
  if (acres < 1) return "backyard";
  if (acres < 5) return "small";
  if (acres < 100) return "medium";
  return "large";
}

const BAND_TEXT: Record<AcreBand, string> = {
  unknown: "Land size: no acreage was given, so practicality for your land size is not factored in.",
  backyard: "Land size: at under 1 acre, small bags and hand spreading are practical; bulk or machinery-scale products are not.",
  small: "Land size: at 1 to 5 acres, small-farm handling and cost per unit of nutrient both matter.",
  medium: "Land size: at 5 to 100 acres, cost per unit of nutrient and spreader-friendly products matter most.",
  large: "Land size: at 100+ acres, bulk, machinery-applied products are the practical choice.",
};

export function isSandy(c: FertilizerContext["conditions"]): boolean {
  if (!c) return false;
  return (c.sand_pct ?? 0) >= 80 || /sand/i.test(c.texture ?? "") || /excessively/i.test(c.drainage ?? "");
}

function isMuck(c: FertilizerContext["conditions"]): boolean {
  return !!c && ((c.organic_matter_pct ?? 0) > 20 || /muck/i.test(c.texture ?? ""));
}

const isLow = (r?: Rating) => r === "low";
const isOk = (r?: Rating) => r === "adequate" || r === "high";

/** Crop-data fit (UF/IFAS nitrogen figure only). Nitrogen alone never decides a crop's full needs. */
function cropFit(item: Catalog, ctx: FertilizerContext): { fit: number; reasons: string[]; conditional: string | null } {
  const reasons: string[] = [];
  const n = ctx.nPerAcre;
  const noRoutineN = n === 0;
  const heavyN = typeof n === "number" && n >= 150;
  let fit = 2;
  let conditional: string | null = null;
  if (noRoutineN && item.nitrogen) {
    fit = 1;
    conditional = "UF/IFAS crop data suggests no routine nitrogen for this crop. That is not a guarantee: use a nitrogen-supplying product only if a soil test or your county extension agent advises it.";
    reasons.push("Crop data: no routine nitrogen is suggested for this crop, but other nutrients may still be needed, so this stays a conditional option.");
  }
  if (item.id === "pk_no_nitrogen") {
    if (noRoutineN) { fit = 3; reasons.push("Crop data: no routine nitrogen is suggested for this crop, so a nitrogen-free product matches that, if a soil test shows P or K is needed."); }
    else { fit = 1; reasons.push("Crop data: this crop has a nitrogen recommendation, so this option would need nitrogen supplied separately."); }
  }
  if (heavyN && ["controlled_release_n", "nitrogen_soluble"].includes(item.id)) {
    fit = 3;
    reasons.push(`Crop data: nitrogen is a major input for this crop (UF/IFAS suggests about ${n} lb N per acre per season), so nitrogen-focused options are relevant. Phosphorus and potassium needs depend on a soil test.`);
  } else if (typeof n === "number" && n > 0 && item.nitrogen) {
    reasons.push(`Crop data: UF/IFAS suggests about ${n} lb N per acre per season, split across several applications.`);
  }
  if (n == null && item.nitrogen) reasons.push("Crop data: no nitrogen figure is available for this crop, so confirm nitrogen needs with UF/IFAS Extension.");
  if (ctx.vegetable && item.id === "controlled_release_n") reasons.push("Crop data: UF/IFAS vegetable guidance encourages controlled- or slow-release products for preplant nitrogen and potassium to reduce leaching.");
  if (item.id === "compost") reasons.push("Soil: UF/IFAS reports organic amendments such as compost can raise organic matter and water holding capacity in Florida sandy soils.");
  return { fit, reasons, conditional };
}

/** Soil adjustments. Regional values are estimates; only ctx.soilTest is treated as measured. */
function soilAdjust(item: Catalog, ctx: FertilizerContext): { ecoDelta: number; fitDelta: number; reasons: string[]; excluded: boolean; conditional: string | null } {
  const out = { ecoDelta: 0, fitDelta: 0, reasons: [] as string[], excluded: false, conditional: null as string | null };
  const t = ctx.soilTest;
  const soluble = ["balanced_soluble", "nitrogen_soluble"].includes(item.id);
  if (isSandy(ctx.conditions)) {
    if (soluble) { out.ecoDelta = -1; out.reasons.push("Regional estimate: sandy, fast-draining soil (not a soil test) raises leaching risk for soluble nutrients."); }
    if (["slow_release_balanced", "controlled_release_n", "compost"].includes(item.id)) { out.fitDelta = 1; out.reasons.push("Regional estimate: sandy, fast-draining soil (not a soil test), where slower release and organic matter can help."); }
  }
  if (isMuck(ctx.conditions) && item.id === "compost") { out.fitDelta = -1; out.reasons.push("Regional estimate: muck soils are already very high in organic matter, so extra compost adds less."); }
  const hasP = ["balanced_soluble", "slow_release_balanced", "pk_no_nitrogen"].includes(item.id);
  if (hasP && isOk(t?.p)) {
    out.fitDelta -= 2;
    out.conditional = "Your soil test reports adequate or high phosphorus. Prefer a phosphorus-free option.";
    out.reasons.push("Soil test: phosphorus is adequate or high, so avoid fertilizer that adds more.");
  }
  if (item.id === "potassium_focused") {
    if (isOk(t?.k)) out.excluded = true;
    if (isLow(t?.k)) { out.fitDelta += 2; out.reasons.push("Soil test: potassium is low."); }
  }
  if (item.id === "pk_no_nitrogen") {
    if (isOk(t?.p) && isOk(t?.k)) out.excluded = true;
    if (isLow(t?.k) || isLow(t?.p)) { out.fitDelta += 2; out.reasons.push("Soil test: phosphorus or potassium is low."); }
  }
  return out;
}

/** True when a supplied soil test actually supports the nutrients this option adds. */
function supportedBySoilTest(item: Catalog, t?: SoilTest): boolean {
  if (!t) return false;
  if (item.id === "potassium_focused") return isLow(t.k);
  if (item.id === "pk_no_nitrogen") return isLow(t.k) || isLow(t.p);
  if (item.soilTestDependent) return isLow(t.p);
  return false;
}

const SOIL_TEST_NOTE = "No soil-test results are available. P and K needs come from a soil test (UF/IFAS), so use this only if a test shows the nutrients it supplies are needed.";

function sourcesFor(item: Catalog, ctx: FertilizerContext): Source[] {
  const peanut = ctx.cropId === "peanut";
  return item.sources.filter(({ scope }) => scope === "any" || (scope === "veg" && ctx.vegetable) || (scope === "agronomic" && !ctx.vegetable)
    || (scope === "peanut" && peanut)).map(({ key }) => source(key));
}

function traitsFor(item: Catalog, ecoScore: number, band: AcreBand): Record<FilterId, boolean> {
  return {
    eco: ecoScore >= 2,
    cost: item.cost === 1,
    organic: item.organic,
    low_maintenance: item.ease >= 3,
    small_space: item.scale.backyard >= 3 && band !== "large",
  };
}

/** Rank all suitable fertilizer categories for the crop; filters are applied separately. */
export function recommendFertilizers(ctx: FertilizerContext): FertilizerRecommendation[] {
  const band = acreBand(ctx.acres);
  const results: FertilizerRecommendation[] = [];
  for (const item of CATALOG) {
    const cf = cropFit(item, ctx);
    const sa = soilAdjust(item, ctx);
    if (sa.excluded) continue;
    const eco = Math.max(0, Math.min(3, item.eco + sa.ecoDelta));
    const scaleFit = band === "unknown" ? 1.5 : item.scale[band];
    const supported = supportedBySoilTest(item, ctx.soilTest);
    const conditional = sa.conditional ?? cf.conditional
      ?? (item.soilTestDependent && !supported ? SOIL_TEST_NOTE : null);
    const sources = sourcesFor(item, ctx);
    const evidence = sources.some((s) => !/epa\.gov/.test(s.url)) ? 1 : 0;
    // Weights: crop need 3x, land-size practicality 2x, evidence, then eco and affordability.
    const score = 3 * Math.max(0, cf.fit + sa.fitDelta) + 2 * scaleFit + evidence + eco + (4 - item.cost) / 2;
    const reasons = [...cf.reasons, ...sa.reasons, BAND_TEXT[band]];
    if (conditional) reasons.push("Nutrient amounts are not estimated here; a soil test decides whether and how much to apply.");
    const bestFor = [...item.bestFor];
    if (band === "large" && item.scale.large >= 2 && !bestFor.includes("Larger agricultural plots")) bestFor.push("Larger agricultural plots");
    results.push({
      id: item.id, name: item.name, npk: item.npk, cost: "$".repeat(item.cost) as "$" | "$$" | "$$$", costBasis: item.costBasis,
      organic: item.organic, traits: traitsFor(item, eco, band), score,
      whyRecommended: conditional
        ? `${item.name} is a conditional option for this crop: consider it only if the condition below is met.`
        : `${item.name} suits ${ctx.vegetable ? "this vegetable crop" : "this field crop"}${band === "unknown" ? " (acreage not provided)" : scaleFit >= 2 ? " and your land size" : ", though it is a less practical fit for your land size"}.`,
      whyAgriSense: reasons, bestFor, environment: item.environment, drawbacks: item.drawbacks, conditional, sources,
    });
  }
  // Options that need a soil test or professional advice never outrank those that do not.
  return results.sort((a, b) => Number(a.conditional !== null) - Number(b.conditional !== null) || b.score - a.score || a.name.localeCompare(b.name));
}

/** Keep only options matching EVERY selected filter. Empty selection means "All". */
export function applyFilters(list: FertilizerRecommendation[], selected: readonly FilterId[]): FertilizerRecommendation[] {
  if (!selected.length) return list;
  return list.filter((item) => selected.every((id) => item.traits[id]));
}

const NUM = (v: unknown): number | null => typeof v === "number" && Number.isFinite(v) ? v : null;
const VEG = new Set(["tomato", "watermelon", "strawberry", "potato", "sweet_corn", "snap_bean", "bell_pepper", "cabbage"]);

/** Build a context from a crop detail response and the optional acreage. */
export function contextFromCrop(crop: {
  id: string | null; nutrient_plan?: { n_lb_per_acre: number | null } | null;
  conditions?: FertilizerContext["conditions"]; requirements?: CropDetail["requirements"];
}, acres?: number): FertilizerContext {
  const req = (crop.requirements ?? {}) as Record<string, unknown>;
  const lo = NUM(req.ph_ideal_min);
  const hi = NUM(req.ph_ideal_max);
  return {
    cropId: crop.id ?? "", nPerAcre: crop.nutrient_plan?.n_lb_per_acre ?? null, vegetable: VEG.has(crop.id ?? ""), acres,
    conditions: crop.conditions, phIdeal: lo !== null && hi !== null ? [lo, hi] : null,
  };
}

/** Message about estimated pH vs the crop's ideal range; never a measured result. */
export function phNote(ctx: FertilizerContext): string | null {
  const ph = ctx.conditions?.soil_ph;
  if (ph == null || !ctx.phIdeal) return null;
  const [lo, hi] = ctx.phIdeal;
  if (ph >= lo && ph <= hi) return null;
  return `Regional data estimates soil pH near ${ph}, outside this crop's ideal ${lo}–${hi}. Test your soil pH first: pH affects nutrient availability and lime may matter more than fertilizer.`;
}
