import { useState } from "react";
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

function ResultSkeleton() {
  return <div className="search-progress__skeleton" aria-hidden="true">
    {Array.from({ length: 2 }, (_, index) => <div className="search-progress__skeleton-card" key={index}>
      <span className="search-progress__skeleton-mode" />
      <span className="search-progress__skeleton-lines"><i /><i /></span>
      <span className="search-progress__skeleton-lines search-progress__skeleton-lines--short"><i /><i /></span>
      <span className="search-progress__skeleton-price"><i /><i /></span>
    </div>)}
  </div>;
}

function SearchArtwork({ mode, origin, destination }: { mode: TravelMode; origin: string; destination: string }) {
  const [readyImages, setReadyImages] = useState(0);
  const artworkReady = readyImages >= 2;
  const markImageReady = (image: HTMLImageElement) => {
    void image.decode().catch(() => undefined).finally(() => {
      setReadyImages((count) => Math.min(2, count + 1));
    });
  };

  return <div
    className={`search-progress__artwork search-progress__artwork--${mode} ${artworkReady ? "is-ready" : ""}`}
    data-artwork-ready={artworkReady ? "true" : "false"}
    aria-label={`${modeContent[mode].label} از ${origin} به ${destination}`}
  >
    <img
      className="search-progress__artwork-background"
      src="/images/loading/ticket-search-background-v2.png"
      alt=""
      width={1536}
      height={1024}
      loading="eager"
      fetchPriority="high"
      decoding="async"
      onLoad={(event) => markImageReady(event.currentTarget)}
      onError={(event) => markImageReady(event.currentTarget)}
    />
    <img
      className="search-progress__artwork-magnifier"
      src="/images/loading/ticket-search-magnifier-v2.png"
      alt=""
      width={1537}
      height={1023}
      loading="eager"
      fetchPriority="high"
      decoding="async"
      onLoad={(event) => markImageReady(event.currentTarget)}
      onError={(event) => markImageReady(event.currentTarget)}
    />
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
      <SearchArtwork mode={mode} origin={origin} destination={destination} />
      <div className="search-progress__route-summary" aria-label={`مسیر جست‌وجو از ${origin} به ${destination}`}>
        <span><small>مبدأ</small><strong>{origin}</strong></span>
        <b className="search-progress__route-separator" aria-hidden="true">←</b>
        <span><small>مقصد</small><strong>{destination}</strong></span>
      </div>
      <ol className="search-progress__steps" aria-label="مراحل جست‌وجو">
        <li className={isQueued ? "is-active" : "is-done"}><i>۱</i><span>ثبت جست‌وجو</span></li>
        <li className={isQueued ? "" : "is-active"}><i>۲</i><span>دریافت موجودی زنده</span></li>
        <li><i>۳</i><span>مقایسهٔ قیمت‌ها</span></li>
      </ol>
      {searchId && <code className="search-progress__tracking" title={searchId}>شناسهٔ پیگیری: {toFa(searchId.slice(-6))}</code>}
      <ResultSkeleton />
    </div>
  );
}
