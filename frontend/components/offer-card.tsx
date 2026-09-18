import Link from "next/link";
import { duration, localizeTravelValue, locationName, modeContent, price, recommendationText, stopsLabel, time, toFa } from "@/lib/content";
import { supports } from "@/lib/capabilities";
import { OfferGroup } from "@/lib/types";
import { GuaranteeMark, TorobPay } from "./brand";
import { ClockIcon, ModeIcon } from "./icons";
import { ModeDetailTags } from "./mode-details";
import { OperatorLogo } from "./operator-logo";

export function OfferCard({ offer, featured = false, resultsUrl }: { offer: OfferGroup; featured?: boolean; resultsUrl: string }) {
  const content = modeContent[offer.mode];
  const guaranteed = supports(offer.recommended_capabilities, "torob_guarantee");
  const recommendationReasons = offer.attributes.stops === 0
    ? offer.recommendation_reasons
    : offer.recommendation_reasons.filter((reason) => reason !== "direct");
  const recommendedSeller = offer.seller_offers.find(
    (seller) => seller.id === offer.recommended_seller_offer_id,
  );
  const remainingSeats = recommendedSeller?.remaining_seats;
  const arrivalTime = time(offer.arrival_at);
  const travelDuration = duration(offer.duration_minutes);
  const stops = stopsLabel(offer.attributes.stops);
  const priceDiffersFromLowest = offer.recommended_price.amount !== offer.lowest_price.amount;
  const recommendation = recommendationText(
    offer.recommendation_summary,
    recommendationReasons,
  );
  const sellerUrl = `/offers/${encodeURIComponent(offer.id)}?return_to=${encodeURIComponent(resultsUrl)}`;
  return (
    <article className={`offer-card offer-card--${offer.mode} ${featured ? "featured" : ""}`}>
      {guaranteed && <div className="guarantee-ribbon"><GuaranteeMark compact /> تضمین ترب</div>}
      <div className="operator">
        <OperatorLogo
          mode={offer.mode}
          name={localizeTravelValue(offer.attributes.operator)}
          url={offer.attributes.operator_logo_url}
          alt={offer.attributes.operator_logo_alt}
          fallback={offer.attributes.operator_logo_fallback}
        />
        <strong>{localizeTravelValue(offer.attributes.operator)}</strong>
        {offer.attributes.service_number && <small>شماره {toFa(offer.attributes.service_number)}</small>}
      </div>
      <div className="journey">
        <div><b>{time(offer.departure_at)}</b><span>{locationName(offer.origin)}</span></div>
        <div className="journey-line">
          {travelDuration && <span><ClockIcon size={17} /> {travelDuration}</span>}
          <i className={`journey-mode journey-mode--${offer.mode}`} aria-hidden="true"><ModeIcon mode={offer.mode} size={22} /></i>
          {stops && <small>{stops}</small>}
        </div>
        <div><b>{arrivalTime}</b><span>{locationName(offer.destination)}</span></div>
      </div>
      <div className="offer-meta"><ModeDetailTags details={offer.mode_details} capabilities={offer.recommended_capabilities} />{remainingSeats != null && <em>{toFa(remainingSeats)} صندلی باقی مانده</em>}</div>
      {featured && recommendation && <div className="why"><strong>چرا این گزینه؟</strong><span>{recommendation}</span></div>}
      <div className="price-box">
        {supports(offer.recommended_capabilities, "torob_pay") && <TorobPay />}
        <div><b>{price(offer.recommended_price.amount)}</b> <span>تومان</span></div>
        <small className="party-price-note">قیمت کل برای {toFa(offer.passenger_count)} مسافر</small>
        <small>{priceDiffersFromLowest ? <>کمترین قیمت این سفر: {price(offer.lowest_price.amount)} تومان</> : <>کمترین قیمت در {toFa(offer.seller_count)} فروشگاه</>}</small>
        <Link href={sellerUrl} className="primary">مقایسه فروشنده‌ها</Link>
      </div>
    </article>
  );
}
