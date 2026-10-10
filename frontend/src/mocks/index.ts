import type { CropDetail, CropResult, RecommendResponse } from "../lib/types";
import acreage from "./acreage.json";
import marianna from "./marianna.json";
import hastings from "./hastings.json";
import plantCity from "./plant_city.json";
import belleGlade from "./belle_glade.json";

interface DemoSample {
  recommend: RecommendResponse;
  crops: Record<string, CropDetail>;
}

// Generated JSON widens literal strings; the generator supplies contract values.
const samples = [marianna, hastings, plantCity, belleGlade] as DemoSample[];
const farmNames = ["marianna", "hastings", "plant_city", "belle_glade"];
const acreageSamples = acreage as Record<string, Record<string, Record<string, Pick<CropResult, "scale" | "score" | "flags" | "est_gross_value">>>>;
const demos = samples.map((sample) => sample.recommend);

/** Great-circle distance term; sufficient for comparing demo locations. */
function distance(lat: number, lon: number, demoLat: number, demoLon: number): number {
  const radians = Math.PI / 180;
  return Math.sin((demoLat - lat) * radians / 2) ** 2
    + Math.cos(lat * radians) * Math.cos(demoLat * radians)
    * Math.sin((demoLon - lon) * radians / 2) ** 2;
}

/** Real backend samples. Return independent copies to protect shared fixtures. */
export function getMockRecommend(lat: number, lon: number, acres?: number): RecommendResponse {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    throw new Error("Latitude and longitude must be finite numbers");
  }
  let nearest = demos[0];
  let nearestDistance = Infinity;
  for (const demo of demos) {
    const candidate = distance(lat, lon, demo.location?.lat ?? NaN, demo.location?.lon ?? NaN);
    if (candidate < nearestDistance) {
      nearest = demo;
      nearestDistance = candidate;
    }
  }
  const result = structuredClone(nearest);
  if (acres !== undefined) {
    const overrides = acreageSamples[farmNames[demos.indexOf(nearest)]][String(acres)];
    if (!overrides) throw new Error("Mock acreage supports 0.5, 3, 10, 50 or 100 acres. Choose a quick pick or use the live API for another size.");
    result.crops = (result.crops ?? []).map((crop) => ({ ...crop, ...overrides[crop.id ?? ""] }))
      .sort((a, b) => (b.score ?? -1) - (a.score ?? -1) || (a.name ?? "").localeCompare(b.name ?? ""));
  }
  return result;
}

export function getMockCropDetail(id: string, lat: number, lon: number, acres?: number): CropDetail {
  const nearest = getMockRecommend(lat, lon);
  const sample = samples.find((candidate) => candidate.recommend.location?.lat === nearest.location?.lat
    && candidate.recommend.location?.lon === nearest.location?.lon);
  const detail = sample?.crops[id];
  if (!detail) throw new Error("Unknown crop");
  const result = structuredClone(detail);
  if (acres !== undefined) {
    const overrides = getMockRecommend(lat, lon, acres).crops?.find((crop) => crop.id === id);
    if (overrides) Object.assign(result, overrides);
  }
  return result;
}
