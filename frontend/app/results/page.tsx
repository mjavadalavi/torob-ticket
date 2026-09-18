import { ResultsWorkspace } from "@/components/results-workspace";
import { defaultDepartureDate } from "@/lib/content";
import { SearchIntent, TravelMode } from "@/lib/types";

type ResultsSearchParams = {
  mode?: string;
  intent?: string;
  origin?: string;
  destination?: string;
  date?: string;
  return_date?: string;
  passengers?: string;
  adults?: string;
  children?: string;
  infants?: string;
  exclusive_compartment?: string;
  search_id?: string;
};

function validMode(value?: string): TravelMode {
  return value === "train" || value === "bus" ? value : "flight";
}

function validIntent(value?: string): SearchIntent {
  return value === "cheapest" || value === "fastest" ? value : "best";
}

function validIsoDate(value?: string): value is string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function integerParam(value: string | undefined, fallback: number) {
  if (value == null || value === "") return fallback;
  return /^\d+$/.test(value) ? Number(value) : Number.NaN;
}

export default async function ResultsPage({
  searchParams,
}: {
  searchParams: Promise<ResultsSearchParams>;
}) {
  const params = await searchParams;
  const mode = validMode(params.mode);
  const intent = validIntent(params.intent);
  const origin = params.origin?.trim() ?? "";
  const destination = params.destination?.trim() ?? "";
  const requestedDate = params.date;
  const dateIsValid = validIsoDate(requestedDate);
  const departureDate = dateIsValid ? requestedDate : defaultDepartureDate();
  const requestedReturnDate = params.return_date;
  const returnDateIsValid = requestedReturnDate == null || validIsoDate(requestedReturnDate);
  const returnDate = requestedReturnDate && returnDateIsValid ? requestedReturnDate : null;
  const adults = integerParam(params.adults ?? params.passengers, 1);
  const children = integerParam(params.children, 0);
  const infants = integerParam(params.infants, 0);
  const totalPassengers = adults + children + infants;
  const passengersAreValid = Number.isInteger(adults)
    && Number.isInteger(children)
    && Number.isInteger(infants)
    && adults >= 1
    && adults <= 9
    && children >= 0
    && children <= 8
    && infants >= 0
    && infants <= 8
    && infants <= adults
    && totalPassengers <= 9;

  let validationError: string | undefined;
  if (params.mode && params.mode !== "flight" && params.mode !== "train" && params.mode !== "bus") {
    validationError = "نوع سفر معتبر نیست.";
  } else if (origin.length < 2 || destination.length < 2) {
    validationError = "مبدأ و مقصد را از فهرست شهرهای قابل جست‌وجو انتخاب کنید.";
  } else if (origin === destination) {
    validationError = "مبدأ و مقصد نمی‌توانند یکسان باشند.";
  } else if (!dateIsValid || departureDate < defaultDepartureDate(0)) {
    validationError = "تاریخ سفر معتبر نیست یا در گذشته قرار دارد.";
  } else if (!returnDateIsValid || (returnDate != null && returnDate <= departureDate)) {
    validationError = "تاریخ برگشت باید معتبر و بعد از تاریخ رفت باشد.";
  } else if (!passengersAreValid) {
    validationError = "تعداد مسافران معتبر نیست.";
  }

  const initialSearchId = params.search_id && /^src_[a-f0-9]{32}$/.test(params.search_id)
    ? params.search_id
    : undefined;

  return (
    <ResultsWorkspace
      key={mode}
      mode={mode}
      initialIntent={intent}
      initialError={validationError}
      initialSearchId={initialSearchId}
      initialOrigin={origin}
      initialDestination={destination}
      initialDate={departureDate}
      initialReturnDate={returnDate}
      initialPassengers={passengersAreValid ? { adults, children, infants } : { adults: 1, children: 0, infants: 0 }}
      initialExclusiveCompartment={params.exclusive_compartment === "true"}
    />
  );
}
