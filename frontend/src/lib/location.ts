export interface LocationResult {
  label: string;
  lat: number;
  lon: number;
  county: string | null;
  state: string;
}

export const locationSearchUnavailable =
  "Location search is unavailable right now. Click the map or enter coordinates instead.";
