from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from app.domain.capabilities import Capability, merge_capabilities
from app.domain.itinerary import OfferAttributes
from app.domain.offer import NormalizedOffer, OfferGroup
from app.services.journey_identity import canonical_arrival, canonical_text
from app.services.normalization import stable_group_id


class OfferGroupingService:
    def group(
        self,
        offers: Iterable[NormalizedOffer],
        *,
        passenger_count: int,
    ) -> list[OfferGroup]:
        buckets: dict[str, list[NormalizedOffer]] = defaultdict(list)
        for offer in offers:
            buckets[offer.journey_key].append(offer)

        groups: list[OfferGroup] = []
        for journey_key, seller_offers in buckets.items():
            # Source IDs are provider-internal proposal tokens. They are often
            # different for the same bus journey (for example, one token per
            # seat/availability snapshot), so they must not create duplicate
            # seller rows or duplicate journey cards. Keep genuinely different
            # fares/capabilities, while selecting the freshest token for an
            # otherwise identical provider offer so redirects still work.
            seller_offers = self._deduplicate_seller_offers(seller_offers)
            seller_offers.sort(
                key=lambda item: (
                    item.price.amount,
                    item.seller.rating is None,
                    -(item.seller.rating or 0),
                )
            )
            representative = seller_offers[0]
            # A provider can omit the operator logo on its cheapest row while
            # another seller for the same journey includes the verified asset.
            # Keep the cheapest fare as the representative, but do not throw
            # away usable brand metadata when building the journey card.
            attributes = self._merge_brand_metadata(
                representative.attributes,
                seller_offers,
            )
            groups.append(
                OfferGroup(
                    id=stable_group_id(journey_key),
                    mode=representative.mode,
                    passenger_count=passenger_count,
                    origin=representative.origin,
                    destination=representative.destination,
                    departure_at=representative.departure_at,
                    arrival_at=representative.arrival_at,
                    duration_minutes=representative.duration_minutes,
                    attributes=attributes,
                    mode_details=representative.mode_details,
                    available_capabilities=self._aggregate_capabilities(seller_offers),
                    lowest_price=representative.price,
                    seller_count=len(
                        {(offer.provider, offer.seller.id) for offer in seller_offers}
                    ),
                    seller_offers=seller_offers,
                    recommended_seller_offer_id=representative.id,
                    recommended_price=representative.price,
                    recommended_capabilities=representative.capabilities,
                )
            )
        return groups

    @staticmethod
    def _merge_brand_metadata(
        representative: OfferAttributes,
        offers: list[NormalizedOffer],
    ) -> OfferAttributes:
        if representative.operator_logo_url is not None:
            return representative
        for offer in offers:
            candidate = offer.attributes
            if candidate.operator_logo_url is None:
                continue
            return representative.model_copy(
                update={
                    "operator_logo_url": candidate.operator_logo_url,
                    "operator_logo_alt": candidate.operator_logo_alt,
                    "operator_logo_fallback": candidate.operator_logo_fallback,
                }
            )
        return representative

    @staticmethod
    def _deduplicate_seller_offers(
        offers: list[NormalizedOffer],
    ) -> list[NormalizedOffer]:
        """Collapse repeated provider proposals without hiding fare choices.

        A provider can return several opaque proposal IDs for one displayed
        journey. First keep the freshest record for an exact provider token;
        then show one row when the price, fare attributes, and capabilities are
        identical. A changed price, ticket type, vehicle class, or capability
        set remains a separate seller offer inside the same journey group.
        """

        latest_by_source: dict[tuple[str, str], NormalizedOffer] = {}
        for offer in offers:
            source_key = (offer.provider, offer.source_offer_id)
            current = latest_by_source.get(source_key)
            if current is None or offer.last_updated_at > current.last_updated_at:
                latest_by_source[source_key] = offer

        unique: dict[tuple[object, ...], NormalizedOffer] = {}
        for offer in latest_by_source.values():
            key = (
                offer.provider,
                offer.seller.id,
                offer.price.currency,
                offer.price.amount,
                canonical_arrival(offer.arrival_at),
                canonical_text(offer.attributes.ticket_type),
                canonical_text(offer.attributes.vehicle_class),
                tuple(sorted(capability.value for capability in offer.capabilities)),
                offer.refundable,
                canonical_text(offer.cancellation_summary),
            )
            current = unique.get(key)
            if current is None or offer.last_updated_at > current.last_updated_at:
                unique[key] = offer
        return list(unique.values())

    @staticmethod
    def _aggregate_capabilities(offers: list[NormalizedOffer]) -> list[Capability]:
        return merge_capabilities(*(offer.capabilities for offer in offers))
