import "server-only";
import Anthropic from "@anthropic-ai/sdk";
import { factorLabel, scoreTone } from "@/lib/format";
import type { FactorKey } from "@/lib/types";

export const runtime = "nodejs";

const SYSTEM_PROMPT = "You write short crop reports for small-farm owners in Florida. Use ONLY the numbers and facts in the JSON you are given. Never invent scores, yields, prices, dates, nutrient rates, chemical or product names. Mention soil testing and the lower-impact practices in nutrient_plan. Use only provided numbers; omit nitrogen rates when n_lb_per_acre is null or missing. Treat the supplied acres as context for land size, never calculate or invent a rate. If data is missing, say so plainly. Write at an 8th-grade reading level. Mention UF/IFAS Extension when advice depends on local conditions. Respond with JSON only, no markdown.";
const INSTRUCTION = "Return JSON with keys: verdict (one sentence, max 25 words, starting with the crop name), summary (2-3 sentences explaining the score using the factor values), pros (exactly 3 short strings), cons (exactly 3 short strings, use the flags), first_steps (3-4 practical next steps a farmer would take before planting, e.g. soil test, talk to county extension agent).";
const keys: FactorKey[] = ["soil_ph", "drainage", "season_temp", "frost_risk", "rainfall", "local_history"];
const MAX_BODY_BYTES = 64 * 1024;
const MAX_STRING_LENGTH = 500;
const CROP_NAMES: Record<string, string> = {
  peanut: "Peanut", cotton: "Cotton", field_corn: "Field corn", soybean: "Soybean",
  sugarcane: "Sugarcane", tomato: "Tomato", watermelon: "Watermelon", strawberry: "Strawberry",
  potato: "Potato", sweet_corn: "Sweet corn", snap_bean: "Snap bean", bell_pepper: "Bell pepper",
  cabbage: "Cabbage",
};
const CROP_FIELDS = new Set(["id", "name", "score", "season_label", "factors", "factor_details", "avg_yield", "price", "scale", "est_gross_value", "limited_by", "flags", "nutrient_plan", "requirements", "general_guidance", "extension_links", "conditions", "location", "scoring", "provenance", "confidence"]);

type InputCrop = Record<string, unknown> & {
  id: string;
  name: string;
  score: number | null;
  factors: Record<FactorKey, number | null> | null;
};
type TrustedCrop = Pick<InputCrop, "id" | "name" | "score" | "factors">;
type Report = { verdict: string; summary: string; pros: string[]; cons: string[]; first_steps: string[] };
type Result = { report: Report; source: "ai" | "fallback" };
const CACHE_MAX_ENTRIES = 256;
const CACHE_TTL_MS = 5 * 60_000;
type CacheEntry = { promise: Promise<Result>; expiresAt: number };
// Cache promises as well as completed results so simultaneous clicks share one call.
const cache = new Map<string, CacheEntry>();

