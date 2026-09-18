"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Filters } from "@/components/filters";
import { Header } from "@/components/header";
import { OfferCard } from "@/components/offer-card";
import { SearchProgress } from "@/components/search-progress";
import { DatePicker, TripType } from "@/components/date-picker";
import { CityCombobox } from "@/components/city-combobox";
import { PassengerCounts, PassengerPicker, passengerTotal } from "@/components/passenger-picker";
import { ChevronIcon, FilterIcon, SearchIcon } from "@/components/icons";
import { defaultDepartureDate, locationName, modeContent, price, toFa } from "@/lib/content";
import { NearbyDateOption, SearchIntent, SearchJobState, SearchLegResponse, SearchResponse, TravelMode } from "@/lib/types";
import { supports } from "@/lib/capabilities";
import { getNearbyDates } from "@/lib/nearby-dates";
import {
  createSearchJob,
  getSearchJob,
  MINIMUM_SEARCH_JOB_POLL_DELAY_MS,
  SearchJobRequest,
} from "@/lib/search-jobs";

type SortOption = { value: SearchIntent; label: string; description: string };
type TripLeg = "outbound" | "return";
type SearchValues = {
  mode: TravelMode;
  origin: string;
  destination: string;
  travelDate: string;
  returnDate: string | null;
  passengers: PassengerCounts;
  exclusiveCompartment: boolean;
  intent: SearchIntent;
};

const sortOptions: SortOption[] = [
  { value: "best", label: "بهترین انتخاب", description: "رتبه‌بندی ترکیبی پیشنهادها بر اساس قیمت، زمان و امکانات" },
  { value: "cheapest", label: "ارزان‌ترین", description: "مرتب‌شده بر اساس کمترین قیمت" },
  { value: "fastest", label: "سریع‌ترین", description: "مرتب‌شده بر اساس کوتاه‌ترین زمان سفر" },
];

const modeLabel = (mode: TravelMode) => modeContent[mode].label;

function passengersForMode(mode: TravelMode, passengers: PassengerCounts): PassengerCounts {
  return mode === "flight"
    ? passengers
    : { adults: passengers.adults, children: 0, infants: 0 };
}

function shiftDate(value: string, days: number) {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function compactPersianDate(value: string) {
  return new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    day: "numeric",
    month: "long",
  }).format(new Date(`${value}T12:00:00Z`));
}

function persianWeekday(value: string) {
  return new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    weekday: "long",
  }).format(new Date(`${value}T12:00:00Z`));
}

function searchJobRequest(values: SearchValues): SearchJobRequest {
  return {
    mode: values.mode,
    origin: values.origin,
    destination: values.destination,
    departure_date: values.travelDate,
    return_date: values.returnDate,
    passengers: passengersForMode(values.mode, values.passengers),
    intent: values.intent,
    preferences: {
      mode: values.mode,
      ...(values.mode === "train"
        ? { exclusive_compartment: values.exclusiveCompartment }
        : {}),
    },
  };
}

function nearbyDateRequest(values: SearchValues, leg: TripLeg): SearchJobRequest {
  const isReturn = leg === "return" && values.returnDate != null;
  return {
    ...searchJobRequest(values),
    origin: isReturn ? values.destination : values.origin,
    destination: isReturn ? values.origin : values.destination,
    departure_date: isReturn ? values.returnDate! : values.travelDate,
    return_date: null,
  };
}

function pollDelay(signal: AbortSignal, delayMs: number) {
  return new Promise<void>((resolve, reject) => {
    const abort = () => {
      window.clearTimeout(timeout);
      reject(new DOMException("Search polling was cancelled.", "AbortError"));
    };
    const timeout = window.setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, delayMs);
    signal.addEventListener("abort", abort, { once: true });
  });
}

function searchErrorMessage(cause: unknown) {
  const message = cause instanceof Error ? cause.message : "";
  return /[\u0600-\u06ff]/.test(message)
    ? message
    : "ارتباط با سرویس فروش برقرار نشد. لطفاً دوباره تلاش کنید.";
}

function updateUrl(pathname: string, values: Record<string, string | null | undefined>) {
  const params = new URLSearchParams(window.location.search);
  Object.entries(values).forEach(([key, value]) => {
    if (value == null || value === "") params.delete(key);
    else params.set(key, value);
  });
  window.history.replaceState(null, "", `${pathname}?${params.toString()}`);
}

