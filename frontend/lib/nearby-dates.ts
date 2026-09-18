import type { NearbyDatesResponse } from "./types";
import type { SearchJobRequest } from "./search-jobs";
import { apiErrorMessage, isNearbyDatesResponse } from "./wire";

export async function getNearbyDates(
  request: SearchJobRequest,
  signal?: AbortSignal,
): Promise<NearbyDatesResponse> {
  const response = await fetch("/api/travel/nearby-dates", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
    cache: "no-store",
    signal,
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok || !isNearbyDatesResponse(body)) {
    throw new Error(apiErrorMessage(body, "دریافت قیمت روزهای نزدیک ممکن نشد."));
  }
  return body;
}
