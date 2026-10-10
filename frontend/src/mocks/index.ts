import type { CropDetail, RecommendResponse } from "../lib/types";
import marianna from "./marianna.json";
import hastings from "./hastings.json";
import plantCity from "./plant_city.json";
import belleGlade from "./belle_glade.json";

// Check every JSON fixture without assertions that could hide type mismatches.
const demos = [marianna, hastings, plantCity, belleGlade] satisfies RecommendResponse[];

/** Great-circle distance term; sufficient for comparing demo locations. */
function distance(lat: number, lon: number, demoLat: number, demoLon: number): number {
  const radians = Math.PI / 180;
  return Math.sin((demoLat - lat) * radians / 2) ** 2
    + Math.cos(lat * radians) * Math.cos(demoLat * radians)
    * Math.sin((demoLon - lon) * radians / 2) ** 2;
}

/** Synthetic demo data. Return independent copies to protect shared fixtures. */
export function getMockRecommend(lat: number, lon: number): RecommendResponse {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    throw new Error("Latitude and longitude must be finite numbers");
  }
  let nearest = demos[0];
  let nearestDistance = Infinity;
  for (const demo of demos) {
    const candidate = distance(lat, lon, demo.location.lat, demo.location.lon);
    if (candidate < nearestDistance) {
      nearest = demo;
      nearestDistance = candidate;
    }
  }
  return structuredClone(nearest);
}

export function getMockCropDetail(id: string, lat: number, lon: number): CropDetail {
  const recommendation = getMockRecommend(lat, lon);
  const crop = recommendation.crops?.find((candidate) => candidate.id === id);
  if (!crop) throw new Error("Unknown crop");

  return {
    ...crop,
    requirements: {
      mock: true,
      soil_ph_ideal: crop.factor_details?.soil_ph?.ideal ?? null,
      drainage_ideal: crop.factor_details?.drainage?.ideal ?? null,
      season_temp_ideal: crop.factor_details?.season_temp?.ideal ?? null,
      rainfall_ideal: crop.factor_details?.rainfall?.ideal ?? null,
      fl_windows: [crop.season_label],
    },
    general_guidance: `Mock guidance for ${crop.name} near ${recommendation.location?.county}: ${crop.season_label}. Review soil pH, drainage, irrigation, and freeze protection with your local Extension office. Scores, yields, prices, and requirements in this demo are synthetic fixtures, not measured data or farm advice.`,
    extension_links: [{
      title: "UF/IFAS Extension publications (EDIS)",
      url: "https://edis.ifas.ufl.edu/",
    }],
    conditions: recommendation.conditions,
    location: recommendation.location,
  };
}