function resultsUrl({
  mode,
  intent,
  origin,
  destination,
  travelDate,
  returnDate,
  passengers,
  exclusiveCompartment,
}: SearchValues, searchId?: string) {
  const normalizedPassengers = passengersForMode(mode, passengers);
  const params = new URLSearchParams({
    mode,
    intent,
    date: travelDate,
    adults: String(normalizedPassengers.adults),
    passengers: String(passengerTotal(normalizedPassengers)),
  });
  if (mode === "flight") {
    params.set("children", String(normalizedPassengers.children));
    params.set("infants", String(normalizedPassengers.infants));
  }
  if (origin) params.set("origin", origin);
  if (destination) params.set("destination", destination);
  if (returnDate) params.set("return_date", returnDate);
  if (mode === "train") {
    params.set("exclusive_compartment", String(exclusiveCompartment));
  }
  if (searchId) params.set("search_id", searchId);
  return `/results?${params.toString()}`;
}

function ResultsToolbar({
  mode,
  origin,
  destination,
  travelDate,
  returnDate,
  passengers,
  exclusiveCompartment,
  onChange,
  onModeChange,
}: {
  mode: TravelMode;
  origin: string;
  destination: string;
  travelDate: string;
  returnDate: string | null;
  passengers: PassengerCounts;
  exclusiveCompartment: boolean;
  onChange: (values: Omit<SearchValues, "mode" | "intent">) => void;
  onModeChange: (mode: TravelMode) => void;
}) {
  const pathname = usePathname();
  const [draftError, setDraftError] = useState("");
  const [draft, setDraft] = useState({
    origin,
    destination,
    travelDate,
    returnDate,
    tripType: (returnDate ? "round-trip" : "one-way") as TripType,
    passengers,
    exclusiveCompartment,
  });

  useEffect(() => {
    setDraft({ origin, destination, travelDate, returnDate, tripType: returnDate ? "round-trip" : "one-way", passengers, exclusiveCompartment });
    setDraftError("");
  }, [origin, destination, travelDate, returnDate, passengers, exclusiveCompartment]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = {
      origin: draft.origin.trim(),
      destination: draft.destination.trim(),
      travelDate: draft.travelDate,
      returnDate: draft.tripType === "round-trip" ? draft.returnDate : null,
      passengers: passengersForMode(mode, draft.passengers),
      exclusiveCompartment: draft.exclusiveCompartment,
    };
    if (next.origin === next.destination) {
      setDraftError("مبدأ و مقصد نمی‌توانند یکسان باشند.");
      return;
    }
    if (draft.tripType === "round-trip" && (!next.returnDate || next.returnDate <= next.travelDate)) {
      setDraftError("تاریخ برگشت را بعد از تاریخ رفت انتخاب کنید.");
      return;
    }
    onChange(next);
    updateUrl(pathname, {
      origin: next.origin,
      destination: next.destination,
      date: next.travelDate,
      passengers: String(passengerTotal(next.passengers)),
      adults: String(next.passengers.adults),
      children: mode === "flight" ? String(next.passengers.children) : null,
      infants: mode === "flight" ? String(next.passengers.infants) : null,
      exclusive_compartment: mode === "train" ? String(next.exclusiveCompartment) : null,
      return_date: next.returnDate,
    });
    setDraftError("");
  }

  return (
    <form className="results-workspace__toolbar is-editing" aria-label="جزئیات جست‌وجو" onSubmit={submit}>
      <nav className="results-workspace__mode-tabs" aria-label="نوع بلیت">
        {(Object.keys(modeContent) as TravelMode[]).map((item) => (
          <button
            key={item}
            type="button"
            className={item === mode ? "is-active" : ""}
            aria-current={item === mode ? "page" : undefined}
            onClick={() => onModeChange(item)}
          >
            {modeContent[item].label}
          </button>
        ))}
      </nav>
      <div className="results-workspace__city-field">
        <CityCombobox label="مبدأ" value={draft.origin} mode={mode} excludedCity={draft.destination} onChange={(value) => setDraft((current) => ({ ...current, origin: value }))} />
      </div>
      <div className="results-workspace__route-arrow" aria-hidden="true">←</div>
      <div className="results-workspace__city-field">
        <CityCombobox label="مقصد" value={draft.destination} mode={mode} excludedCity={draft.origin} onChange={(value) => setDraft((current) => ({ ...current, destination: value }))} />
      </div>
      <div className="results-workspace__toolbar-field results-workspace__toolbar-date"><DatePicker tripType={draft.tripType} departureDate={draft.travelDate} returnDate={draft.returnDate} singleDateLabel="تاریخ سفر" onDepartureChange={(value) => setDraft((current) => ({ ...current, travelDate: value, returnDate: current.returnDate && current.returnDate > value ? current.returnDate : null }))} onReturnChange={(value) => setDraft((current) => ({ ...current, returnDate: value }))} /></div>
      <div className="results-workspace__passenger-field"><PassengerPicker value={draft.passengers} onChange={(value) => setDraft((current) => ({ ...current, passengers: value }))} allowMinorPassengers={mode === "flight"} /></div>
      <button className="primary results-workspace__search-button" type="submit"><SearchIcon /> جستجو</button>
      <div className="results-workspace__edit-extras">
        <div className="trip-type results-workspace__trip-type" aria-label="نوع سفر">
          <button type="button" className={draft.tripType === "one-way" ? "active" : ""} aria-pressed={draft.tripType === "one-way"} onClick={() => setDraft((current) => ({ ...current, tripType: "one-way", returnDate: null }))}>یک‌طرفه</button>
          <button type="button" className={draft.tripType === "round-trip" ? "active" : ""} aria-pressed={draft.tripType === "round-trip"} onClick={() => setDraft((current) => ({ ...current, tripType: "round-trip" }))}>رفت‌وبرگشت</button>
        </div>
        {mode === "train" && (
          <label>
            <input type="checkbox" checked={draft.exclusiveCompartment} onChange={(event) => setDraft((current) => ({ ...current, exclusiveCompartment: event.target.checked }))} />
            کوپه دربست
          </label>
        )}
        {draftError && <strong role="alert">{draftError}</strong>}
      </div>
    </form>
  );
}

