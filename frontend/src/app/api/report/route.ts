import "server-only";
import Anthropic from "@anthropic-ai/sdk";
import { factorLabel, scoreTone } from "@/lib/format";
import type { FactorKey } from "@/lib/types";

export const runtime = "nodejs";

const SYSTEM_PROMPT = "You write short crop reports for small-farm owners in Florida. Use ONLY the numbers and facts in the JSON you are given. Never invent scores, yields, prices, dates, chemical or product names. If data is missing, say so plainly. Write at an 8th-grade reading level. Mention UF/IFAS Extension when advice depends on local conditions. Respond with JSON only, no markdown.";
const INSTRUCTION = "Return JSON with keys: verdict (one sentence, max 25 words, starting with the crop name), summary (2-3 sentences explaining the score using the factor values), pros (exactly 3 short strings), cons (exactly 3 short strings, use the flags), first_steps (3-4 practical next steps a farmer would take before planting, e.g. soil test, talk to county extension agent).";
const keys: FactorKey[] = ["soil_ph", "drainage", "season_temp", "frost_risk", "rainfall", "local_history"];

type InputCrop = Record<string, unknown> & {
  id: string;
  name: string;
  score: number | null;
  factors: Record<FactorKey, number | null> | null;
};
type Report = { verdict: string; summary: string; pros: string[]; cons: string[]; first_steps: string[] };
type Result = { report: Report; source: "ai" | "fallback" };
// Cache promises as well as completed results so simultaneous clicks share one call.
const cache = new Map<string, Promise<Result>>();

function object(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function scoreValue(value: unknown): boolean {
  return value === null || typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100;
}

function validCrop(value: unknown): value is InputCrop {
  const c = object(value);
  if (!c || typeof c.id !== "string" || !c.id.trim() || typeof c.name !== "string" || !c.name.trim() || !scoreValue(c.score)) return false;
  if (c.factors === null) return true;
  const factors = object(c.factors);
  return !!factors && keys.every((key) => scoreValue(factors[key]));
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
  const missing = keys.filter((key) => crop.factors?.[key] == null);
  return {
    verdict: crop.score === null ? `${crop.name} has no suitability score available.` : `${crop.name} is ${label} with a suitability score of ${crop.score}/100.`,
    summary: `${crop.score === null ? "The suitability score is missing" : `The supplied suitability score is ${crop.score}/100`}. ${factors.length ? `The highest available factor is ${factorLabel(factors[0].key)} at ${factors[0].value}/100` : "All factor scores are missing"}.${missing.length ? ` Missing factor data: ${missing.map(factorLabel).join(", ")}.` : " Review the factor values alongside local conditions before planting."}`,
    pros, cons,
    first_steps: ["Get a soil test before deciding what to plant.", "Talk with your county UF/IFAS Extension agent about local conditions.", "Check water access, drainage and the recommended planting window.", "Confirm expected costs and a market for the crop before planting."],
  };
}

async function generate(crop: InputCrop): Promise<Result> {
  const local: Result = { report: fallback(crop), source: "fallback" };
  if (!process.env.ANTHROPIC_API_KEY?.trim()) return local;
  try {
    const client = new Anthropic();
    const message = await client.messages.create({
      model: process.env.ANTHROPIC_MODEL ?? "claude-haiku-5-5",
      max_tokens: 2000,
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content: `${JSON.stringify(crop)}\n\n${INSTRUCTION}` }],
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
  let body: unknown;
  try { body = await request.json(); } catch { return Response.json({ detail: "Invalid JSON body" }, { status: 400 }); }
  const crop = object(body)?.crop;
  if (!validCrop(crop)) return Response.json({ detail: "crop must include id, name, score and all six factors (values may be null)" }, { status: 400 });
  const location = object(crop.location);
  const key = `${crop.id}:${location?.lat ?? "unknown"}:${location?.lon ?? "unknown"}`;
  let pending = cache.get(key);
  if (!pending) { pending = generate(crop); cache.set(key, pending); }
  return Response.json(await pending);
}
