"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  Capability,
  OfferDetails,
  OfferGroup,
  RedirectPreview,
  RefundRules,
  Seat,
  SeatMap,
  SellerOffer,
} from "@/lib/types";
import { localizeTravelValue, modeContent, price, sellerName, time, toFa } from "@/lib/content";
import { GuaranteeMark, TorobPay } from "./brand";
import { ExternalIcon, ShieldIcon } from "./icons";
import { capabilityLabels, supports } from "@/lib/capabilities";
import { TrustedLogo } from "./operator-logo";
import {
  apiErrorCode,
  apiErrorMessage,
  isOfferDetails,
  isRedirectPreview,
  isRefundRules,
  isSeatMap,
} from "@/lib/wire";

const highlightOrder: Capability[] = [
  "torob_pay",
  "installment_payment",
  "refund_rules",
  "seat_selection",
  "vehicle_transport",
  "torob_guarantee",
];

type PanelKind = "details" | "refund-rules" | "seat-map";

type PanelData =
  | { kind: "details"; value: OfferDetails }
  | { kind: "refund-rules"; value: RefundRules }
  | { kind: "seat-map"; value: SeatMap };

const panelTitles: Record<PanelKind, string> = {
  details: "جزئیات بلیت",
  "refund-rules": "قوانین استرداد",
  "seat-map": "نقشه صندلی",
};

function CapabilityFeature({ capability }: { capability?: Capability }) {
  if (!capability) return <div className="seller-feature is-empty" aria-hidden="true" />;
  if (capability === "torob_pay") return <div className="seller-feature"><TorobPay /> {capabilityLabels[capability]}</div>;
  return <div className="seller-feature"><ShieldIcon /> {capabilityLabels[capability]}</div>;
}

function textValue(value?: string | null): string | null {
  return value ? toFa(value) : null;
}

function localizedTextValue(value?: string | null): string | null {
  return value ? localizeTravelValue(value) : null;
}

function numberValue(value?: number | null, suffix = ""): string | null {
  return value == null ? null : `${toFa(value)}${suffix}`;
}

function booleanValue(value?: boolean | null): string | null {
  if (value == null) return null;
  return value ? "بله" : "خیر";
}

function fareTypeValue(value?: "system" | "charter" | null): string | null {
  if (value === "system") return "سیستمی";
  if (value === "charter") return "چارتری";
  return null;
}

function updatedAt(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return toFa(value);
  return new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Tehran",
  }).format(parsed);
}

