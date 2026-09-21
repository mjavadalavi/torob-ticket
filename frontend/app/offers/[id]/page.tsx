import Link from "next/link";
import { Header } from "@/components/header";
import { ClockIcon, HomeIcon, ModeIcon, ShieldIcon } from "@/components/icons";
import { ModeSummaryFeature } from "@/components/mode-details";
import { OperatorLogo } from "@/components/operator-logo";
import { SellerRow } from "@/components/seller-row";
import { getOffer } from "@/lib/api";
import { duration, localizeTravelValue, locationName, modeContent, stopsLabel, time, toFa, travelDate } from "@/lib/content";
import { supports } from "@/lib/capabilities";

function safeResultsUrl(value?: string) {
  if (!value) return null;
  try {
    const parsed = new URL(value, "http://torob-ticket.local");
    if (parsed.origin !== "http://torob-ticket.local" || parsed.pathname !== "/results") return null;
    return `${parsed.pathname}${parsed.search}`;
  } catch {
    return null;
  }
}

function refreshResultsUrl(value: string) {
  const parsed = new URL(value, "http://torob-ticket.local");
  parsed.searchParams.delete("search_id");
  return `${parsed.pathname}${parsed.search}`;
}

export default async function SellersPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ return_to?: string }>;
}) {
  const { id } = await params;
  const query = await searchParams;
  const offer = await getOffer(id);
  const content = modeContent[offer.mode];
  const operator = localizeTravelValue(offer.attributes.operator);
  const origin = locationName(offer.origin);
  const destination = locationName(offer.destination);
  const departureDate = travelDate(offer.departure_at);
  const fallbackResultsUrl = `/results?mode=${offer.mode}&origin=${encodeURIComponent(offer.origin)}&destination=${encodeURIComponent(offer.destination)}&date=${offer.departure_at.slice(0, 10)}`;
  const resultsUrl = safeResultsUrl(query.return_to) ?? fallbackResultsUrl;
  const freshResultsUrl = refreshResultsUrl(resultsUrl);
  const sellerStatus = offer.seller_offers.length === offer.seller_count
    ? `${toFa(offer.seller_count)} فروشنده با قیمت و موجودی زنده`
    : `${toFa(offer.seller_offers.length)} پیشنهاد از ${toFa(offer.seller_count)} فروشنده با قیمت و موجودی زنده`;
  const hasModeSummary = offer.mode_details.mode !== "flight"
    || offer.mode_details.baggage_allowance_kg != null;
  const travelDuration = duration(offer.duration_minutes);
  const stops = stopsLabel(offer.attributes.stops);
  return (
    <main className="seller-page">
      <Header compact />
      <div className="page-shell seller-shell">
        <div className="breadcrumb"><HomeIcon /><Link href={resultsUrl}>نتایج {content.label}</Link><span>/</span><span>{origin} به {destination}</span></div>
        <div className="seller-layout">
          <aside className="summary-card">
            <h2><span><ModeIcon mode={offer.mode} size={20} /></span> خلاصه انتخاب شما</h2>
            <div className="summary-route"><b>{origin}</b><span>←</span><b>{destination}</b></div>
            <p>{departureDate}</p><hr/>
            <h3>{operator}</h3>{offer.attributes.service_number && <p>شماره: {toFa(offer.attributes.service_number)}</p>}
            <div className="summary-times"><b>{time(offer.departure_at)}<small>{origin}</small></b><span>←</span><b>{time(offer.arrival_at)}<small>{destination}</small></b></div>
            <ul>
              {travelDuration && <li><ClockIcon /> {travelDuration}</li>}
              {stops && <li><ModeIcon mode={offer.mode} size={18} /> {stops}</li>}
              {hasModeSummary && <li><ModeSummaryFeature details={offer.mode_details} attributes={offer.attributes} /></li>}
            </ul>
            {supports(offer.recommended_capabilities, "torob_guarantee") && <section className="guarantee-box"><h3><ShieldIcon /> تضمین ترب</h3><p>این فروشنده برای همین گزینه نشان تضمین ترب را دارد.</p></section>}
          </aside>
          <section className="seller-main">
            <article className="journey-summary">
              <div className="journey-brand"><OperatorLogo mode={offer.mode} name={operator} url={offer.attributes.operator_logo_url} alt={offer.attributes.operator_logo_alt} fallback={offer.attributes.operator_logo_fallback} /><b>{operator}</b>{offer.attributes.service_number && <small>شماره {toFa(offer.attributes.service_number)}</small>}</div>
              <div className="large-route"><h1>{origin} <span>←</span> {destination}</h1><p>{departureDate}</p><div><b>{time(offer.departure_at)} {origin}</b><span>←</span><b>{time(offer.arrival_at)} {destination}</b></div></div>
            </article>
            <section className="seller-list-card">
              <header><h2>مقایسه فروشنده‌ها</h2><p className="seller-list-status">{sellerStatus}</p></header>
              <div className="seller-list">{offer.seller_offers.map((seller, index) => <SellerRow group={offer} offer={seller} index={index} refreshResultsUrl={freshResultsUrl} key={seller.id}/>)}</div>
              <p className="redirect-note">پیوند فروشنده صفحه جست‌وجوی همان مسیر را باز می‌کند؛ قیمت و موجودی را در سایت فروشنده دوباره بررسی کنید.</p>
            </section>
            <div className="seller-footer"><Link href={resultsUrl}>← بازگشت به نتایج</Link></div>
          </section>
        </div>
      </div>
    </main>
  );
}
