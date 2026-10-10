import type { CropDetail, RecommendResponse } from "../lib/types";
import marianna from "./marianna.json";
import hastings from "./hastings.json";
import plantCity from "./plant_city.json";
import belleGlade from "./belle_glade.json";

interface DemoSample {
  recommend: RecommendResponse;
  crops: Record<string, CropDetail>;
}

// Check every JSON fixture without assertions that could hide type mismatches.
const samples: DemoSample[] = [marianna, hastings, plantCity, belleGlade];
const demos = samples.map((sample) => sample.recommend);

/** Great-circle distance term; sufficient for comparing demo locations. */
function distance(lat: number, lon: number, demoLat: number, demoLon: number): number {
  const radians = Math.PI / 180;
  return Math.sin((demoLat - lat) * radians / 2) ** 2
    + Math.cos(lat * radians) * Math.cos(demoLat * radians)
    * Math.sin((demoLon - lon) * radians / 2) ** 2;
}

/** Real backend samples. Return independent copies to protect shared fixtures. */
export function getMockRecommend(lat: number, lon: number): RecommendResponse {
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
  return structuredClone(nearest);
}

export function getMockCropDetail(id: string, lat: number, lon: number): CropDetail {
  const nearest = getMockRecommend(lat, lon);
  const sample = samples.find((candidate) => candidate.recommend.location?.lat === nearest.location?.lat
    && candidate.recommend.location?.lon === nearest.location?.lon);
  const detail = sample?.crops[id];
  if (!detail) throw new Error("Unknown crop");
  return structuredClone(detail);
}
