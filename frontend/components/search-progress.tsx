import { ModeIcon } from "@/components/icons";
import { modeContent, toFa } from "@/lib/content";
import type { SearchJobState, TravelMode } from "@/lib/types";

const runningCopy: Record<TravelMode, { title: string; detail: string }> = {
  flight: {
    title: "در حال بررسی پروازها",
    detail: "قیمت، ظرفیت، بار و شرایط پرواز فروشنده‌ها را مقایسه می‌کنیم.",
  },
  train: {
    title: "در حال بررسی قطارها",
    detail: "ظرفیت، نوع کوپه و امکانات قطارها را بررسی می‌کنیم.",
  },
  bus: {
    title: "در حال بررسی اتوبوس‌ها",
    detail: "سرویس‌ها، پایانه‌ها و صندلی‌های خالی را بررسی می‌کنیم.",
  },
};

function RunningVehicle({ mode }: { mode: TravelMode }) {
  const assets: Record<TravelMode, string> = {
    flight: "/images/loading/flight-vehicle-v3.png",
    train: "/images/loading/train-vehicle-v2.png",
    bus: "/images/loading/bus-vehicle-v2.png",
  };

  return <img
    className={`search-progress__vehicle-art search-progress__vehicle-art--${mode}`}
    src={assets[mode]}
    alt=""
    width={1774}
    height={887}
    loading="eager"
    decoding="async"
  />;
}

function RunningIllustration({ mode, origin, destination }: { mode: TravelMode; origin: string; destination: string }) {
  return <div className="search-progress__illustration search-progress__illustration--running" aria-label={`${modeContent[mode].label} از ${origin} به ${destination}`}>
    <div className="search-progress__landscape" aria-hidden="true"><i /><i /><i /><i /><i /></div>
    <span className="search-progress__route" aria-hidden="true" />
    <span className="search-progress__vehicle" aria-hidden="true"><RunningVehicle mode={mode} /></span>
    <span className="search-progress__stop is-start" aria-hidden="true" />
    <span className="search-progress__stop is-end" aria-hidden="true" />
    <strong className="search-progress__place is-start">{origin}</strong>
    <strong className="search-progress__place is-end">{destination}</strong>
  </div>;
}

function QueuedIllustration({ origin, destination }: { origin: string; destination: string }) {
  return <div className="search-progress__illustration search-progress__illustration--queued" aria-label={`جست‌وجوی ثبت‌شده از ${origin} به ${destination}`}>
    <img
      className="search-progress__queued-art"
      src="/images/loading/general-waiting-v1.png"
      alt=""
      width={960}
      height={640}
      loading="eager"
      decoding="async"
    />
    <div className="search-progress__queued-route" aria-hidden="true">
      <strong>{origin}</strong>
      <span><i /><i /><i /></span>
      <strong>{destination}</strong>
    </div>
  </div>;
}

function ResultSkeleton({ mode }: { mode: TravelMode }) {
  return <div className="search-progress__skeleton" aria-hidden="true">
    {Array.from({ length: 2 }, (_, index) => <div className="search-progress__skeleton-card" key={index}>
      <span className="search-progress__skeleton-mode"><ModeIcon mode={mode} size={25} /></span>
      <span className="search-progress__skeleton-lines"><i /><i /></span>
      <span className="search-progress__skeleton-lines search-progress__skeleton-lines--short"><i /><i /></span>
      <span className="search-progress__skeleton-price"><i /><i /></span>
    </div>)}
  </div>;
}

export function SearchProgress({
  mode,
  status,
  searchId,
  origin,
  destination,
}: {
  mode: TravelMode;
  status: Exclude<SearchJobState, "completed" | "failed">;
  searchId?: string;
  origin: string;
  destination: string;
}) {
  const isQueued = status === "queued";
  const content = runningCopy[mode];
  const statusText = isQueued
    ? `جست‌وجوی ${modeContent[mode].label} ثبت شد؛ آمادهٔ بررسی فروشنده‌ها`
    : `در حال دریافت موجودی زندهٔ ${modeContent[mode].label}`;

  return (
    <div
      className={`search-progress search-progress--${mode} search-progress--${status}`}
      data-status={status}
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <div className="search-progress__copy">
        <b>{content.title}</b>
        <span>{content.detail}</span>
        <small>{statusText}</small>
      </div>
      {isQueued
        ? <QueuedIllustration origin={origin} destination={destination} />
        : <RunningIllustration mode={mode} origin={origin} destination={destination} />}
      <ol className="search-progress__steps" aria-label="مراحل جست‌وجو">
        <li className={isQueued ? "is-active" : "is-done"}><i>۱</i><span>ثبت جست‌وجو</span></li>
        <li className={isQueued ? "" : "is-active"}><i>۲</i><span>دریافت موجودی زنده</span></li>
        <li><i>۳</i><span>مقایسهٔ قیمت‌ها</span></li>
      </ol>
      {searchId && <code className="search-progress__tracking" title={searchId}>شناسهٔ پیگیری: {toFa(searchId.slice(-6))}</code>}
      <ResultSkeleton mode={mode} />
    </div>
  );
}
