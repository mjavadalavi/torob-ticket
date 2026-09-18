"use client";

import { useId, useState } from "react";
import { toFa } from "@/lib/content";
import { ChevronIcon, UserIcon } from "./icons";

export type PassengerKey = "adults" | "children" | "infants";
export type PassengerCounts = Record<PassengerKey, number>;

const passengerLabels: Record<PassengerKey, { title: string; hint: string }> = {
  adults: { title: "بزرگسال", hint: "۱۲ سال به بالا" },
  children: { title: "کودک", hint: "۲ تا ۱۲ سال" },
  infants: { title: "نوزاد", hint: "زیر ۲ سال" },
};

export const passengerTotal = (value: PassengerCounts) =>
  value.adults + value.children + value.infants;

export function PassengerPicker({
  value,
  onChange,
  allowMinorPassengers = true,
}: {
  value: PassengerCounts;
  onChange: (value: PassengerCounts) => void;
  allowMinorPassengers?: boolean;
}) {
  const menuId = `${useId()}-passengers`;
  const [open, setOpen] = useState(false);
  const total = allowMinorPassengers ? passengerTotal(value) : value.adults;
  const visiblePassengerKeys: PassengerKey[] = allowMinorPassengers
    ? ["adults", "children", "infants"]
    : ["adults"];

  function change(key: PassengerKey, delta: number) {
    if (!allowMinorPassengers && key !== "adults") return;
    const minimum = key === "adults" ? 1 : 0;
    const next = Math.max(minimum, value[key] + delta);
    if (delta > 0 && total >= 9) return;
    if (key === "infants" && next > value.adults) return;
    if (key === "adults" && next < value.infants) return;
    onChange({
      ...value,
      [key]: next,
      ...(!allowMinorPassengers && { children: 0, infants: 0 }),
    });
  }

  return (
    <div className="passenger-picker">
      <span className="field-label">تعداد مسافر</span>
      <button
        type="button"
        className="passengers"
        role="combobox"
        aria-label={allowMinorPassengers ? "تعداد مسافر" : "تعداد مسافر، فقط بزرگسال"}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((current) => !current)}
      >
        <b><UserIcon /> {toFa(total)} {allowMinorPassengers ? "مسافر" : "بزرگسال"}</b><ChevronIcon />
      </button>
      {open && (
        <div id={menuId} className="passenger-menu" role="dialog" aria-label="انتخاب تعداد مسافر">
          <header><strong>مسافران</strong><button type="button" onClick={() => setOpen(false)}>بستن</button></header>
          {!allowMinorPassengers && (
            <p role="note">برای بلیت قطار و اتوبوس فقط مسافر بزرگسال قابل انتخاب است.</p>
          )}
          {visiblePassengerKeys.map((key) => (
            <div className="passenger-row" key={key}>
              <div><b>{passengerLabels[key].title}</b><small>{passengerLabels[key].hint}</small></div>
              <div className="counter" role="group" aria-label={`تعداد ${passengerLabels[key].title}`}>
                <button type="button" aria-label={`کم کردن ${passengerLabels[key].title}`} disabled={value[key] === (key === "adults" ? 1 : 0)} onClick={() => change(key, -1)}>−</button>
                <output aria-live="polite">{toFa(value[key])}</output>
                <button type="button" aria-label={`اضافه کردن ${passengerLabels[key].title}`} disabled={total >= 9 || (key === "infants" && value.infants >= value.adults)} onClick={() => change(key, 1)}>+</button>
              </div>
            </div>
          ))}
          <button className="passenger-done" type="button" onClick={() => setOpen(false)}>تأیید</button>
        </div>
      )}
    </div>
  );
}
