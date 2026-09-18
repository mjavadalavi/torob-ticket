"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { SearchIcon } from "@/components/icons";

function recoveryResultsUrl(search: string) {
  const returnTo = new URLSearchParams(search).get("return_to");
  if (!returnTo) return "/";

  try {
    const parsed = new URL(returnTo, window.location.origin);
    if (parsed.origin !== window.location.origin || parsed.pathname !== "/results") return "/";
    parsed.searchParams.delete("search_id");
    return `${parsed.pathname}${parsed.search}`;
  } catch {
    return "/";
  }
}

export default function OfferError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const [recoveryUrl, setRecoveryUrl] = useState("/");

  useEffect(() => {
    console.error("Offer page could not be rendered", error.digest ?? error.name);
    setRecoveryUrl(recoveryResultsUrl(window.location.search));
  }, [error]);

  return (
    <main className="seller-page">
      <Header compact />
      <div className="page-shell offer-recovery" role="alert">
        <div className="offer-recovery__icon" aria-hidden="true">⌛</div>
        <h1>این نتیجه دیگر تازه نیست</h1>
        <p>
          قیمت و موجودی بلیت‌ها زنده است و ممکن است این نتیجه منقضی شده باشد.
          برای دیدن اطلاعات معتبر، دوباره جست‌وجو کنید.
        </p>
        <div className="offer-recovery__actions">
          <Link className="primary" href={recoveryUrl}><SearchIcon size={20} /> جست‌وجوی دوباره</Link>
          <button type="button" onClick={reset}>تلاش برای بازیابی نتیجه</button>
        </div>
      </div>
    </main>
  );
}
