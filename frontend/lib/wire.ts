import {
  Capability,
  LocationSearchResponse,
  NearbyDatesResponse,
  OfferDetails,
  RedirectPreview,
  RefundRules,
  SearchJobAccepted,
  SearchJobStatusResponse,
  SearchResponse,
  Seat,
  SeatMap,
} from "./types";

const capabilities = new Set<Capability>([
  "refund_rules",
  "seat_selection",
  "vehicle_transport",
  "installment_payment",
  "torob_guarantee",
  "torob_pay",
]);

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function isCapability(value: unknown): value is Capability {
  return typeof value === "string" && capabilities.has(value as Capability);
}

export function apiErrorMessage(body: unknown, fallback: string): string {
  if (isRecord(body)) {
    const nestedMessage = isRecord(body.error) ? body.error.message : undefined;
    const detail = typeof body.detail === "string" ? body.detail : undefined;
    const message = typeof nestedMessage === "string" ? nestedMessage : detail ?? "";
    if (/[\u0600-\u06ff]/.test(message)) return message;
  }
  return fallback;
}

export function apiErrorCode(body: unknown): string | null {
  if (!isRecord(body) || !isRecord(body.error)) return null;
  return typeof body.error.code === "string" ? body.error.code : null;
}

export function isSearchResponse(value: unknown): value is SearchResponse {
  if (!(isRecord(value)
    && typeof value.search_id === "string"
    && (value.mode === "flight" || value.mode === "train" || value.mode === "bus")
    && (value.intent === "best" || value.intent === "cheapest" || value.intent === "fastest")
    && typeof value.total === "number"
    && typeof value.providers_queried === "number"
    && typeof value.providers_succeeded === "number"
    && Array.isArray(value.provider_failures)
    && Array.isArray(value.offers))) return false;

  if (value.return_leg == null) return true;
  return isRecord(value.return_leg)
    && typeof value.return_leg.total === "number"
    && typeof value.return_leg.providers_queried === "number"
    && typeof value.return_leg.providers_succeeded === "number"
    && Array.isArray(value.return_leg.provider_failures)
    && Array.isArray(value.return_leg.offers);
}

export function isNearbyDatesResponse(value: unknown): value is NearbyDatesResponse {
  if (
    !isRecord(value)
    || (value.mode !== "flight" && value.mode !== "train" && value.mode !== "bus")
    || typeof value.origin !== "string"
    || typeof value.destination !== "string"
    || typeof value.selected_date !== "string"
    || !Array.isArray(value.dates)
    || value.dates.length !== 5
  ) return false;

  return value.dates.every((option) => (
    isRecord(option)
    && typeof option.date === "string"
    && typeof option.offset_days === "number"
    && ["available", "sold_out", "availability_unknown", "provider_unavailable", "past"].includes(String(option.status))
    && (option.minimum_price === null || (
      isRecord(option.minimum_price)
      && typeof option.minimum_price.amount === "number"
      && option.minimum_price.currency === "IRT"
    ))
    && typeof option.offer_count === "number"
    && typeof option.providers_queried === "number"
    && typeof option.providers_succeeded === "number"
    && Array.isArray(option.provider_failures)
  ));
}

export function isSearchJobAccepted(value: unknown): value is SearchJobAccepted {
  return isRecord(value)
    && typeof value.search_id === "string"
    && /^src_[a-f0-9]{32}$/.test(value.search_id)
    && value.status === "queued";
}

export function isSearchJobStatusResponse(value: unknown): value is SearchJobStatusResponse {
  if (
    !isRecord(value)
    || typeof value.search_id !== "string"
    || !/^src_[a-f0-9]{32}$/.test(value.search_id)
    || !["queued", "running", "completed", "failed"].includes(String(value.status))
  ) return false;

  const result = value.result;
  const error = value.error;
  if (value.status === "completed") {
    return isSearchResponse(result)
      && result.search_id === value.search_id
      && error === null;
  }
  if (value.status === "failed") {
    return result === null
      && isRecord(error)
      && typeof error.code === "string"
      && typeof error.message === "string"
      && typeof error.retryable === "boolean";
  }
  return result === null && error === null;
}

export function isLocationSearchResponse(value: unknown): value is LocationSearchResponse {
  return isRecord(value)
    && (value.mode === "flight" || value.mode === "train" || value.mode === "bus")
    && typeof value.query === "string"
    && typeof value.total === "number"
    && typeof value.providers_queried === "number"
    && typeof value.providers_succeeded === "number"
    && Array.isArray(value.provider_failures)
    && Array.isArray(value.locations)
    && value.locations.every((location) => (
      isRecord(location)
      && typeof location.code === "string"
      && typeof location.name === "string"
      && location.mode === value.mode
      && Array.isArray(location.providers)
    ));
}

export function isOfferDetails(value: unknown): value is OfferDetails {
  if (!isRecord(value) || !isRecord(value.attributes) || !isRecord(value.mode_details)) return false;
  return typeof value.seller_offer_id === "string"
    && (value.mode === "flight" || value.mode === "train" || value.mode === "bus")
    && value.mode_details.mode === value.mode
    && Array.isArray(value.capabilities)
    && value.capabilities.every(isCapability)
    && typeof value.last_updated_at === "string";
}

export function isRefundRules(value: unknown): value is RefundRules {
  return isRecord(value)
    && typeof value.offer_id === "string"
    && typeof value.refundable === "boolean"
    && typeof value.summary === "string";
}

function isSeat(value: unknown): value is Seat {
  return isRecord(value)
    && typeof value.number === "string"
    && typeof value.available === "boolean"
    && typeof value.price_delta === "number"
    && (value.row == null || typeof value.row === "number")
    && (value.column == null || typeof value.column === "number");
}

export function isSeatMap(value: unknown): value is SeatMap {
  return isRecord(value)
    && typeof value.offer_id === "string"
    && Array.isArray(value.seats)
    && value.seats.every(isSeat);
}

export function isRedirectPreview(value: unknown): value is RedirectPreview {
  if (!isRecord(value)) return false;
  if (
    typeof value.offer_id !== "string"
    || typeof value.seller_offer_id !== "string"
    || typeof value.provider !== "string"
    || typeof value.seller_id !== "string"
    || typeof value.seller_name !== "string"
    || typeof value.url !== "string"
    || (value.target_kind !== "seller_search" && value.target_kind !== "offer_deep_link")
    || typeof value.price_recheck_required !== "boolean"
    || value.is_external !== true
    || value.notice_code !== "external_checkout"
  ) return false;

  try {
    return new URL(value.url).protocol === "https:";
  } catch {
    return false;
  }
}