function DateRail({
  leg,
  origin,
  destination,
  roundTrip,
  selectedDate,
  lowestPrice,
  nearbyDates,
  calendarLoading,
  calendarError,
  disabled,
  minimumDate,
  maximumDate,
  onSelect,
}: {
  leg: TripLeg;
  origin: string;
  destination: string;
  roundTrip: boolean;
  selectedDate: string;
  lowestPrice?: number;
  nearbyDates?: NearbyDateOption[];
  calendarLoading: boolean;
  calendarError?: string;
  disabled: boolean;
  minimumDate: string;
  maximumDate?: string;
  onSelect: (value: string) => void;
}) {
  const headingId = `nearby-dates-${leg}`;
  const dates = nearbyDates?.some((option) => option.date === selectedDate)
    ? nearbyDates.map((option) => option.date).filter((value) => value >= minimumDate && (maximumDate == null || value <= maximumDate))
    : (() => {
        let start = shiftDate(selectedDate, -2);
        if (start < minimumDate) start = minimumDate;
        if (maximumDate != null && shiftDate(start, 4) > maximumDate) {
          start = shiftDate(maximumDate, -4);
          if (start < minimumDate) start = minimumDate;
        }
        return Array.from({ length: 5 }, (_, index) => shiftDate(start, index))
          .filter((value) => maximumDate == null || value <= maximumDate);
      })();
  const dateLayoutKey = dates.join("|");
  const railRef = useRef<HTMLElement>(null);
  const activeDateRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const rail = railRef.current;
    const activeDate = activeDateRef.current;
    if (!rail || !activeDate || !window.matchMedia("(max-width: 760px)").matches) return;

    const railRect = rail.getBoundingClientRect();
    const activeRect = activeDate.getBoundingClientRect();
    const centeredLeft = rail.scrollLeft
      + activeRect.left
      - railRect.left
      - (rail.clientWidth - activeRect.width) / 2;
    rail.scrollTo({
      left: centeredLeft,
      // Nearby-date data can replace the five cards immediately after a date
      // click. An atomic recenter prevents two overlapping smooth scrolls from
      // leaving the active day visibly off-centre on narrow screens.
      behavior: "auto",
    });
  }, [dateLayoutKey, selectedDate]);

  return (
    <section className="results-workspace__nearby-dates" aria-labelledby={headingId}>
      <header className="results-workspace__nearby-heading">
        <div>
          <h2 id={headingId}>قیمت روزهای قبل و بعد{roundTrip ? `ِ ${leg === "outbound" ? "رفت" : "برگشت"}` : ""}</h2>
          <span>{locationName(origin)} به {locationName(destination)}؛ قیمت و موجودی واقعی دو روز اطراف را بررسی می‌کنیم.</span>
        </div>
        {calendarLoading && <em role="status">در حال دریافت قیمت روزهای نزدیک…</em>}
        {!calendarLoading && calendarError && <em className="is-error" role="status">{calendarError}</em>}
      </header>
      <nav ref={railRef} className="results-workspace__date-rail" aria-label="انتخاب تاریخ سفر">
      <button type="button" aria-label="روز قبل" disabled={disabled || shiftDate(selectedDate, -1) < minimumDate} onClick={() => onSelect(shiftDate(selectedDate, -1))}>›</button>
      {dates.map((value) => {
        const isOutsideRange = value < minimumDate || (maximumDate != null && value > maximumDate);
        const option = nearbyDates?.find((candidate) => candidate.date === value);
        const dayStatus = isOutsideRange
          ? value < defaultDepartureDate(0) ? "گذشته" : "غیرفعال"
          : option?.status === "available"
          ? option.minimum_price != null
            ? <>{price(option.minimum_price.amount)} <em>تومان</em></>
            : "موجود"
          : option?.status === "sold_out"
            ? "تکمیل ظرفیت"
            : option?.status === "availability_unknown"
              ? "در حال بررسی"
            : option?.status === "provider_unavailable"
              ? "قیمت در دسترس نیست"
              : option?.status === "past"
                ? "گذشته"
                : value === selectedDate && lowestPrice != null
                  ? <>{price(lowestPrice)} <em>تومان</em></>
                  : calendarLoading
                    ? "در حال بررسی"
                    : "در حال بررسی";
        return (
          <button ref={value === selectedDate ? activeDateRef : undefined} key={value} type="button" disabled={disabled || isOutsideRange} className={`results-workspace__date-button ${value === selectedDate ? "is-active" : ""} ${option ? `is-${option.status}` : ""}`} onClick={() => onSelect(value)} aria-current={value === selectedDate ? "date" : undefined}>
            <span>{persianWeekday(value)}</span><small>{compactPersianDate(value)}</small>
            <b>{dayStatus}</b>
          </button>
        );
      })}
      <button type="button" aria-label="روز بعد" disabled={disabled || (maximumDate != null && shiftDate(selectedDate, 1) > maximumDate)} onClick={() => onSelect(shiftDate(selectedDate, 1))}>‹</button>
      </nav>
      <small className="results-workspace__nearby-swipe">برای دیدن روزهای اطراف، کارت‌ها را به چپ یا راست بکشید.</small>
    </section>
  );
}

