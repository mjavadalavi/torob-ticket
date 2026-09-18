"use client";

import { KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";
import { LocationSearchResponse, TravelLocation, TravelMode } from "@/lib/types";
import { apiErrorMessage, isLocationSearchResponse } from "@/lib/wire";
import { ChevronIcon, PinIcon } from "./icons";

const scopeLabel: Record<TravelMode, string> = {
  flight: "فرودگاه‌های این شهر",
  train: "ایستگاه‌های راه‌آهن این شهر",
  bus: "پایانه‌های اتوبوس این شهر",
};

const LOCATION_CACHE_TTL_MS = 5 * 60 * 1000;
const locationCache = new Map<string, { expiresAt: number; response: LocationSearchResponse }>();
const locationRequests = new Map<string, Promise<LocationSearchResponse>>();

function locationCacheKey(mode: TravelMode, query: string) {
  return `${mode}:${query}`;
}

function cachedLocations(mode: TravelMode, query: string) {
  const key = locationCacheKey(mode, query);
  const cached = locationCache.get(key);
  if (!cached) return null;
  if (cached.expiresAt <= Date.now()) {
    locationCache.delete(key);
    return null;
  }
  return cached.response;
}

async function requestLocations(mode: TravelMode, query: string) {
  const cached = cachedLocations(mode, query);
  if (cached) return cached;

  const key = locationCacheKey(mode, query);
  const pending = locationRequests.get(key);
  if (pending) return pending;

  const params = new URLSearchParams({ mode, q: query, limit: "10" });
  const request = fetch(`/api/locations?${params.toString()}`, {
    cache: "no-store",
  })
    .then(async (response) => {
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok || !isLocationSearchResponse(body)) {
        throw new Error(apiErrorMessage(body, "دریافت فهرست شهرها ممکن نشد."));
      }
      locationCache.set(key, {
        expiresAt: Date.now() + LOCATION_CACHE_TTL_MS,
        response: body,
      });
      return body;
    })
    .finally(() => locationRequests.delete(key));

  locationRequests.set(key, request);
  return request;
}

export function CityCombobox({
  label,
  value,
  mode,
  excludedCity,
  onChange,
}: {
  label: string;
  value: string;
  mode: TravelMode;
  excludedCity?: string;
  onChange: (value: string) => void;
}) {
  const id = useId();
  const listId = `${id}-list`;
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [userTyped, setUserTyped] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [options, setOptions] = useState<TravelLocation[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [providerNotice, setProviderNotice] = useState<string | null>(null);
  const [validSelection, setValidSelection] = useState(() => value.trim().length > 0);
  const visibleOptions = useMemo(
    () => options.filter((location) => location.name !== excludedCity),
    [excludedCity, options],
  );

  useEffect(() => {
    const input = inputRef.current;
    if (!input) return;
    input.setCustomValidity(
      validSelection ? "" : "لطفاً یک شهر را از فهرست انتخاب کنید.",
    );
  }, [validSelection]);

  useEffect(() => {
    if (!open || !window.matchMedia("(max-width: 600px)").matches) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const timeout = window.setTimeout(async () => {
      setLoading(true);
      setLoadError(null);
      setProviderNotice(null);
      try {
        const query = userTyped ? value.trim() : "";
        const body = await requestLocations(mode, query);
        if (cancelled) return;
        setOptions(body.locations);
        const failureMessages = [...new Set(body.provider_failures.map((failure) => failure.message))];
        if (failureMessages.length > 0 && body.locations.length > 0) {
          setProviderNotice(failureMessages.join(" "));
        }
        if (body.locations.length === 0 && body.provider_failures.length > 0) {
          setLoadError(failureMessages.join(" ") || "دریافت فهرست شهرها ممکن نشد.");
        }
      } catch (cause) {
        if (cancelled) return;
        setOptions([]);
        const message = cause instanceof Error ? cause.message : "";
        setLoadError(/[\u0600-\u06ff]/.test(message) ? message : "دریافت فهرست شهرها ممکن نشد.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, userTyped ? 250 : 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [mode, open, userTyped, value]);

  function selectCity(location: TravelLocation) {
    onChange(location.name);
    setUserTyped(false);
    setValidSelection(true);
    setOpen(false);
    setActiveIndex(0);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((index) => Math.min(index + 1, Math.max(0, visibleOptions.length - 1)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(0, index - 1));
    } else if (event.key === "Enter" && open && visibleOptions[activeIndex]) {
      event.preventDefault();
      selectCity(visibleOptions[activeIndex]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="field city-field">
      <label className="city-field__label" htmlFor={id}>{label}</label>
      <div className={`city-combobox ${open ? "is-open" : ""}`}>
        <PinIcon />
        <input
          ref={inputRef}
          id={id}
          value={value}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-invalid={!validSelection}
          aria-controls={listId}
          aria-activedescendant={open && visibleOptions[activeIndex] ? `${id}-option-${activeIndex}` : undefined}
          autoComplete="off"
          required
          placeholder="نام شهر را بنویسید"
          onFocus={(event) => {
            setOpen(true);
            setUserTyped(false);
            setActiveIndex(0);
            event.currentTarget.select();
          }}
          onClick={() => {
            setOpen(true);
            setUserTyped(false);
            setActiveIndex(0);
          }}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          onChange={(event) => {
            onChange(event.target.value);
            setUserTyped(true);
            setValidSelection(false);
            setOpen(true);
            setActiveIndex(0);
          }}
          onKeyDown={handleKeyDown}
        />
        <ChevronIcon />
        {open && (
          <button
            className="city-combobox__close"
            type="button"
            aria-label="بستن فهرست شهرها"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => setOpen(false)}
          >
            ×
          </button>
        )}
        {open && (
          <div id={listId} className="city-combobox__menu" role="listbox" aria-label={`انتخاب ${label}`}>
            <div className="city-combobox__heading">{userTyped && value ? "نتیجه جست‌وجو" : "شهرهای قابل جست‌وجو"}</div>
            {loading ? (
              <div className="city-combobox__status" role="status">در حال دریافت شهرها…</div>
            ) : loadError ? (
              <div className="city-combobox__status is-error" role="alert">{loadError}</div>
            ) : visibleOptions.length > 0 ? visibleOptions.map((location, index) => (
              <button
                id={`${id}-option-${index}`}
                key={`${location.kind}-${location.code}-${location.name}`}
                type="button"
                role="option"
                aria-selected={location.name === value}
                className={index === activeIndex ? "is-active" : ""}
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => selectCity(location)}
              >
                <PinIcon size={18} />
                <span><b>{location.name}</b><small>{scopeLabel[mode]}</small></span>
              </button>
            )) : (
              <div className="city-combobox__empty">{value ? `شهری با نام «${value}» پیدا نشد.` : "شهری برای این نوع سفر برگردانده نشد."}</div>
            )}
            {!loading && providerNotice && <div className="city-combobox__provider-note" role="status">{providerNotice}</div>}
          </div>
        )}
      </div>
    </div>
  );
}
