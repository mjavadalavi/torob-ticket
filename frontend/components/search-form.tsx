"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { defaultDepartureDate, modeContent } from "@/lib/content";
import { TravelMode } from "@/lib/types";
import { SearchIcon, SwapIcon } from "./icons";
import { DatePicker, TripType } from "./date-picker";
import { ModeTabs } from "./mode-tabs";
import { CityCombobox } from "./city-combobox";
import { PassengerCounts, PassengerPicker, passengerTotal } from "./passenger-picker";
import { createSearchJob } from "@/lib/search-jobs";

export function SearchForm({ mode }: { mode: TravelMode }) {
  const router = useRouter();
  const content = modeContent[mode];
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [departureDate, setDepartureDate] = useState(() => defaultDepartureDate(0));
  const [returnDate, setReturnDate] = useState<string | null>(null);
  const [tripType, setTripType] = useState<TripType>("one-way");
  const [compartment, setCompartment] = useState<"shared" | "private">("shared");
  const [passengers, setPassengers] = useState<PassengerCounts>({ adults: 1, children: 0, infants: 0 });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const submitController = useRef<AbortController | null>(null);
  const allowMinorPassengers = mode === "flight";

  const totalPassengers = allowMinorPassengers ? passengerTotal(passengers) : passengers.adults;

  useEffect(() => {
    if (allowMinorPassengers) return;
    setPassengers((current) => current.children === 0 && current.infants === 0
      ? current
      : { ...current, children: 0, infants: 0 });
  }, [allowMinorPassengers]);

  useEffect(() => () => submitController.current?.abort(), []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (submitting) return;
    if (tripType === "round-trip" && (!returnDate || returnDate <= departureDate)) {
      setSubmitError("تاریخ برگشت را بعد از تاریخ رفت انتخاب کنید.");
      return;
    }
    submitController.current?.abort();
    const controller = new AbortController();
    submitController.current = controller;
    setSubmitting(true);
    setSubmitError("");
    const query = new URLSearchParams({
      mode,
      origin: origin.trim(),
      destination: destination.trim(),
      date: departureDate,
      passengers: String(totalPassengers),
      adults: String(passengers.adults),
    });
    if (allowMinorPassengers) {
      query.set("children", String(passengers.children));
      query.set("infants", String(passengers.infants));
    }
    if (mode === "train") query.set("exclusive_compartment", String(compartment === "private"));
    if (tripType === "round-trip" && returnDate) query.set("return_date", returnDate);
    try {
      const { job } = await createSearchJob({
        mode,
        origin: origin.trim(),
        destination: destination.trim(),
        departure_date: departureDate,
        return_date: tripType === "round-trip" ? returnDate : null,
        passengers: allowMinorPassengers
          ? passengers
          : { adults: passengers.adults, children: 0, infants: 0 },
        intent: "best",
        preferences: {
          mode,
          ...(mode === "train" ? { exclusive_compartment: compartment === "private" } : {}),
        },
      }, controller.signal);
      query.set("search_id", job.search_id);
      router.push(`/results?${query.toString()}`);
    } catch (cause) {
      if (controller.signal.aborted) return;
      const message = cause instanceof Error ? cause.message : "";
      setSubmitError(/[\u0600-\u06ff]/.test(message)
        ? message
        : "شروع جست‌وجوی زنده ممکن نشد. دوباره تلاش کنید.");
    } finally {
      if (submitController.current === controller) {
        submitController.current = null;
        setSubmitting(false);
      }
    }
  }

  function swap() {
    setOrigin(destination);
    setDestination(origin);
  }

  function changeDepartureDate(value: string) {
    setDepartureDate(value);
    if (returnDate && returnDate <= value) setReturnDate(null);
  }

  function changeTripType(value: TripType) {
    setTripType(value);
    setSubmitError("");
    if (value === "one-way") setReturnDate(null);
  }

  return (
    <form className="ticket-search" onSubmit={submit}>
      <div className="search-head">
        <div className="search-head-slot train-slot" aria-hidden="true" />
        <ModeTabs mode={mode} />
        <div className="search-head-slot trip-slot">
          <div className="trip-type" aria-label="نوع سفر">
            <button type="button" className={tripType === "one-way" ? "active" : ""} aria-pressed={tripType === "one-way"} onClick={() => changeTripType("one-way")}>یک‌طرفه</button>
            <button type="button" className={tripType === "round-trip" ? "active" : ""} aria-pressed={tripType === "round-trip"} onClick={() => changeTripType("round-trip")}>رفت‌وبرگشت</button>
          </div>
          {mode === "train" && (
            <div className="train-compartment-picker">
              <label className="train-compartment-check">
                <span>کوپه دربست</span>
                <input
                  type="checkbox"
                  aria-label="کوپه دربست"
                  checked={compartment === "private"}
                  onChange={(event) => setCompartment(event.target.checked ? "private" : "shared")}
                />
              </label>
            </div>
          )}
        </div>
      </div>
      <div className="search-fields">
        <CityCombobox label="مبدا" value={origin} mode={mode} excludedCity={destination} onChange={setOrigin} />
        <button className="swap" type="button" aria-label="جابجایی مبدا و مقصد" onClick={swap}><SwapIcon /></button>
        <CityCombobox label="مقصد" value={destination} mode={mode} excludedCity={origin} onChange={setDestination} />
        <div className="field date"><span>{tripType === "round-trip" ? "تاریخ رفت و برگشت" : content.dateLabel}</span><DatePicker tripType={tripType} departureDate={departureDate} returnDate={returnDate} onDepartureChange={changeDepartureDate} onReturnChange={setReturnDate} /></div>
        <PassengerPicker value={passengers} onChange={setPassengers} allowMinorPassengers={allowMinorPassengers} />
        <button className="primary search-submit" disabled={submitting}><SearchIcon /> {submitting ? "در حال ثبت جست‌وجو…" : "جستجو"}</button>
      </div>
      {submitError && <p className="search-submit-error" role="alert">{submitError}</p>}
    </form>
  );
}
