/** Shared wire types for the provider-neutral Torob travel API. */

export type TravelMode = "flight" | "train" | "bus";
export type SearchIntent = "best" | "cheapest" | "fastest";
export type Currency = "IRT";
export type ProviderSupportStatus =
  | "registered"
  | "upstream_unavailable"
  | "access_restricted"
  | "requires_human_verification"
  | "referral_only"
  | "unverified";
export type Capability =
  | "refund_rules"
  | "seat_selection"
  | "vehicle_transport"
  | "installment_payment"
  | "torob_guarantee"
  | "torob_pay";

export interface PassengerCounts {
  adults: number;
  children: number;
  infants: number;
}

export interface GroundPassengerCounts {
  adults: number;
  children?: 0;
  infants?: 0;
}

export type FlightSearchPreferences = {
  mode: "flight";
  nonstop_only?: boolean;
  fare_type?: "system" | "charter" | null;
};

export type TrainSearchPreferences = {
  mode: "train";
  exclusive_compartment?: boolean;
  passenger_type?: "family" | "female" | "male";
  vehicle_transport?: boolean;
};

export type BusSearchPreferences = {
  mode: "bus";
  seat_selection_required?: boolean;
};

export type TravelSearchPreferences =
  | FlightSearchPreferences
  | TrainSearchPreferences
  | BusSearchPreferences;

interface SearchRequestBase {
  origin: string;
  destination: string;
  departure_date: string;
  /** When present, it must be later than departure_date. */
  return_date?: string | null;
  intent?: SearchIntent;
}

export type SearchRequest = SearchRequestBase & (
  | {
      mode: "flight";
      passengers?: PassengerCounts;
      preferences?: FlightSearchPreferences | null;
    }
  | {
      mode: "train";
      passengers?: GroundPassengerCounts;
      preferences?: TrainSearchPreferences | null;
    }
  | {
      mode: "bus";
      passengers?: GroundPassengerCounts;
      preferences?: BusSearchPreferences | null;
    }
);

export type LocationKind = "airport" | "railway_station" | "bus_station";

export interface TravelLocation {
  code: string;
  name: string;
  mode: TravelMode;
  kind: LocationKind;
  popular?: boolean;
  providers: string[];
}

export interface LocationProviderFailure {
  provider: string;
  message: string;
}

export interface LocationSearchResponse {
  mode: TravelMode;
  query: string;
  total: number;
  providers_queried: number;
  providers_succeeded: number;
  provider_failures?: LocationProviderFailure[];
  locations: TravelLocation[];
}

export interface ProviderSupportRecord {
  provider_id: string;
  name_fa: string;
  mode: TravelMode;
  status: ProviderSupportStatus;
  reason_fa: string;
  official_url: string;
  adapter_registered: boolean;
  verified_on: string;
}

export interface ProviderSupportResponse {
  mode: TravelMode;
  providers: ProviderSupportRecord[];
}

export interface Money { amount: number; currency: Currency }
export interface Seller {
  id: string;
  name: string;
  rating?: number | null;
  review_count?: number | null;
  logo_url?: string | null;
  logo_alt?: string | null;
  logo_fallback?: string | null;
}

export interface OfferAttributes {
  operator: string;
  operator_code?: string | null;
  operator_logo_url?: string | null;
  operator_logo_alt?: string | null;
  operator_logo_fallback?: string | null;
  service_number?: string | null;
  vehicle_class?: string | null;
  ticket_type?: string | null;
  stops?: number | null;
  baggage_allowance_kg?: number | null;
}

export interface FlightDetails {
  mode: "flight";
  origin_airport_code: string;
  destination_airport_code: string;
  airline: string;
  flight_number: string;
  fare_type: "system" | "charter";
  cabin_class: string;
  baggage_allowance_kg?: number | null;
}

export interface TrainDetails {
  mode: "train";
  railway_company: string;
  train_number: string;
  class_name: string;
  compartment_capacity?: number | null;
  private_compartment_available?: boolean | null;
  women_only_available?: boolean | null;
  vehicle_transport_available?: boolean | null;
}

export interface BusDetails {
  mode: "bus";
  origin_terminal: string;
  destination_terminal: string;
  company: string;
  service_number?: string | null;
  bus_class: string;
  seat_selection_available?: boolean | null;
  capacity?: number | null;
  cancellation_policy?: string | null;
}

export type TravelDetails = FlightDetails | TrainDetails | BusDetails;