function object(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function boundedStrings(value: unknown): boolean {
  if (typeof value === "string") return value.length <= MAX_STRING_LENGTH;
  if (Array.isArray(value)) return value.every(boundedStrings);
  const record = object(value);
  return record === null || Object.values(record).every(boundedStrings);
}

function scoreValue(value: unknown): boolean {
  return value === null || typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100;
}

function validCrop(value: unknown): value is InputCrop {
  const c = object(value);
  if (!c || Object.keys(c).some((key) => !CROP_FIELDS.has(key)) || typeof c.id !== "string" || !CROP_NAMES[c.id]
    || typeof c.name !== "string" || c.name.length > MAX_STRING_LENGTH || !c.name.trim() || !scoreValue(c.score)) return false;
  if (c.factors === null) return true;
  const factors = object(c.factors);
  return !!factors && keys.every((key) => scoreValue(factors[key]));
}

function trustedCrop(crop: InputCrop): TrustedCrop {
  return { id: crop.id, name: CROP_NAMES[crop.id], score: crop.score, factors: crop.factors };
}

function cachedResult(key: string): Promise<Result> | undefined {
  const entry = cache.get(key);
  if (!entry) return undefined;
  if (entry.expiresAt <= Date.now()) {
    cache.delete(key);
    return undefined;
  }
  cache.delete(key);
  cache.set(key, entry);
  return entry.promise;
}

function rememberResult(key: string, promise: Promise<Result>): void {
  cache.delete(key);
  const entry: CacheEntry = { promise, expiresAt: Date.now() + CACHE_TTL_MS };
  cache.set(key, entry);
  while (cache.size > CACHE_MAX_ENTRIES) cache.delete(cache.keys().next().value as string);
  promise.catch(() => {
    if (cache.get(key) === entry) cache.delete(key);
  });
}

function strings(value: unknown, min: number, max = min): value is string[] {
  return Array.isArray(value) && value.length >= min && value.length <= max
    && value.every((item) => typeof item === "string" && item.trim().length > 0);
}

function validReport(value: unknown, name: string): value is Report {
  const r = object(value);
  return !!r && typeof r.verdict === "string" && r.verdict.startsWith(name)
    && r.verdict.trim().split(/\s+/).length <= 25
    && typeof r.summary === "string" && !!r.summary.trim()
    && strings(r.pros, 3) && strings(r.cons, 3) && strings(r.first_steps, 3, 4);
}

function fallback(crop: InputCrop): Report {
  const tone = scoreTone(crop.score);
  const label = tone === "strong" ? "a strong fit" : tone === "fair" ? "a fair fit" : "a weak fit";
  const factors = keys.map((key) => ({ key, value: crop.factors?.[key] ?? null }))
    .filter((factor): factor is { key: FactorKey; value: number } => factor.value !== null)
    .sort((a, b) => b.value - a.value);
  const pros = factors.slice(0, 3).map((factor) => `${factorLabel(factor.key)} is one of the highest factors at ${factor.value}/100.`);
  while (pros.length < 3) pros.push("More factor data is needed to identify another advantage.");
  const cons = Array.isArray(crop.flags) ? crop.flags.filter((flag): flag is string => typeof flag === "string" && !!flag.trim()).slice(0, 3) : [];
  while (cons.length < 3) cons.push("No additional crop flag was provided; check local conditions with UF/IFAS Extension.");
  const plan = object(crop.nutrient_plan);
  const practices = Array.isArray(plan?.practices) ? plan.practices : [];
  const lowerImpact = practices.find((practice): practice is string => typeof practice === "string" && /cover crops|compost|controlled-release|drip/i.test(practice));
  const missing = keys.filter((key) => crop.factors?.[key] == null);
  return {
    verdict: crop.score === null ? `${crop.name} has no suitability score available.` : `${crop.name} is ${label} with a suitability score of ${crop.score}/100.`,
    summary: `${crop.score === null ? "The suitability score is missing" : `The supplied suitability score is ${crop.score}/100`}. ${factors.length ? `The highest available factor is ${factorLabel(factors[0].key)} at ${factors[0].value}/100` : "All factor scores are missing"}.${missing.length ? ` Missing factor data: ${missing.map(factorLabel).join(", ")}.` : " Review the factor values alongside local conditions before planting."}`,
    pros, cons,
    first_steps: ["Get a soil test before deciding what to plant.", "Talk with your county UF/IFAS Extension agent about local conditions.", lowerImpact ?? "Check water access, drainage and the recommended planting window.", "Confirm expected costs and a market for the crop before planting."],
  };
}

async function generate(crop: InputCrop, acres?: number): Promise<Result> {
  const local: Result = { report: fallback(crop), source: "fallback" };
  if (!process.env.ANTHROPIC_API_KEY?.trim()) return local;
  try {
    const client = new Anthropic();
    const message = await client.messages.create({
      model: process.env.ANTHROPIC_MODEL ?? "claude-haiku-5-5",
      max_tokens: 2000,
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content: `${JSON.stringify({ crop: trustedCrop(crop), acres: acres ?? null })}\n\n${INSTRUCTION}` }],
    }, { timeout: 20_000, maxRetries: 0 });
    const text = message.content.filter((block) => block.type === "text").map((block) => block.text).join("\n").trim();
    const parsed: unknown = JSON.parse(text.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, ""));
    if (validReport(parsed, crop.name)) return { report: parsed, source: "ai" };
  } catch {
    // Do not expose provider errors or credentials; use the local report instead.
  }
  return local;
}

export async function POST(request: Request): Promise<Response> {
  const contentLength = request.headers.get("content-length");
  if (contentLength && Number(contentLength) > MAX_BODY_BYTES) return Response.json({ detail: "Request body is too large" }, { status: 413 });
  let body: unknown;
  let rawBody: string;
  try {
    rawBody = await request.text();
    if (new TextEncoder().encode(rawBody).byteLength > MAX_BODY_BYTES) return Response.json({ detail: "Request body is too large" }, { status: 413 });
    body = JSON.parse(rawBody);
  } catch { return Response.json({ detail: "Invalid JSON body" }, { status: 400 }); }
  const input = object(body);
  if (!boundedStrings(body)) return Response.json({ detail: "String value is too large" }, { status: 413 });
  if (!input || Object.keys(input).some((key) => key !== "crop" && key !== "acres")) return Response.json({ detail: "Unexpected request field" }, { status: 400 });
  const cropInput = input.crop;
  if (!validCrop(cropInput)) return Response.json({ detail: "crop must include a known id, score and all six factors (values may be null)" }, { status: 400 });
  const crop: InputCrop = { ...cropInput, name: CROP_NAMES[cropInput.id] };
  const acres = input.acres;
  if (acres !== undefined && (typeof acres !== "number" || !Number.isFinite(acres) || acres < 0.1 || acres > 10000)) {
    return Response.json({ detail: "acres must be between 0.1 and 10000" }, { status: 400 });
  }
  const key = JSON.stringify({ crop: trustedCrop(crop), acres });
  let pending = cachedResult(key);
  if (!pending) { pending = generate(crop, acres); rememberResult(key, pending); }
  return Response.json(await pending);
}