function SortMenu({ intent, fastestAvailable, searchReady, onChange }: { intent: SearchIntent; fastestAvailable: boolean; searchReady: boolean; onChange: (value: SearchIntent) => void }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const current = sortOptions.find((option) => option.value === intent) ?? sortOptions[0];

  function select(value: SearchIntent) {
    onChange(value);
    updateUrl(pathname, { intent: value });
    setOpen(false);
  }

  return (
    <div className="results-workspace__sort">
      <span>مرتب‌سازی:</span>
      <button className="results-workspace__sort-trigger" type="button" aria-haspopup="listbox" aria-expanded={open} disabled={!searchReady} onClick={() => setOpen((value) => !value)}>
        {current.label}<ChevronIcon size={17} />
      </button>
      {open && <div className="results-workspace__sort-menu" role="listbox" aria-label="روش مرتب‌سازی">
        {sortOptions.map((option) => {
          const disabled = !searchReady || (option.value === "fastest" && !fastestAvailable);
          return <button key={option.value} type="button" role="option" aria-selected={option.value === intent} disabled={disabled} onClick={() => select(option.value)}><b>{option.label}</b><small>{option.value === "fastest" && !fastestAvailable ? "برای نتایج فعلی در دسترس نیست" : option.description}</small></button>;
        })}
      </div>}
    </div>
  );
}

