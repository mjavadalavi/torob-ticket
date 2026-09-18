"use client";

import { useEffect, useMemo, useState } from "react";
import { defaultDepartureDate } from "@/lib/content";
import { CalendarIcon, ChevronIcon } from "./icons";

export type TripType = "one-way" | "round-trip";

type DatePickerProps = {
  tripType: TripType;
  departureDate: string;
  returnDate: string | null;
  singleDateLabel?: string;
  onDepartureChange: (value: string) => void;
  onReturnChange: (value: string | null) => void;
};

const weekDays = ["ش", "ی", "د", "س", "چ", "پ", "ج"];
const persianPartsFormatter = new Intl.DateTimeFormat("en-US-u-ca-persian-nu-latn", {
  calendar: "persian",
  timeZone: "UTC",
  year: "numeric",
  month: "numeric",
  day: "numeric",
});

function parseIso(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

function toIso(value: Date) {
  const year = value.getUTCFullYear();
  const month = String(value.getUTCMonth() + 1).padStart(2, "0");
  const day = String(value.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(value: Date, amount: number) {
  const next = new Date(value);
  next.setUTCDate(next.getUTCDate() + amount);
  return next;
}

function persianDateParts(value: Date) {
  const parts = persianPartsFormatter.formatToParts(value);
  const number = (type: Intl.DateTimeFormatPartTypes) => Number(parts.find((part) => part.type === type)?.value);
  return { year: number("year"), month: number("month"), day: number("day") };
}

function persianMonth(value: Date) {
  const current = persianDateParts(value);
  const first = addDays(value, 1 - current.day);
  let daysInMonth = 29;
  for (let offset = 29; offset <= 31; offset += 1) {
    const candidate = persianDateParts(addDays(first, offset));
    if (candidate.year !== current.year || candidate.month !== current.month) {
      daysInMonth = offset;
      break;
    }
  }
  return { first, daysInMonth };
}

function todayIso() {
  return defaultDepartureDate(0);
}

function displayDate(value: string) {
  return new Intl.DateTimeFormat("fa-IR", {
    calendar: "persian",
    timeZone: "UTC",
    weekday: "short",
    day: "numeric",
    month: "long",
  }).format(new Date(`${value}T00:00:00Z`));
}

function displayCompactDate(value: string) {
  return new Intl.DateTimeFormat("fa-IR", {
    calendar: "persian",
    timeZone: "UTC",
    day: "numeric",
    month: "short",
  }).format(new Date(`${value}T00:00:00Z`));
}

function displayMonth(value: Date) {
  return new Intl.DateTimeFormat("fa-IR", {
    calendar: "persian",
    timeZone: "UTC",
    month: "long",
    year: "numeric",
  }).format(value);
}

export function DatePicker({
  tripType,
  departureDate,
  returnDate,
  singleDateLabel = "رفت",
  onDepartureChange,
  onReturnChange,
}: DatePickerProps) {
  const [open, setOpen] = useState(false);
  const [month, setMonth] = useState(() => parseIso(departureDate));
  const [phase, setPhase] = useState<"departure" | "return">("departure");
  const today = todayIso();

  useEffect(() => {
    setPhase("departure");
  }, [tripType]);

  useEffect(() => {
    setMonth(parseIso(departureDate));
  }, [departureDate]);

  const cells = useMemo(() => {
    const { first, daysInMonth } = persianMonth(month);
    const offsetFromSaturday = (first.getUTCDay() + 1) % 7;
    return Array.from({ length: 42 }, (_, index) => {
      const day = index - offsetFromSaturday + 1;
      if (day < 1 || day > daysInMonth) return null;
      return toIso(addDays(first, day - 1));
    });
  }, [month]);

  function choose(value: string) {
    if (value < today) return;
    if (tripType === "one-way") {
      onDepartureChange(value);
      onReturnChange(null);
      setOpen(false);
      return;
    }
    if (phase === "departure") {
      onDepartureChange(value);
      onReturnChange(null);
      setPhase("return");
      return;
    }
    if (value <= departureDate) {
      onDepartureChange(value);
      onReturnChange(null);
      setPhase("return");
      return;
    }
    onReturnChange(value);
    setPhase("departure");
    setOpen(false);
  }

  function moveMonth(delta: number) {
    setMonth((current) => {
      const { first, daysInMonth } = persianMonth(current);
      return delta > 0 ? addDays(first, daysInMonth) : addDays(first, -1);
    });
  }

  return (
    <div className="date-picker-wrap">
      <button
        type="button"
        className="date-trigger"
        data-trip-type={tripType}
        aria-label={tripType === "round-trip" ? "انتخاب تاریخ رفت و برگشت" : "انتخاب تاریخ رفت"}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <CalendarIcon />
        <span className="date-trigger-content">
          <span className="date-trigger-segment">
            <small>{tripType === "round-trip" ? "رفت" : singleDateLabel}</small>
            <b>{tripType === "round-trip" ? displayCompactDate(departureDate) : displayDate(departureDate)}</b>
          </span>
          {tripType === "round-trip" && (
            <>
              <span className="date-range-separator" aria-hidden="true">←</span>
              <span className="date-trigger-segment return-segment">
                <small>برگشت</small>
                <b>{returnDate ? displayCompactDate(returnDate) : "انتخاب"}</b>
              </span>
            </>
          )}
        </span>
        <ChevronIcon />
      </button>
      {open && (
        <div className="date-popover" role="dialog" aria-label="انتخاب تاریخ">
          <header>
            <button type="button" aria-label="ماه قبل" onClick={() => moveMonth(-1)}>‹</button>
            <strong>{displayMonth(month)}</strong>
            <button type="button" aria-label="ماه بعد" onClick={() => moveMonth(1)}>›</button>
          </header>
          {tripType === "round-trip" && <div className="range-steps"><span className={phase === "departure" ? "active" : "done"}>۱. رفت</span><span className={phase === "return" ? "active" : ""}>۲. برگشت</span></div>}
          {tripType === "round-trip" && <p className="date-phase">{phase === "departure" ? "اول تاریخ رفت را انتخاب کنید" : "حالا یک تاریخ بعد از رفت را برای برگشت انتخاب کنید"}</p>}
          <p className="date-today">امروز: {displayDate(today)}</p>
          <div className="calendar-grid calendar-weekdays">{weekDays.map((day) => <span key={day}>{day}</span>)}</div>
          <div className="calendar-grid">
            {cells.map((value, index) => {
              if (!value) return <span className="calendar-empty" key={`empty-${index}`} />;
              const selected = value === departureDate || value === returnDate;
              const inRange = tripType === "round-trip" && returnDate != null && value > departureDate && value < returnDate;
              const isInvalidReturnDate = tripType === "round-trip"
                && phase === "return"
                && value <= departureDate;
              const isPastDate = value < today;
              const isToday = value === today;
              const disabled = isPastDate || isInvalidReturnDate;
              return (
                <button
                  type="button"
                  key={value}
                  data-date={value}
                  className={`${selected ? "selected" : ""} ${inRange ? "in-range" : ""} ${isPastDate ? "past" : ""} ${isToday ? "today" : ""}`}
                  disabled={disabled}
                  title={isPastDate
                    ? "تاریخ‌های قبل از امروز قابل انتخاب نیستند"
                    : isInvalidReturnDate
                      ? "تاریخ برگشت باید بعد از تاریخ رفت باشد"
                      : isToday
                        ? "امروز"
                        : undefined}
                  aria-current={isToday ? "date" : undefined}
                  aria-pressed={selected}
                  onClick={() => choose(value)}
                >
                  {new Intl.DateTimeFormat("fa-IR", { calendar: "persian", timeZone: "UTC", day: "numeric" }).format(new Date(`${value}T00:00:00Z`))}
                </button>
              );
            })}
          </div>
          <footer><button type="button" onClick={() => setOpen(false)}>بستن</button></footer>
        </div>
      )}
    </div>
  );
}
