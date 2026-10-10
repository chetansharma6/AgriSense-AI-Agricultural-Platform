import { locationSearchUnavailable, type LocationResult } from "@/lib/location";

export const runtime = "nodejs";

const CACHE_MAX_ENTRIES = 256;
const CACHE_TTL_MS = 5 * 60_000;
type CacheEntry = { results: LocationResult[]; expiresAt: number };
const cache = new Map<string, CacheEntry>();
const pending = new Map<string, Promise<LocationResult[]>>();
let cityQueue: Promise<void> = Promise.resolve();
let lastCityRequest = 0;
const userAgent = "AgriSense-hackathon/1.0 (https://github.com/chetansharma6/AgriSense-AI-Agricultural-Platform)";

function cachedResults(key: string): LocationResult[] | undefined {
  const entry = cache.get(key);
  if (!entry) return undefined;
  if (entry.expiresAt <= Date.now()) {
    cache.delete(key);
    return undefined;
  }
  cache.delete(key);
  cache.set(key, entry);
  return entry.results;
}

function rememberResults(key: string, results: LocationResult[]): void {
  cache.delete(key);
  cache.set(key, { results, expiresAt: Date.now() + CACHE_TTL_MS });
  while (cache.size > CACHE_MAX_ENTRIES) cache.delete(cache.keys().next().value as string);
}

type ZipResponse = {
  places: { "place name": string; "state abbreviation": string; latitude: string; longitude: string }[];
};
type CityResult = {
  lat: string;
  lon: string;
  name?: string;
  addresstype?: string;
  category?: string;
  address: {
    city?: string; town?: string; village?: string; hamlet?: string;
    county?: string; state?: string; "ISO3166-2-lvl4"?: string;
  };
};

function inFlorida(result: LocationResult): boolean {
  return result.state === "FL" && Number.isFinite(result.lat) && Number.isFinite(result.lon)
    && result.lat >= 24.3 && result.lat <= 31.1 && result.lon >= -87.7 && result.lon <= -79.9;
}

async function upstream(url: string): Promise<Response> {
  return fetch(url, {
    headers: { "User-Agent": userAgent },
    signal: AbortSignal.timeout(8_000),
    cache: "no-store",
  });
}

async function findZip(q: string): Promise<LocationResult[]> {
  const response = await upstream(`https://api.zippopotam.us/us/${q}`);
  if (response.status === 404) return [];
  if (!response.ok) throw new Error("ZIP lookup failed");
  const data = await response.json() as ZipResponse;
  const place = data.places[0];
  if (!place) return [];
  const result: LocationResult = {
    label: `${place["place name"]}, ${place["state abbreviation"]}`,
    lat: Number(place.latitude), lon: Number(place.longitude),
    county: null, state: place["state abbreviation"],
  };
  return inFlorida(result) ? [result] : [];
}

async function findCity(q: string): Promise<LocationResult[]> {
  // One process-wide queue: upstream city requests never overlap or start within a second.
  const task = cityQueue.then(async () => {
    const wait = Math.max(0, 1_000 - (Date.now() - lastCityRequest));
    if (wait) await new Promise((resolve) => setTimeout(resolve, wait));
    const url = new URL(process.env.NOMINATIM_SEARCH_URL ?? "https://nominatim.openstreetmap.org/search");
    url.search = new URLSearchParams({
      q, format: "jsonv2", countrycodes: "us", addressdetails: "1", limit: "5",
      viewbox: "-87.7,31.1,-79.9,24.3", bounded: "1",
    }).toString();
    lastCityRequest = Date.now();
    const response = await upstream(url.toString());
    if (!response.ok) throw new Error("City lookup failed");
    const data = await response.json() as CityResult[];
    return data.filter((place) => place.addresstype !== "road" && place.category !== "highway").map((place): LocationResult | null => {
      const address = place.address ?? {};
      const state = address["ISO3166-2-lvl4"] === "US-FL" || address.state === "Florida" ? "FL" : "";
      const name = address.city ?? address.town ?? address.village ?? address.hamlet ?? place.name;
      if (!name || !Number.isFinite(Number(place.lat)) || !Number.isFinite(Number(place.lon))) return null;
      return {
        label: [name, address.county, state].filter(Boolean).join(", "),
        lat: Number(place.lat), lon: Number(place.lon), county: address.county ?? null, state,
      };
    }).filter((result): result is LocationResult => result !== null && inFlorida(result));
  });
  cityQueue = task.then(() => undefined, () => undefined);
  return task;
}

export async function GET(request: Request): Promise<Response> {
  const q = (new URL(request.url).searchParams.get("q") ?? "").trim();
  if (!q || q.length > 100) {
    return Response.json({ detail: "Enter a city or ZIP code of 1 to 100 characters." }, { status: 400 });
  }
  const key = q.toLowerCase();
  const cached = cachedResults(key);
  if (cached) return Response.json({ results: cached });
  try {
    let lookup = pending.get(key);
    if (!lookup) {
      lookup = (/^\d{5}$/.test(q) ? findZip(q) : findCity(q)).then((results) => {
        rememberResults(key, results);
        return results;
      }).finally(() => pending.delete(key));
      pending.set(key, lookup);
    }
    return Response.json({ results: await lookup });
  } catch {
    return Response.json({ detail: locationSearchUnavailable }, { status: 502 });
  }
}
