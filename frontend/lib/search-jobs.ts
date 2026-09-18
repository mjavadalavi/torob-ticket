import type {
  SearchIntent,
  SearchJobAccepted,
  SearchJobStatusResponse,
  TravelMode,
} from "./types";
import {
  apiErrorMessage,
  isSearchJobAccepted,
  isSearchJobStatusResponse,
} from "./wire";

export type SearchJobRequest = {
  mode: TravelMode;
  origin: string;
  destination: string;
  departure_date: string;
  return_date: string | null;
  passengers: { adults: number; children: number; infants: number };
  intent: SearchIntent;
  preferences: {
    mode: TravelMode;
    exclusive_compartment?: boolean;
  };
};

export type SearchJobResult<T> = {
  job: T;
  retryAfterMs: number;
};

export const MINIMUM_SEARCH_JOB_POLL_DELAY_MS = 1_000;

function retryAfterMs(response: Response) {
  const value = response.headers.get("retry-after")?.trim();
  if (!value) return MINIMUM_SEARCH_JOB_POLL_DELAY_MS;

  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) {
    return Math.max(MINIMUM_SEARCH_JOB_POLL_DELAY_MS, seconds * 1_000);
  }

  const retryAt = Date.parse(value);
  if (Number.isFinite(retryAt)) {
    return Math.max(MINIMUM_SEARCH_JOB_POLL_DELAY_MS, retryAt - Date.now());
  }
  return MINIMUM_SEARCH_JOB_POLL_DELAY_MS;
}

export async function createSearchJob(
  request: SearchJobRequest,
  signal?: AbortSignal,
): Promise<SearchJobResult<SearchJobAccepted>> {
  const response = await fetch("/api/travel/search-jobs", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
    cache: "no-store",
    signal,
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok || !isSearchJobAccepted(body)) {
    throw new Error(apiErrorMessage(body, "شروع جست‌وجوی زنده ممکن نشد."));
  }
  return { job: body, retryAfterMs: retryAfterMs(response) };
}

export async function getSearchJob(
  searchId: string,
  signal?: AbortSignal,
): Promise<SearchJobResult<SearchJobStatusResponse>> {
  const response = await fetch(`/api/travel/search-jobs/${encodeURIComponent(searchId)}`, {
    cache: "no-store",
    signal,
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok || !isSearchJobStatusResponse(body)) {
    throw new Error(apiErrorMessage(body, "پیگیری این جست‌وجو ممکن نشد."));
  }
  return { job: body, retryAfterMs: retryAfterMs(response) };
}