export interface NormalizedOffer {
  id: string;
  provider: string;
  mode: TravelMode;
  seller: Seller;
  origin: string;
  destination: string;
  departure_at: string;
  arrival_at?: string | null;
  duration_minutes?: number | null;
  price: Money;
  attributes: OfferAttributes;
  mode_details: TravelDetails;
  capabilities: Capability[];
  remaining_seats?: number | null;
  cancellation_summary?: string | null;
  refundable?: boolean | null;
  last_updated_at: string;
}

export interface OfferDetails {
  /** Public opaque ID. Provider source tokens are never exposed. */
  seller_offer_id: string;
  mode: TravelMode;
  attributes: OfferAttributes;
  mode_details: TravelDetails;
  capabilities?: Capability[];
  remaining_seats?: number | null;
  cancellation_summary?: string | null;
  refundable?: boolean | null;
  last_updated_at: string;
}

export interface RefundRules {
  offer_id: string;
  refundable: boolean;
  summary: string;
}

export interface Seat {
  number: string;
  row?: number | null;
  column?: number | null;
  available: boolean;
  price_delta?: number;
}

export interface SeatMap {
  offer_id: string;
  seats: Seat[];
}

export type RecommendationReason =
  | "low_price"
  | "lowest_price"
  | "short_travel_time"
  | "shortest_travel_time"
  | "direct"
  | "high_seller_trust"
  | "torob_guarantee"
  | "refund_rules";

export interface OfferGroup {
  id: string;
  mode: TravelMode;
  passenger_count: number;
  origin: string;
  destination: string;
  departure_at: string;
  arrival_at?: string | null;
  duration_minutes?: number | null;
  attributes: OfferAttributes;
  mode_details: TravelDetails;
  available_capabilities: Capability[];
  lowest_price: Money;
  seller_count: number;
  seller_offers: NormalizedOffer[];
  /** Concrete seller offer selected by the active ranking policy. */
  recommended_seller_offer_id: string;
  recommended_price: Money;
  recommended_capabilities: Capability[];
  rank?: number | null;
  score?: number | null;
  recommendation_reasons: RecommendationReason[];
  recommendation_summary?: string | null;
}

export interface ProviderFailure { provider: string; message: string }

export interface SearchLegResponse {
  total: number;
  providers_queried: number;
  providers_succeeded: number;
  provider_failures: ProviderFailure[];
  offers: OfferGroup[];
}

export interface SearchResponse {
  search_id: string;
  mode: TravelMode;
  intent: SearchIntent;
  total: number;
  providers_queried: number;
  providers_succeeded: number;
  provider_failures: ProviderFailure[];
  offers: OfferGroup[];
  /** Present only for a round-trip search. */
  return_leg?: SearchLegResponse | null;
}

export type NearbyDateStatus =
  | "available"
  | "sold_out"
  | "availability_unknown"
  | "provider_unavailable"
  | "past";

export interface NearbyDateOption {
  date: string;
  offset_days: -2 | -1 | 0 | 1 | 2;
  status: NearbyDateStatus;
  minimum_price?: Money | null;
  offer_count?: number;
  providers_queried?: number;
  providers_succeeded?: number;
  provider_failures?: ProviderFailure[];
}

export interface NearbyDatesResponse {
  mode: TravelMode;
  origin: string;
  destination: string;
  selected_date: string;
  dates: NearbyDateOption[];
}

export type SearchJobState = "queued" | "running" | "completed" | "failed";

export interface SearchJobAccepted {
  search_id: string;
  status: "queued";
}

export interface SearchJobError {
  code: string;
  message: string;
  retryable: boolean;
}

export type SearchJobStatusResponse =
  | {
      search_id: string;
      status: "queued" | "running";
      result: null;
      error: null;
    }
  | {
      search_id: string;
      status: "completed";
      result: SearchResponse;
      error: null;
    }
  | {
      search_id: string;
      status: "failed";
      result: null;
      error: SearchJobError;
    };

export interface RedirectPreview {
  offer_id: string;
  seller_offer_id: string;
  provider: string;
  seller_id: string;
  seller_name: string;
  url: string;
  target_kind: "seller_search" | "offer_deep_link";
  price_recheck_required: boolean;
  is_external: boolean;
  notice_code: "external_checkout";
}

export interface ApiError { error: { code: string; message: string } }
export const API_PREFIX = "/api/v1" as const;
