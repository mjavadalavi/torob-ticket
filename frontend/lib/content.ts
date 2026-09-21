import type { RecommendationReason, TravelMode } from "./types";

export const modeContent: Record<TravelMode, {
  label: string; dateLabel: string;
}> = {
  flight: { label: "پرواز", dateLabel: "تاریخ رفت" },
  train: { label: "قطار", dateLabel: "تاریخ رفت" },
  bus: { label: "اتوبوس", dateLabel: "تاریخ حرکت" },
};

export const toFa = (value: string | number) => String(value).replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)]);
export const price = (amount: number) => toFa(new Intl.NumberFormat("en-US").format(amount));
export function defaultDepartureDate(daysFromToday = 7) {
  const value = new Date(Date.now() + daysFromToday * 86_400_000);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tehran",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}
export function time(iso?: string | null): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return toFa(new Intl.DateTimeFormat("fa-IR", { hour: "2-digit", minute: "2-digit", hour12: false }).format(date));
}

export function duration(minutes?: number | null): string | null {
  if (minutes == null || !Number.isFinite(minutes) || minutes <= 0) return null;
  return `${toFa(Math.floor(minutes / 60))} ساعت و ${toFa(minutes % 60)} دقیقه`;
}

export function stopsLabel(stops?: number | null): string | null {
  if (stops == null) return null;
  return stops === 0 ? "مستقیم" : `${toFa(stops)} توقف`;
}
export const travelDate = (iso: string) => new Intl.DateTimeFormat("fa-IR-u-ca-persian", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(new Date(iso));

export function locationName(value: unknown): string {
  const raw = String(value ?? "").trim();
  const labels: Record<string, string> = {
    THR: "تهران",
    MHD: "مشهد",
    Tehran: "تهران",
    Mashhad: "مشهد",
  };
  return labels[raw] ?? raw;
}

/** Convert provider enum values to copy that is safe to show in the Persian UI. */
export function localizeTravelValue(value: unknown, fallback = "—"): string {
  if (value == null || value === "") return fallback;
  const raw = String(value);
  if (/^(?:نام فارسی\s*)?(?:اعلام نشده|نامشخص)$/u.test(raw.trim())) return fallback;
  const normalized = raw.trim().toLowerCase().replace(/[\s-]+/g, "_");
  const labels: Record<string, string> = {
    system: "سیستمی",
    charter: "چارتری",
    economy: "اکونومی",
    business: "بیزنس",
    first_class: "فرست‌کلاس",
    standard: "استاندارد",
    vip: "وی‌آی‌پی",
    direct: "مستقیم",
    low_price: "قیمت مناسب",
    torob_guarantee: "تضمین ترب",
    torob_pay: "ترب‌پی",
    star_compartment_5: "کوپه ۵ ستاره",
    star_compartment_4: "کوپه ۴ ستاره",
    compartment_5: "کوپه ۵ ستاره",
    compartment_4: "کوپه ۴ ستاره",
    five_star: "۵ ستاره",
    four_star: "۴ ستاره",
    seat_selection: "انتخاب صندلی",
    refundable: "قابل استرداد",
    fadak: "فدک",
    raja: "رجا",
    bon_rail: "بن‌ریل",
    bonrail: "بن‌ریل",
    mahan_air: "ماهان",
    aseman_airlines: "آسمان",
    pars_air: "پارس‌ایر",
    sepehr_airline: "سپهران",
    sepehran_airlines: "سپهران",
    ماهان_ایر: "ماهان",
    iran_air: "ایران‌ایر",
    ata_air: "آتا",
    kish_air: "کیش‌ایر",
    qeshm_air: "قشم‌ایر",
    meraj_air: "معراج",
    sepehran_air: "سپهران",
    royal_safar: "رویال سفر",
    seir_o_safar: "سیر و سفر",
    seiro_safar: "سیر و سفر",
    iran_peyma: "ایران‌پیما",
    vip_25_seats: "وی‌آی‌پی ۲۵ نفره",
    vip_32_seats: "وی‌آی‌پی ۳۲ نفره",
    آسیا: "آسیا",
  };
  if (labels[normalized]) return labels[normalized];
  if (/^(?:star_)?compartment[_ -]?(?:5|five)$/.test(normalized) || /^(?:5|five)[_ -]star[_ -]compartment$/.test(normalized)) return "کوپه ۵ ستاره";
  if (/^(?:star_)?compartment[_ -]?(?:4|four)$/.test(normalized) || /^(?:4|four)[_ -](?:bed|star)[_ -]compartment$/.test(normalized)) return "کوپه ۴ تخته";
  if (/^star_compartment_\d+$/.test(normalized)) return `کوپه ${toFa(normalized.replace(/\D/g, ""))} ستاره`;
  if (/^compartment_\d+$/.test(normalized)) return `کوپه ${toFa(normalized.replace(/\D/g, ""))} تخته`;
  if (/^(?:5|five)[-_ ]star[-_ ]compartment$/.test(normalized)) return "کوپه ۵ ستاره";
  if (/^(?:4|four)[-_ ]bed[-_ ]compartment$/.test(normalized)) return "کوپه ۴ تخته";
  if (/(?:scania|volvo|maral|v(?:\s*\.\s*)?i(?:\s*\.\s*)?p|seats?)/i.test(raw)) {
    return toFa(raw)
      .replace(/scania/gi, "اسکانیا")
      .replace(/volvo/gi, "ولوو")
      .replace(/maral/gi, "مارال")
      .replace(/v(?:\s*\.\s*)?i(?:\s*\.\s*)?p\.?/gi, "وی‌آی‌پی")
      .replace(/\bseats?\b/gi, "صندلی")
      .replace(/([۰-۹])(?=(?:اسکانیا|ولوو|مارال|وی‌آی‌پی))/g, "$1 ")
      .replace(/(اسکانیا|ولوو|مارال|وی‌آی‌پی)(?=[۰-۹])/g, "$1 ")
      .replace(/([A-Za-z۰-۹])(?=وی‌آی‌پی)/g, "$1 ")
      .replace(/وی‌آی‌پی(?=[\u0600-\u06ff])/g, "وی‌آی‌پی ")
      .replace(/ي/g, "ی")
      .replace(/ك/g, "ک")
      .replace(/\s+/g, " ")
      .trim();
  }
  // Keep provider values intact; only normalize separators and Persian digits for display.
  if (/^[\u0600-\u06ff\d\s،‌-]+$/.test(raw)) {
    return toFa(raw)
      .replace(/ي/g, "ی")
      .replace(/ك/g, "ک")
      .replace(/([۰-۹])(?=[\u0600-\u06ff])/g, "$1 ")
      .replace(/([\u0600-\u06ff])(?=[۰-۹])/g, "$1 ");
  }
  // Never leak provider-side enum values into the Persian UI. Unknown machine
  // labels are optional metadata, so a neutral dash is clearer than an error-like
  // "announced/not announced" message.
  if (/^[a-z0-9][a-z0-9 _-]*$/i.test(raw)) return "—";
  return raw;
}

export function recommendationText(
  _summary?: string | null,
  reasons: RecommendationReason[] = [],
): string | null {
  const reasonLabels: Record<RecommendationReason, string> = {
    low_price: "قیمت مناسب",
    lowest_price: "کمترین قیمت نهایی",
    short_travel_time: "زمان سفر کوتاه",
    shortest_travel_time: "کوتاه‌ترین زمان سفر",
    direct: "مسیر مستقیم",
    high_seller_trust: "فروشنده‌های معتبر",
    torob_guarantee: "تضمین ترب",
    refund_rules: "قوانین استرداد شفاف",
  };
  const readableReasons = reasons.map((reason) => reasonLabels[reason]);
  return readableReasons.length > 0
    ? `رتبه‌بندی بر اساس ${readableReasons.join("، ")}.`
    : "رتبه‌بندی با داده‌های قابل‌مقایسهٔ موجود انجام شده است.";
}

export function sellerName(value: unknown): string {
  const normalized = String(value ?? "").trim().toLowerCase().replace(/[\s-]+/g, "_");
  const labels: Record<string, string> = {
    alibaba: "علی‌بابا",
    snapptrip: "اسنپ‌تریپ",
    mr_bilit: "مستر بلیط",
    mrbilit: "مستر بلیط",
    ghasedak24: "قاصدک۲۴",
    ghasedak_24: "قاصدک۲۴",
    flightio: "فلایتیو",
    trip: "تریپ",
    safarmarket: "سفرمارکت",
  };
  if (labels[normalized]) return labels[normalized];
  const raw = String(value ?? "").trim();
  return raw ? toFa(raw.replace(/[_-]+/g, " ")) : "فروشنده";
}
