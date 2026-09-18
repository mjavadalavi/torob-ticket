from __future__ import annotations

from datetime import date

import pytest
from app.adapters.payaneha import PayanehaBusAdapter
from app.adapters.payaneha.spec import (
    PAYANEHA_DESTINATIONS_URL,
    PAYANEHA_ORIGINS_URL,
    PAYANEHA_SEARCH_URL,
)
from app.core.errors import AdapterUnavailableError
from app.domain.travel import SearchRequest

RESULT_HTML = """
<section id="Services">
  <div id="service-divx" class="result_wrapper font13">
    <img src="../../../images/payanehlogo/ROYAL.png" alt="رويال سفر">
    <span class="co-brand">رویال سفر</span>
    <span class="co-name">رویال سفر تهران ترمینال بیهقی</span>
    <div class="travel-route"><strong>تهران بيهقي به اصفهان</strong>
      <span>مقصدنهایی : اصفهان کاوه</span></div>
    <a href="/busticket/terminal/tehran"><span>ترمینال بیهقی تهران</span></a>
    <div class="bus-type">درسا VIP + مانیتور + شارژر</div>
    <div class="date-move"><span>1405/07/01</span></div>
    <div class="time-move"><strong>00:30</strong></div>
    <span class="capacity">ظرفیت باقیمانده : 25 صندلی</span>
    <span class="price-pay"><span>7,120,000</span> ریال</span>
    <form action="/busticket/book"><input type="hidden" name="GetID" value="verified-service"></form>
  </div>
</section>
"""


class StubHttp:
    def __init__(self, *, malformed: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.malformed = malformed

    async def request_json(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if url == PAYANEHA_ORIGINS_URL:
            return [{"CityName": "تهران", "CityCode": "تهران"}]
        if url == PAYANEHA_DESTINATIONS_URL:
            return [{"CityName": "اصفهان", "CityCode": "اصفهان"}]
        raise AssertionError(url)

    async def request_text(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        assert url == PAYANEHA_SEARCH_URL
        return RESULT_HTML.replace("verified-service", "") if self.malformed else RESULT_HTML


def request(*, passengers: int = 1) -> SearchRequest:
    return SearchRequest(
        mode="bus",
        origin="تهران",
        destination="اصفهان",
        departure_date=date(2026, 9, 23),
        passengers={"adults": passengers},
    )


@pytest.mark.asyncio
async def test_maps_verified_payaneha_bus_html() -> None:
    http = StubHttp()
    adapter = PayanehaBusAdapter(http_client=http)

    offers = await adapter.search(request(passengers=2))

    assert len(offers) == 1
    offer = offers[0]
    assert offer.origin == "تهران"
    assert offer.destination == "اصفهان"
    assert offer.price.amount == 1_424_000
    assert offer.remaining_seats == 25
    assert offer.attributes.operator == "رویال سفر"
    assert offer.attributes.operator_logo_url is not None
    assert offer.mode_details.origin_terminal == "ترمینال بیهقی تهران"
    assert offer.mode_details.destination_terminal == "اصفهان کاوه"
    assert offer.mode_details.capacity is None
    assert offer.capabilities == []
    search_call = next(call for call in http.calls if call[0] == PAYANEHA_SEARCH_URL)
    assert search_call[1]["query"] == {
        "origin": "تهران",
        "dest": "اصفهان",
        "datemove": "1405/07/01",
    }
    redirect = adapter.build_redirect_url(offer.source_offer_id)
    assert redirect.startswith("https://www.payaneha.com/busticket/search/")
    assert "date=1405%2F07%2F01" in redirect


@pytest.mark.asyncio
async def test_payaneha_locations_use_verified_origin_catalogue() -> None:
    http = StubHttp()
    adapter = PayanehaBusAdapter(http_client=http)

    locations = await adapter.search_locations("تهران")
    repeated = await adapter.search_locations("تهران")

    assert locations == repeated
    assert locations[0].name == "تهران"
    assert locations[0].providers == ["payaneha"]
    assert [call[0] for call in http.calls] == [PAYANEHA_ORIGINS_URL]


@pytest.mark.asyncio
async def test_payaneha_reports_wholly_malformed_rows() -> None:
    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await PayanehaBusAdapter(http_client=StubHttp(malformed=True)).search(request())
