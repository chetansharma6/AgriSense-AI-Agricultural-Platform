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
// Persist only successful AI reports; share in-flight work without caching failures.
const cache = new Map<string, Result>();
const inFlight = new Map<string, Promise<Result>>();

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
  function factorLine(factor: { key: FactorKey; value: number }, description: string): string {
    const detail = object(object(crop.factor_details)?.[factor.key]);
    const unit = typeof detail?.unit === "string" ? ` ${detail.unit}` : "";
    const actual = detail?.value == null ? "No data" : `${String(detail.value)}${unit}`;
    const ideal = typeof detail?.ideal === "string" ? `${detail.ideal}${unit}` : "No data";
    return `${factorLabel(factor.key)} is ${description} at ${factor.value}/100: ${actual} vs ideal ${ideal}.`;
  }
  const pros = factors.slice(0, 3).map((factor) => factorLine(factor, "one of the strongest factors"));
  const flags = Array.isArray(crop.flags) ? crop.flags.filter((flag): flag is string => typeof flag === "string" && !!flag.trim()).map((flag) => flag.trim()) : [];
  const cons = [...new Set(flags)].slice(0, 3);
  for (const factor of [...factors].reverse().filter((factor) => factor.value < 75)) {
    if (cons.length >= 3) break;
    const line = factorLine(factor, "one of the weakest factors");
    if (!cons.includes(line)) cons.push(line);
  }
  const missing = keys.filter((key) => crop.factors?.[key] == null);
  return {
    verdict: crop.score === null ? `${crop.name} has no suitability score available.` : `${crop.name} is ${label} with a suitability score of ${crop.score}/100.`,
    summary: `${crop.score === null ? "The suitability score is missing" : `The supplied suitability score is ${crop.score}/100`}. ${factors.length ? `The highest available factor is ${factorLabel(factors[0].key)} at ${factors[0].value}/100` : "All factor scores are missing"}.${missing.length ? ` Missing factor data: ${missing.map(factorLabel).join(", ")}.` : " Review the factor values alongside local conditions before planting."}`,
    pros, cons,
    first_steps: ["Get a soil test before deciding what to plant.", "Talk with your county UF/IFAS Extension agent about local conditions.", "Check water access, drainage and the recommended planting window.", "Confirm expected costs and a market for the crop before planting."],
  };
}

function safeMessage(value: unknown): string {
  let message = value instanceof Error ? value.message : "Unknown error";
  const key = process.env.ANTHROPIC_API_KEY?.trim();
  if (key) message = message.split(key).join("[redacted]");
  return message.replace(/sk-ant-[A-Za-z0-9_-]+/g, "[redacted]");
}

function parseReport(text: string): unknown {
  const stripped = text.trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
  try { return JSON.parse(stripped); } catch {
    // Recover the first balanced object, respecting braces inside JSON strings.
    const start = stripped.indexOf("{");
    let depth = 0;
    let quoted = false;
    let escaped = false;
    for (let i = start; start >= 0 && i < stripped.length; i++) {
      const char = stripped[i];
      if (quoted) {
        if (escaped) escaped = false;
        else if (char === "\\") escaped = true;
        else if (char === '"') quoted = false;
      } else if (char === '"') quoted = true;
      else if (char === "{") depth++;
      else if (char === "}" && --depth === 0) return JSON.parse(stripped.slice(start, i + 1));
    }
    throw new SyntaxError("No complete JSON report object found");
  }
}

async function generate(crop: InputCrop): Promise<Result> {
  const local: Result = { report: fallback(crop), source: "fallback" };
  if (!process.env.ANTHROPIC_API_KEY?.trim()) {
    console.log("[report] source=fallback reason=no key");
    return local;
  }
  const model = process.env.ANTHROPIC_MODEL ?? "claude-haiku-5-5";
  let phase = "api";
  try {
    const client = new Anthropic();
    const message = await client.messages.create({
      // The configured model rejects the deprecated temperature parameter.
      model, max_tokens: 800, thinking: { type: "disabled" }, system: SYSTEM_PROMPT,
      messages: [{ role: "user", content: `${JSON.stringify(crop)}\n\n${INSTRUCTION}` }],
    }, { timeout: 20_000, maxRetries: 0 });
    console.log(`[report] response stop_reason=${message.stop_reason} text_blocks=${message.content.filter((block) => block.type === "text").length} output_tokens=${message.usage.output_tokens}`);
    phase = "parse";
    const text = message.content.filter((block) => block.type === "text").map((block) => block.text).join("\n");
    const parsed = parseReport(text);
    if (!validReport(parsed, crop.name)) throw new Error("Report JSON does not match the required fields or verdict format");
    console.log("[report] source=ai reason=valid report");
    return { report: parsed, source: "ai" };
  } catch (error) {
    const status = object(error)?.status;
    const type = error instanceof Error ? error.name : "UnknownError";
    console.error(`[report] failure ${JSON.stringify({ type, status: typeof status === "number" ? status : null, message: safeMessage(error), ...(status === 404 ? { model } : {}) })}`);
    console.log(`[report] source=fallback reason=${phase} error${typeof status === "number" ? ` ${status}` : ""}`);
    return local;
  }
}

export async function POST(request: Request): Promise<Response> {
  let body: unknown;
  try { body = await request.json(); } catch { return Response.json({ detail: "Invalid JSON body" }, { status: 400 }); }
  const crop = object(body)?.crop;
  if (!validCrop(crop)) return Response.json({ detail: "crop must include id, name, score and all six factors (values may be null)" }, { status: 400 });
  const location = object(crop.location);
  const key = `${crop.id}:${location?.lat ?? "unknown"}:${location?.lon ?? "unknown"}`;
  const cached = cache.get(key);
  if (cached) {
    console.log("[report] source=ai reason=cache hit");
    return Response.json(cached);
  }
  let pending = inFlight.get(key);
  if (!pending) {
    pending = generate(crop).then((result) => {
      if (result.source === "ai") cache.set(key, result);
      return result;
    }).finally(() => inFlight.delete(key));
    inFlight.set(key, pending);
  }
  return Response.json(await pending);
}