function IntentTabs({ intent, fastestAvailable, searchReady, onChange }: { intent: SearchIntent; fastestAvailable: boolean; searchReady: boolean; onChange: (value: SearchIntent) => void }) {
  const pathname = usePathname();
  return <div className="results-workspace__intent-tabs" role="tablist" aria-label="اولویت نمایش نتایج">
    {sortOptions.map((option) => {
      const disabled = !searchReady || (option.value === "fastest" && !fastestAvailable);
      return <button key={option.value} type="button" role="tab" aria-selected={option.value === intent} className={option.value === intent ? "is-active" : ""} disabled={disabled} onClick={() => { onChange(option.value); updateUrl(pathname, { intent: option.value }); }}><b>{option.label}</b><span>{option.value === "fastest" && !fastestAvailable ? "برای نتایج فعلی در دسترس نیست" : option.description}</span></button>;
    })}
  </div>;
}

export function ResultsWorkspace({
  mode,
  initialIntent,
  initialError,
  initialSearchId,
  initialOrigin = "",
  initialDestination = "",
  initialDate = defaultDepartureDate(),
  initialReturnDate = null,
  initialPassengers = { adults: 1, children: 0, infants: 0 },
  initialExclusiveCompartment = false,
}: {
  mode: TravelMode;
  initialIntent: SearchIntent;
  initialError?: string;
  initialSearchId?: string;
  initialOrigin?: string;
  initialDestination?: string;
  initialDate?: string;
  initialReturnDate?: string | null;
  initialPassengers?: PassengerCounts;
  initialExclusiveCompartment?: boolean;
}) {
  const [intent, setIntent] = useState(initialIntent);
  const [origin, setOrigin] = useState(initialOrigin);
  const [destination, setDestination] = useState(initialDestination);
  const [travelDate, setTravelDate] = useState(initialDate);
  const [returnDate, setReturnDate] = useState<string | null>(initialReturnDate);
  const [activeLeg, setActiveLeg] = useState<TripLeg>("outbound");
  const [passengers, setPassengers] = useState<PassengerCounts>(() => passengersForMode(mode, initialPassengers));
  const [exclusiveCompartment, setExclusiveCompartment] = useState(initialExclusiveCompartment);
  const [resultsData, setResultsData] = useState<SearchResponse | undefined>();
  const [isLoading, setIsLoading] = useState(false);
  const [searchError, setSearchError] = useState(initialError);
  const [activeSearchId, setActiveSearchId] = useState(initialSearchId);
  const [jobStatus, setJobStatus] = useState<Extract<SearchJobState, "queued" | "running">>("queued");
  const [nearbyDates, setNearbyDates] = useState<NearbyDateOption[] | undefined>();
  const [nearbyDatesLoading, setNearbyDatesLoading] = useState(false);
  const [nearbyDatesError, setNearbyDatesError] = useState<string | undefined>();
  const [selectedOperators, setSelectedOperators] = useState<string[]>([]);
  const [refundableOnly, setRefundableOnly] = useState(false);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const requestController = useRef<AbortController | null>(null);
  const nearbyDatesController = useRef<AbortController | null>(null);
  const activeResults: SearchLegResponse | undefined = activeLeg === "return"
    ? resultsData?.return_leg ?? undefined
    : resultsData;
  const offers = activeResults?.offers ?? [];
  const visibleOffers = useMemo(
    () => offers.filter((offer) =>
      (selectedOperators.length === 0 || selectedOperators.includes(offer.attributes.operator))
      && (!refundableOnly || supports(offer.available_capabilities, "refund_rules")),
    ),
    [offers, refundableOnly, selectedOperators],
  );
  const lowestPrice = offers.length
    ? Math.min(...offers.map((offer) => offer.lowest_price.amount))
    : undefined;
  const fastestAvailable = offers.some((offer) => offer.duration_minutes != null);
  const searchReady = origin.trim().length >= 2
    && destination.trim().length >= 2
    && origin.trim() !== destination.trim()
    && (returnDate == null || returnDate > travelDate);
  const intentExplanation = intent === "fastest" && !fastestAvailable
    ? "مرتب‌سازی سریع‌ترین برای نتایج فعلی در دسترس نیست."
    : sortOptions.find((option) => option.value === intent)?.description;
  const pathname = usePathname();
  const router = useRouter();
  const currentResultsUrl = resultsUrl({
    mode,
    intent,
    origin,
    destination,
    travelDate,
    returnDate,
    passengers,
    exclusiveCompartment,
  }, activeSearchId);

  useEffect(() => () => {
    requestController.current?.abort();
    nearbyDatesController.current?.abort();
  }, []);

  useEffect(() => {
    if (initialError) return;
    // Defer the initial requests by one task. In development React deliberately
    // replays mount effects once; cancelling the first scheduled task keeps that
    // replay from creating a second backend search job.
    const initialRequestTimer = window.setTimeout(() => {
      const values = currentSearch();
      void runSearch(values, initialSearchId);
      void loadNearbyDates(values);
    }, 0);
    return () => {
      window.clearTimeout(initialRequestTimer);
      requestController.current?.abort();
      nearbyDatesController.current?.abort();
    };
    // Search query props are the immutable starting point for this mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runSearch(values: SearchValues, existingSearchId?: string) {
    requestController.current?.abort();
    const controller = new AbortController();
    requestController.current = controller;
    setIsLoading(true);
    setJobStatus("queued");
    setSearchError(undefined);
    setResultsData(undefined);
    setSelectedOperators([]);
    setRefundableOnly(false);
    if (!existingSearchId) {
      setActiveSearchId(undefined);
      updateUrl(pathname, { search_id: null });
    }
    try {
      const accepted = existingSearchId
        ? {
            job: { search_id: existingSearchId, status: "queued" as const },
            retryAfterMs: MINIMUM_SEARCH_JOB_POLL_DELAY_MS,
          }
        : await createSearchJob(searchJobRequest(values), controller.signal);
      const searchId = accepted.job.search_id;
      if (controller.signal.aborted) return;
      setActiveSearchId(searchId);
      updateUrl(pathname, { search_id: searchId });

      await pollDelay(controller.signal, accepted.retryAfterMs);

      while (!controller.signal.aborted) {
        const { job, retryAfterMs } = await getSearchJob(searchId, controller.signal);
        if (job.status === "completed") {
          if (values.returnDate && !job.result?.return_leg) {
            throw new Error("نتیجهٔ مسیر برگشت از منابع فروش دریافت نشد. دوباره جست‌وجو کنید.");
          }
          setResultsData(job.result ?? undefined);
          return;
        }
        if (job.status === "failed") {
          throw new Error(job.error?.message || "Search job failed.");
        }
        setJobStatus(job.status);
        await pollDelay(controller.signal, retryAfterMs);
      }
    } catch (cause) {
      if (controller.signal.aborted) return;
      setSearchError(searchErrorMessage(cause));
    } finally {
      if (requestController.current === controller) {
        requestController.current = null;
        setIsLoading(false);
      }
    }
  }

  async function loadNearbyDates(values: SearchValues, leg: TripLeg = "outbound") {
    if (leg === "return" && !values.returnDate) return;
    nearbyDatesController.current?.abort();
    const controller = new AbortController();
    nearbyDatesController.current = controller;
    setNearbyDatesLoading(true);
    setNearbyDatesError(undefined);
    setNearbyDates(undefined);
    try {
      const response = await getNearbyDates(nearbyDateRequest(values, leg), controller.signal);
      if (!controller.signal.aborted) setNearbyDates(response.dates);
    } catch (cause) {
      if (controller.signal.aborted) return;
      setNearbyDates(undefined);
      setNearbyDatesError("قیمت روزهای اطراف فعلاً دریافت نشد؛ جست‌وجوی روز انتخابی همچنان ادامه دارد.");
    } finally {
      if (nearbyDatesController.current === controller) {
        nearbyDatesController.current = null;
        setNearbyDatesLoading(false);
      }
    }
  }

  function currentSearch(overrides: Partial<SearchValues> = {}): SearchValues {
    return {
      mode,
      intent,
      origin,
      destination,
      travelDate,
      returnDate,
      passengers,
      exclusiveCompartment,
      ...overrides,
    };
  }

  function selectDate(value: string) {
    if (!searchReady || value < defaultDepartureDate(0)) return;
    const values = activeLeg === "return"
      ? currentSearch({ returnDate: value })
      : currentSearch({ travelDate: value });
    if (values.returnDate != null && values.returnDate <= values.travelDate) return;
    if (activeLeg === "return") setReturnDate(value);
    else setTravelDate(value);
    updateUrl(window.location.pathname, activeLeg === "return"
      ? { return_date: value }
      : { date: value });
    void runSearch(values);
    void loadNearbyDates(values, activeLeg);
  }

  function updateSearch(values: Omit<SearchValues, "mode" | "intent">) {
    const normalizedPassengers = passengersForMode(mode, values.passengers);
    setOrigin(values.origin);
    setDestination(values.destination);
    setTravelDate(values.travelDate);
    setReturnDate(values.returnDate);
    setPassengers(normalizedPassengers);
    setExclusiveCompartment(values.exclusiveCompartment);
    if (!values.returnDate) setActiveLeg("outbound");
    const next = { ...values, passengers: normalizedPassengers, mode, intent };
    void runSearch(next);
    void loadNearbyDates(next, values.returnDate && activeLeg === "return" ? "return" : "outbound");
  }

  function switchMode(nextMode: TravelMode) {
    if (nextMode === mode) return;
    const nextPassengers = passengersForMode(nextMode, passengers);
    router.replace(resultsUrl({
      mode: nextMode,
      intent,
      origin,
      destination,
      travelDate,
      returnDate,
      passengers: nextPassengers,
      exclusiveCompartment: nextMode === "train" ? exclusiveCompartment : false,
    }), { scroll: false });
  }

  function updateIntent(value: SearchIntent) {
    if (!searchReady) return;
    setIntent(value);
    void runSearch(currentSearch({ intent: value }));
  }

  function toggleOperator(operator: string) {
    setSelectedOperators((current) =>
      current.includes(operator)
        ? current.filter((value) => value !== operator)
        : [...current, operator],
    );
  }

  function selectLeg(leg: TripLeg) {
    if (leg === activeLeg || (leg === "return" && !returnDate)) return;
    setActiveLeg(leg);
    setSelectedOperators([]);
    setRefundableOnly(false);
    setMobileFiltersOpen(false);
    void loadNearbyDates(currentSearch(), leg);
  }

  const activeFilterCount = selectedOperators.length + (refundableOnly ? 1 : 0);
  const activeOrigin = activeLeg === "outbound" ? origin : destination;
  const activeDestination = activeLeg === "outbound" ? destination : origin;
  const activeDate = activeLeg === "outbound" ? travelDate : returnDate ?? travelDate;
  const activeMinimumDate = activeLeg === "outbound"
    ? defaultDepartureDate(0)
    : shiftDate(travelDate, 1);
  const activeMaximumDate = activeLeg === "outbound" && returnDate
    ? shiftDate(returnDate, -1)
    : undefined;

  return <main className="results-page results-workspace">
    <Header />
    <div className="results-shell page-shell">
      <ResultsToolbar mode={mode} origin={origin} destination={destination} travelDate={travelDate} returnDate={returnDate} passengers={passengers} exclusiveCompartment={exclusiveCompartment} onChange={updateSearch} onModeChange={switchMode} />
      {returnDate && <div className="results-workspace__leg-tabs" role="tablist" aria-label="مسیرهای رفت و برگشت">
        <button id="outbound-leg-tab" type="button" role="tab" aria-selected={activeLeg === "outbound"} aria-controls="active-leg-results" className={activeLeg === "outbound" ? "is-active" : ""} onClick={() => selectLeg("outbound")}>
          <span>رفت</span><b>{locationName(origin)} به {locationName(destination)}</b><small>{compactPersianDate(travelDate)}{resultsData ? ` · ${toFa(resultsData.total)} گزینه` : ""}</small>
        </button>
        <button id="return-leg-tab" type="button" role="tab" aria-selected={activeLeg === "return"} aria-controls="active-leg-results" className={activeLeg === "return" ? "is-active" : ""} onClick={() => selectLeg("return")}>
          <span>برگشت</span><b>{locationName(destination)} به {locationName(origin)}</b><small>{compactPersianDate(returnDate)}{resultsData?.return_leg ? ` · ${toFa(resultsData.return_leg.total)} گزینه` : ""}</small>
        </button>
      </div>}
      <DateRail leg={activeLeg} origin={activeOrigin} destination={activeDestination} roundTrip={returnDate != null} selectedDate={activeDate} lowestPrice={lowestPrice} nearbyDates={nearbyDates} calendarLoading={nearbyDatesLoading} calendarError={nearbyDatesError} disabled={!searchReady || isLoading} minimumDate={activeMinimumDate} maximumDate={activeMaximumDate} onSelect={selectDate} />
      <div className="results-layout">
        <div className="results-workspace__mobile-controls" aria-label="کنترل نتایج">
          <button
            className="results-workspace__filter-toggle"
            type="button"
            aria-expanded={mobileFiltersOpen}
            aria-controls="results-filters-panel"
            onClick={() => setMobileFiltersOpen((value) => !value)}
          >
            <FilterIcon size={20} />
            <span>فیلترها</span>
            {activeFilterCount > 0 && <b aria-label={`${toFa(activeFilterCount)} فیلتر فعال`}>{toFa(activeFilterCount)}</b>}
          </button>
          <SortMenu intent={intent} fastestAvailable={fastestAvailable} searchReady={searchReady && !isLoading} onChange={updateIntent} />
        </div>
        <div
          id="results-filters-panel"
          className={`results-workspace__filters ${mobileFiltersOpen ? "is-open" : ""}`}
        >
          <Filters
            mode={mode}
            offers={offers}
            selectedOperators={selectedOperators}
            refundableOnly={refundableOnly}
            onToggleOperator={toggleOperator}
            onToggleRefundable={() => setRefundableOnly((value) => !value)}
            onClear={() => { setSelectedOperators([]); setRefundableOnly(false); }}
          />
        </div>
        <section id="active-leg-results" role={returnDate ? "tabpanel" : undefined} aria-labelledby={returnDate ? `${activeLeg}-leg-tab` : undefined} className={`offers-area ${isLoading ? "is-loading" : ""}`} aria-live="polite" aria-busy={isLoading}>
          <div className="offers-title">
            <h1>{!searchReady ? "مسیر سفر را تکمیل کنید" : isLoading ? <>در حال جست‌وجوی {modeLabel(mode)} از {locationName(activeOrigin)} به {locationName(activeDestination)}</> : <>{toFa(visibleOffers.length)} گزینه {modeLabel(mode)} برای {locationName(activeOrigin)} به {locationName(activeDestination)}</>}</h1>
            <div className="results-workspace__desktop-sort"><SortMenu intent={intent} fastestAvailable={fastestAvailable} searchReady={searchReady && !isLoading} onChange={updateIntent} /></div>
          </div>
          <IntentTabs intent={intent} fastestAvailable={fastestAvailable} searchReady={searchReady && !isLoading} onChange={updateIntent} />
          <p className="results-workspace__explanation"><SearchIcon size={17} /> {searchReady ? intentExplanation : "برای دریافت نتایج زنده، مبدأ و مقصد را ویرایش کنید."}</p>
          {isLoading && <SearchProgress mode={mode} status={jobStatus} searchId={activeSearchId} origin={locationName(activeOrigin)} destination={locationName(activeDestination)} />}
          {!isLoading && searchError && <div className="results-workspace__state is-error"><b>جست‌وجوی زنده انجام نشد</b><span>{searchError}</span>{searchReady && <button type="button" onClick={() => void runSearch(currentSearch())}>تلاش دوباره</button>}</div>}
          {!isLoading && !searchError && activeResults?.providers_succeeded === 0 && <div className="results-workspace__state is-error"><b>نتیجه‌ای برای مسیر {activeLeg === "outbound" ? "رفت" : "برگشت"} دریافت نشد</b><span>چند لحظه بعد دوباره جست‌وجو کنید یا تاریخ دیگری را انتخاب کنید.</span></div>}
          {!isLoading && !searchError && activeResults && activeResults.providers_succeeded > 0 && offers.length === 0 && <div className="results-workspace__state"><b>{returnDate ? <>برای این تاریخ بلیتی در مسیر {activeLeg === "outbound" ? "رفت" : "برگشت"} پیدا نشد</> : "برای این تاریخ بلیتی پیدا نشد"}</b><span>یک روز قبل یا بعد را انتخاب کنید.</span></div>}
          {!isLoading && !searchError && offers.length > 0 && visibleOffers.length === 0 && <div className="results-workspace__state"><b>گزینه‌ای با این فیلترها پیدا نشد</b><span>فیلترها را پاک کنید و دوباره ببینید.</span></div>}
          {!isLoading && visibleOffers.length > 0 && <div className="offers-list">{visibleOffers.map((offer) => <OfferCard key={offer.id} offer={offer} featured={offer.rank === 1} resultsUrl={currentResultsUrl} />)}</div>}
        </section>
      </div>
    </div>
  </main>;
}
