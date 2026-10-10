/** Omitted acreage stays optional; malformed query values never reach the API. */
export function parseAcres(raw: string | null): number | undefined {
  if (raw === null) return undefined;
  const value = Number(raw);
  return raw.trim() && Number.isFinite(value) && value >= 0.1 && value <= 10000 ? value : NaN;
}
