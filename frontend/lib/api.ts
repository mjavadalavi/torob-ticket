import { OfferGroup, SearchIntent, SearchResponse, TravelMode } from "./types";

const SERVER_API_URL =
  process.env.API_URL ??
  "http://localhost:8000/api/v1";

export interface SearchOptions {
  origin: string;
  destination: string;
  departureDate: string;
  returnDate?: string | null;
  passengerCounts: { adults: number; children: number; infants: number };
  exclusiveCompartment?: boolean;
}

export interface SearchResult {
  data?: SearchResponse;
  error?: string;
}

function searchErrorMessage(cause: unknown) {
  const message = cause instanceof Error ? cause.message : "";
  return /[\u0600-\u06ff]/.test(message)
    ? message
    : "ارتباط با سرویس فروش برقرار نشد. لطفاً دوباره تلاش کنید.";
}

export function searchPayload(
  mode: TravelMode,
  intent: SearchIntent,
  options: SearchOptions,
) {
  return {
    mode,
    origin: options.origin,
    destination: options.destination,
    departure_date: options.departureDate,
    return_date: options.returnDate ?? null,
    passengers: options.passengerCounts,
    intent,
    preferences: {
      mode,
      ...(mode === "train"
        ? { exclusive_compartment: options.exclusiveCompartment ?? false }
        : {}),
    },
  };
}

export async function searchOffers(
  mode: TravelMode,
  intent: SearchIntent,
  options: SearchOptions,
): Promise<SearchResult> {
  try {
    const response = await fetch(`${SERVER_API_URL}/search`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(searchPayload(mode, intent, options)),
      cache: "no-store",
      signal: AbortSignal.timeout(12_000),
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as
        | { error?: { message?: string } }
        | null;
      throw new Error(body?.error?.message || `API returned ${response.status}`);
    }
    return { data: (await response.json()) as SearchResponse };
  } catch (cause) {
    const message = searchErrorMessage(cause);
    return { error: message };
  }
}

export async function getOffer(id: string): Promise<OfferGroup> {
  const response = await fetch(`${SERVER_API_URL}/offers/${encodeURIComponent(id)}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(12_000),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { error?: { message?: string } }
      | null;
    throw new Error(body?.error?.message || "این نتیجه دیگر در دسترس نیست.");
  }
  return response.json() as Promise<OfferGroup>;
}