function DetailGrid({ items }: { items: { label: string; value: ReactNode | null | undefined }[] }) {
  const visibleItems = items.filter(({ value }) => value != null && value !== "");
  if (visibleItems.length === 0) return null;
  return (
    <dl className="seller-panel__details">
      {visibleItems.map(({ label, value }, index) => (
        <div key={`${label}-${index}`}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function OfferDetailsPanel({ details }: { details: OfferDetails }) {
  const commonItems = [
    { label: "نوع سفر", value: modeContent[details.mode].label },
    { label: "اپراتور", value: textValue(details.attributes.operator) },
    { label: "شماره سرویس", value: textValue(details.attributes.service_number) },
    { label: "کلاس وسیله", value: localizedTextValue(details.attributes.vehicle_class) },
    {
      label: "نوع بلیت",
      value: details.mode === "flight"
        ? null
        : localizedTextValue(details.attributes.ticket_type),
    },
    { label: "تعداد توقف", value: numberValue(details.attributes.stops) },
    { label: "بار مجاز", value: numberValue(details.attributes.baggage_allowance_kg, " کیلوگرم") },
    { label: "صندلی باقی‌مانده", value: numberValue(details.remaining_seats) },
    {
      label: "امکان استرداد",
      value: details.refundable == null ? null : details.refundable ? "دارد" : "ندارد",
    },
    { label: "خلاصه استرداد", value: textValue(details.cancellation_summary) },
    { label: "آخرین به‌روزرسانی", value: updatedAt(details.last_updated_at) },
  ];

  const modeItems = details.mode_details.mode === "flight"
    ? [
        { label: "فرودگاه مبدأ", value: textValue(details.mode_details.origin_airport_code) },
        { label: "فرودگاه مقصد", value: textValue(details.mode_details.destination_airport_code) },
        { label: "شرکت هواپیمایی", value: textValue(details.mode_details.airline) },
        { label: "شماره پرواز", value: textValue(details.mode_details.flight_number) },
        { label: "نوع نرخ", value: fareTypeValue(details.mode_details.fare_type) },
        { label: "کلاس پروازی", value: localizedTextValue(details.mode_details.cabin_class) },
        { label: "بار مجاز پرواز", value: numberValue(details.mode_details.baggage_allowance_kg, " کیلوگرم") },
      ]
    : details.mode_details.mode === "train"
      ? [
          { label: "شرکت ریلی", value: textValue(details.mode_details.railway_company) },
          { label: "شماره قطار", value: textValue(details.mode_details.train_number) },
          { label: "کلاس قطار", value: localizedTextValue(details.mode_details.class_name) },
          { label: "ظرفیت کوپه", value: numberValue(details.mode_details.compartment_capacity, " نفر") },
          { label: "کوپه دربست", value: booleanValue(details.mode_details.private_compartment_available) },
          { label: "ویژه بانوان", value: booleanValue(details.mode_details.women_only_available) },
          { label: "حمل خودرو", value: booleanValue(details.mode_details.vehicle_transport_available) },
        ]
      : [
          { label: "ترمینال مبدأ", value: textValue(details.mode_details.origin_terminal) },
          { label: "ترمینال مقصد", value: textValue(details.mode_details.destination_terminal) },
          { label: "شرکت اتوبوس‌رانی", value: textValue(details.mode_details.company) },
          { label: "شماره سرویس اتوبوس", value: textValue(details.mode_details.service_number) },
          { label: "کلاس اتوبوس", value: localizedTextValue(details.mode_details.bus_class) },
          { label: "انتخاب صندلی", value: booleanValue(details.mode_details.seat_selection_available) },
          { label: "ظرفیت", value: numberValue(details.mode_details.capacity, " نفر") },
          { label: "شرایط لغو", value: textValue(details.mode_details.cancellation_policy) },
        ];

  return (
    <>
      <DetailGrid items={[...commonItems, ...modeItems]} />
      {details.capabilities.length > 0 && (
        <section className="seller-panel__capabilities" aria-label="خدمات تأییدشده فروشنده">
          <h3>خدمات تأییدشده فروشنده</h3>
          <div>
            {details.capabilities.map((capability) => (
              <span key={capability}>{capabilityLabels[capability]}</span>
            ))}
          </div>
        </section>
      )}
    </>
  );
}

function RefundRulesPanel({ rules }: { rules: RefundRules }) {
  return (
    <div className="seller-panel__refund">
      <strong className={rules.refundable ? "is-refundable" : "is-nonrefundable"}>
        {rules.refundable ? "این بلیت قابل استرداد است." : "این بلیت قابل استرداد نیست."}
      </strong>
      <p>{toFa(rules.summary)}</p>
    </div>
  );
}

function SeatMapPanel({ seatMap }: { seatMap: SeatMap }) {
  const availableSeats = seatMap.seats.filter((seat) => seat.available).length;
  if (seatMap.seats.length === 0) {
    return <p className="seller-panel__empty">فروشنده صندلی‌ای برای نمایش برنگرداند.</p>;
  }
  return (
    <div className="seller-seat-map">
      <p>
        <strong>{toFa(availableSeats)}</strong> صندلی از {toFa(seatMap.seats.length)} صندلی قابل انتخاب است.
      </p>
      <div className="seller-seat-map__grid" role="list" aria-label="صندلی‌های اعلام‌شده فروشنده">
        {seatMap.seats.map((seat, index) => (
          <div
            className={`seller-seat ${seat.available ? "is-available" : "is-unavailable"}`}
            key={`${seat.number}-${index}`}
            role="listitem"
          >
            <b>صندلی {toFa(seat.number)}</b>
            {seat.row != null && seat.column != null && (
              <span>ردیف {toFa(seat.row)}، ستون {toFa(seat.column)}</span>
            )}
            <span>{seat.available ? "قابل انتخاب" : "در دسترس نیست"}</span>
            <small>افزایش قیمت: {price(seat.price_delta)} تومان</small>
          </div>
        ))}
      </div>
    </div>
  );
}

export function SellerRow({
  group,
  offer,
  index,
  refreshResultsUrl,
}: {
  group: OfferGroup;
  offer: SellerOffer;
  index: number;
  refreshResultsUrl: string;
}) {
  const displaySellerName = sellerName(offer.seller.name);
  const [redirectOpen, setRedirectOpen] = useState(false);
  const [redirectPreview, setRedirectPreview] = useState<RedirectPreview | null>(null);
  const [redirectLoading, setRedirectLoading] = useState(false);
  const [redirectError, setRedirectError] = useState("");
  const [redirectExpired, setRedirectExpired] = useState(false);
  const [activePanel, setActivePanel] = useState<PanelKind | null>(null);
  const [panelData, setPanelData] = useState<PanelData | null>(null);
  const [panelError, setPanelError] = useState("");
  const [panelLoading, setPanelLoading] = useState(false);
  const requestController = useRef<AbortController | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const triggerButtonRef = useRef<HTMLButtonElement | null>(null);
  const highlights = highlightOrder.filter((capability) => supports(offer.capabilities, capability)).slice(0, 2);

  const closePanel = useCallback(() => {
    requestController.current?.abort();
    requestController.current = null;
    setActivePanel(null);
    setPanelData(null);
    setPanelError("");
    setPanelLoading(false);
    window.setTimeout(() => triggerButtonRef.current?.focus(), 0);
  }, []);

  const closeRedirect = useCallback(() => {
    requestController.current?.abort();
    requestController.current = null;
    setRedirectOpen(false);
    setRedirectPreview(null);
    setRedirectError("");
    setRedirectExpired(false);
    setRedirectLoading(false);
    window.setTimeout(() => triggerButtonRef.current?.focus(), 0);
  }, []);

  useEffect(() => () => requestController.current?.abort(), []);

  useEffect(() => {
    if (!activePanel && !redirectOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusTimer = window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (activePanel) closePanel();
        else closeRedirect();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [activePanel, closePanel, closeRedirect, redirectOpen]);

  async function openPanel(kind: PanelKind, trigger?: HTMLButtonElement) {
    if (trigger) triggerButtonRef.current = trigger;
    requestController.current?.abort();
    const controller = new AbortController();
    requestController.current = controller;
    setActivePanel(kind);
    setPanelData(null);
    setPanelError("");
    setPanelLoading(true);
    try {
      const response = await fetch(
        `/api/travel/offers/${encodeURIComponent(group.id)}/${kind}?seller_offer_id=${encodeURIComponent(offer.id)}`,
        { cache: "no-store", signal: controller.signal },
      );
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(apiErrorMessage(body, "دریافت اطلاعات از فروشنده ممکن نشد. لطفاً دوباره تلاش کنید."));

      let parsed: PanelData;
      if (kind === "details" && isOfferDetails(body)) parsed = { kind, value: body };
      else if (kind === "refund-rules" && isRefundRules(body)) parsed = { kind, value: body };
      else if (kind === "seat-map" && isSeatMap(body)) parsed = { kind, value: body };
      else throw new Error("پاسخ فروشنده قابل نمایش نیست. لطفاً دوباره تلاش کنید.");

      if (!controller.signal.aborted) setPanelData(parsed);
    } catch (cause) {
      if (controller.signal.aborted) return;
      const message = cause instanceof Error ? cause.message : "";
      setPanelError(/[؀-ۿ]/.test(message) ? message : apiErrorMessage(null, "دریافت اطلاعات از فروشنده ممکن نشد. لطفاً دوباره تلاش کنید."));
    } finally {
      if (requestController.current === controller) {
        requestController.current = null;
        setPanelLoading(false);
      }
    }
  }

  async function openRedirectPreview(trigger?: HTMLButtonElement) {
    if (trigger) triggerButtonRef.current = trigger;
    requestController.current?.abort();
    const controller = new AbortController();
    requestController.current = controller;
    setRedirectOpen(true);
    setRedirectPreview(null);
    setRedirectLoading(true);
    setRedirectError("");
    setRedirectExpired(false);
    try {
      const response = await fetch(
        `/api/travel/offers/${encodeURIComponent(group.id)}/redirect?seller_offer_id=${encodeURIComponent(offer.id)}`,
        { cache: "no-store", signal: controller.signal },
      );
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        const expired = response.status === 404 && apiErrorCode(body) === "resource_not_found";
        if (expired) setRedirectExpired(true);
        throw new Error(expired
          ? "قیمت و موجودی این نتیجه باید دوباره دریافت شود."
          : apiErrorMessage(body, "دریافت اطلاعات از فروشنده ممکن نشد. لطفاً دوباره تلاش کنید."));
      }
      if (
        !isRedirectPreview(body)
        || body.offer_id !== group.id
        || body.seller_offer_id !== offer.id
        || body.provider !== offer.provider
        || body.seller_id !== offer.seller.id
        || !body.is_external
      ) {
        throw new Error("اطلاعات انتقال فروشنده معتبر نیست. لطفاً دوباره تلاش کنید.");
      }
      if (!controller.signal.aborted) setRedirectPreview(body);
    } catch (cause) {
      if (controller.signal.aborted) return;
      const message = cause instanceof Error ? cause.message : "";
      setRedirectError(/[؀-ۿ]/.test(message) ? message : apiErrorMessage(null, "دریافت اطلاعات از فروشنده ممکن نشد. لطفاً دوباره تلاش کنید."));
    } finally {
      if (requestController.current === controller) {
        requestController.current = null;
        setRedirectLoading(false);
      }
    }
  }

  return (
    <article className={`seller-row ${index === 0 ? "best" : ""}`}>
      {index === 0 && supports(offer.capabilities, "torob_guarantee") && <span className="seller-guarantee"><GuaranteeMark compact /> تضمین ترب</span>}
      <TrustedLogo
        className={`seller-logo seller-${index}`}
        name={displaySellerName}
        url={offer.seller.logo_url}
        alt={offer.seller.logo_alt || `نشان فروشنده ${displaySellerName}`}
        fallback={offer.seller.logo_fallback || displaySellerName.slice(0, 1)}
      />
      <div className="seller-name"><b>{displaySellerName}</b>{offer.seller.rating != null && <span><i>★</i> {toFa(offer.seller.rating)} از ۵</span>}</div>
      <CapabilityFeature capability={highlights[0]} />
      <CapabilityFeature capability={highlights[1]} />
      <div className="seller-price"><div><b>{price(offer.price.amount)}</b><span>تومان</span></div><small>قیمت کل برای {toFa(group.passenger_count)} مسافر</small></div>
      <div className="seller-action"><button className="primary" type="button" aria-haspopup="dialog" onClick={(event) => void openRedirectPreview(event.currentTarget)}>مشاهده در فروشگاه <ExternalIcon /></button><small>آخرین دریافت: ساعت {time(offer.last_updated_at)}</small></div>
      <div className="seller-capability-actions" aria-label={`اطلاعات بلیت ${displaySellerName}`}>
        <button type="button" aria-haspopup="dialog" onClick={(event) => void openPanel("details", event.currentTarget)}>جزئیات</button>
        {supports(offer.capabilities, "refund_rules") && (
          <button type="button" aria-haspopup="dialog" onClick={(event) => void openPanel("refund-rules", event.currentTarget)}>قوانین استرداد</button>
        )}
        {supports(offer.capabilities, "seat_selection") && (
          <button type="button" aria-haspopup="dialog" onClick={(event) => void openPanel("seat-map", event.currentTarget)}>نقشه صندلی</button>
        )}
      </div>

      {activePanel && (
        <div className="seller-panel-backdrop" onMouseDown={(event) => event.target === event.currentTarget && closePanel()}>
          <section
            className="seller-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`seller-panel-title-${offer.id}`}
            aria-busy={panelLoading}
            dir="rtl"
          >
            <header>
              <div>
                <h2 id={`seller-panel-title-${offer.id}`}>{panelTitles[activePanel]}</h2>
                <p>{displaySellerName}</p>
              </div>
              <button ref={closeButtonRef} type="button" onClick={closePanel} aria-label="بستن پنجره">×</button>
            </header>
            <div className="seller-panel__body">
              {panelLoading && (
                <div className="seller-panel__state" role="status">
                  <span className="seller-panel__spinner" aria-hidden="true" />
                  <p>در حال دریافت اطلاعات از فروشنده...</p>
                </div>
              )}
              {!panelLoading && panelError && (
                <div className="seller-panel__state is-error" role="alert">
                  <p>{panelError}</p>
                  <button type="button" onClick={() => void openPanel(activePanel)}>تلاش دوباره</button>
                </div>
              )}
              {!panelLoading && !panelError && panelData?.kind === "details" && <OfferDetailsPanel details={panelData.value} />}
              {!panelLoading && !panelError && panelData?.kind === "refund-rules" && <RefundRulesPanel rules={panelData.value} />}
              {!panelLoading && !panelError && panelData?.kind === "seat-map" && <SeatMapPanel seatMap={panelData.value} />}
            </div>
          </section>
        </div>
      )}

      {redirectOpen && (
        <div className="seller-panel-backdrop" onMouseDown={(event) => event.target === event.currentTarget && closeRedirect()}>
          <section
            className="seller-panel seller-redirect-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`seller-redirect-title-${offer.id}`}
            aria-describedby={redirectPreview ? `seller-redirect-description-${offer.id}` : undefined}
            aria-busy={redirectLoading}
            dir="rtl"
          >
            <header>
              <div>
                <h2 id={`seller-redirect-title-${offer.id}`}>بررسی در سایت فروشنده</h2>
                <p>{displaySellerName}</p>
              </div>
              <button ref={closeButtonRef} type="button" onClick={closeRedirect} aria-label="بستن پنجره">×</button>
            </header>
            <div className="seller-panel__body">
              {redirectLoading && (
                <div className="seller-panel__state" role="status">
                  <span className="seller-panel__spinner" aria-hidden="true" />
                  <p>در حال بررسی پیوند فروشنده...</p>
                </div>
              )}
              {!redirectLoading && redirectError && (
                <div className="seller-panel__state is-error" role="alert">
                  <p>{redirectError}</p>
                  {redirectExpired
                    ? <button type="button" onClick={() => window.location.assign(refreshResultsUrl)}>جست‌وجوی دوباره</button>
                    : <button type="button" onClick={() => void openRedirectPreview()}>تلاش دوباره</button>}
                </div>
              )}
              {!redirectLoading && !redirectError && redirectPreview && (
                <div className="seller-redirect-confirmation">
                  <div className="seller-redirect-confirmation__icon" aria-hidden="true"><ExternalIcon /></div>
                  <div>
                    <h3>{sellerName(redirectPreview.seller_name)}</h3>
                    <p id={`seller-redirect-description-${offer.id}`}>
                      {redirectPreview.target_kind === "seller_search"
                        ? "این پیوند صفحه جست‌وجوی فروشنده را باز می‌کند. قیمت، موجودی و جزئیات بلیت را پیش از خرید دوباره بررسی کنید."
                        : redirectPreview.price_recheck_required
                          ? "این پیوند پیشنهاد فروشنده را باز می‌کند؛ قیمت و موجودی نهایی را پیش از خرید دوباره بررسی کنید."
                          : "این پیوند پیشنهاد انتخاب‌شده را در سایت فروشنده باز می‌کند."}
                    </p>
                    <p className="seller-redirect-confirmation__address" dir="ltr">{new URL(redirectPreview.url).hostname}</p>
                  </div>
                  <div className="seller-redirect-confirmation__actions">
                    <button type="button" onClick={closeRedirect}>انصراف</button>
                    <button className="primary" type="button" onClick={() => window.location.assign(redirectPreview.url)}>
                      مشاهده در سایت فروشنده <ExternalIcon />
                    </button>
                  </div>
                </div>
              )}
            </div>
          </section>
        </div>
      )}
    </article>
  );
}
