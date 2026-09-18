"use client";

import { useEffect, useState } from "react";
import { localizeTravelValue } from "@/lib/content";
import type { TravelMode } from "@/lib/types";

const LOGO_LOAD_TIMEOUT_MS = 6_000;
const TRUSTED_LOGO_HOSTS = new Set([
  "cdn.alibaba.ir",
  "fs.snapptrip.com",
  "store.snapptrip.com",
  "static.mrbilit.com",
  "train.mrbilit.com",
  "cdn.safar724.com",
  "safar724.com",
  "cdn-a.cdnfl2.ir",
  "mrbilit.com",
  "payaneha.com",
  "www.payaneha.com",
  "s3.ir-thr-at1.arvanstorage.ir",
  "booking.ir",
  "www.booking.ir",
  "avaair.ir",
  "flykish.com",
  "www.flykish.com",
]);

export function proxiedLogoUrl(value?: string | null): string | null {
  if (!value || value.length > 2_048) return null;

  try {
    const url = new URL(value);
    const hasTrustedOrigin = url.protocol === "https:"
      && !url.username
      && !url.password
      && (url.port === "" || url.port === "443")
      && TRUSTED_LOGO_HOSTS.has(url.hostname.toLowerCase());

    if (!hasTrustedOrigin) return null;
    url.hash = "";
    return `/api/logo?url=${encodeURIComponent(url.toString())}`;
  } catch {
    return null;
  }
}

export function TrustedLogo({
  className,
  name,
  url,
  alt,
  fallback,
}: {
  className: string;
  name: string;
  url?: string | null;
  alt?: string | null;
  fallback?: string | null;
}) {
  const src = proxiedLogoUrl(url);
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const [loadedSrc, setLoadedSrc] = useState<string | null>(null);
  const failed = src === null || failedSrc === src;
  const fallbackText = fallback?.trim() || name.trim().slice(0, 2) || "سفر";
  const rawAlt = alt?.trim();
  const accessibleAlt = rawAlt && !/(?:اعلام نشده|نامشخص)/u.test(rawAlt)
    ? rawAlt
    : `نشان شرکت ${name}`;

  useEffect(() => {
    if (src === null || loadedSrc === src || failedSrc === src) return;
    const timeout = window.setTimeout(() => setFailedSrc(src), LOGO_LOAD_TIMEOUT_MS);
    return () => window.clearTimeout(timeout);
  }, [failedSrc, loadedSrc, src]);

  return (
    <span className={className} data-logo-status={failed ? "fallback" : loadedSrc === src ? "loaded" : "loading"}>
      {!failed ? (
        // The same-origin route verifies the original HTTPS host and image type.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={accessibleAlt}
          loading="eager"
          decoding="async"
          onLoad={() => setLoadedSrc(src)}
          onError={() => setFailedSrc(src)}
        />
      ) : (
        <b aria-label={`${accessibleAlt} در دسترس نیست`}>{fallbackText}</b>
      )}
    </span>
  );
}

export function OperatorLogo({
  mode,
  name,
  url,
  alt,
  fallback,
}: {
  mode: TravelMode;
  name: string;
  url?: string | null;
  alt?: string | null;
  fallback?: string | null;
}) {
  const localizedFallback = localizeTravelValue(fallback, name);
  return (
    <TrustedLogo
      className={`operator-logo ${mode}`}
      name={name}
      url={url}
      alt={alt}
      fallback={localizedFallback === "—" ? name : localizedFallback}
    />
  );
}
