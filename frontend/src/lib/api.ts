import { locationSearchUnavailable, type LocationResult } from "./location";
import { getMockCropDetail, getMockRecommend } from "../mocks";
import type { CropDetail, RecommendResponse } from "./types";

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

const connectionMessage =
  "Can't reach the AgriSense server. Check your connection and try again.";
const fallbackWarning =
  "Live data is temporarily unavailable. Showing the nearest saved Florida demo response.";

function backendUnavailable(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 0 || error.status >= 500);
}

function fallbackRecommendations(lat: number, lon: number, acres?: number): RecommendResponse {
  const response = getMockRecommend(lat, lon, acres);
  response.warnings = [fallbackWarning, ...(response.warnings ?? [])];
  return response;
}

function mockDelay(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 500));
}

async function request<T>(path: string, lat: number, lon: number, acres?: number): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90_000);
  const query = new URLSearchParams({ lat: String(lat), lon: String(lon) });
  if (acres !== undefined) query.set("acres", String(acres));
  const baseUrl = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/+$/, "");

  try {
    const response = await fetch(`${baseUrl}/api/${path}?${query}`, {
      signal: controller.signal,
    });
    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      try {
        const body: unknown = await response.json();
        if (typeof body === "object" && body !== null && "detail" in body
          && typeof body.detail === "string") {
          message = body.detail;
        }
      } catch {
        // Preserve the HTTP status even when an error body is not valid JSON.
      }
      throw new ApiError(message, response.status);
    }
    return await response.json() as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(connectionMessage, 0);
  } finally {
    clearTimeout(timeout);
  }
}

export async function getRecommendations(lat: number, lon: number, acres?: number): Promise<RecommendResponse> {
  if (process.env.NEXT_PUBLIC_USE_MOCKS === "true") {
    await mockDelay();
    try {
      return getMockRecommend(lat, lon, acres);
    } catch (error) {
      throw new ApiError(error instanceof Error ? error.message : "Mock data is unavailable.", 0);
    }
  }
  try {
    return await request<RecommendResponse>("recommend", lat, lon, acres);
  } catch (error) {
    if (backendUnavailable(error)) return fallbackRecommendations(lat, lon, acres);
    throw error;
  }
}

export async function getCropDetail(id: string, lat: number, lon: number, acres?: number): Promise<CropDetail> {
  if (process.env.NEXT_PUBLIC_USE_MOCKS === "true") {
    await mockDelay();
    try {
      return getMockCropDetail(id, lat, lon, acres);
    } catch (error) {
      if (error instanceof Error && error.message === "Unknown crop") {
        throw new ApiError(error.message, 404);
      }
      throw new ApiError(error instanceof Error ? error.message : "Mock data is unavailable.", 0);
    }
  }
  try {
    return await request<CropDetail>(`crops/${encodeURIComponent(id)}`, lat, lon, acres);
  } catch (error) {
    if (backendUnavailable(error)) {
      return getMockCropDetail(id, lat, lon, acres);
    }
    throw error;
  }
}

export async function searchLocation(q: string): Promise<LocationResult[]> {
  try {
    const response = await fetch(`/api/geocode?${new URLSearchParams({ q })}`);
    const body = await response.json();
    if (!response.ok) {
      throw new ApiError(typeof body.detail === "string" ? body.detail : locationSearchUnavailable, response.status);
    }
    return body.results as LocationResult[];
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(locationSearchUnavailable, 0);
  }
}
