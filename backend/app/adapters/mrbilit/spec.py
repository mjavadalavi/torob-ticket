from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from app.domain.offer import Seller

MRBILIT_FLIGHT_AIRPORTS_URL = "https://flight.atighgasht.com/api/Airports"
MRBILIT_FLIGHT_SEARCH_URL = "https://flight.atighgasht.com/api/Flights"
MRBILIT_TRAIN_SEARCH_URL = "https://train.mrbilit.com/api/GetAvailable/v2"
MRBILIT_BUS_LOCATIONS_URL = (
    "https://bus.mrbilit.ir/api/CityList/GetBusCityList"
)
MRBILIT_BUS_SEARCH_URL = "https://bus.mrbilit.ir/api/GetBusServices"

MRBILIT_SELLER = Seller(
    id="mrbilit",
    name="مستربلیط",
    rating=None,
    review_count=None,
    logo_url="https://mrbilit.com/favicon.ico",
)


@dataclass(frozen=True, slots=True)
class MrBilitTrainStation:
    id: int
    slug: str
    name: str
    aliases: tuple[str, ...] = ()


# MrBilit serves its railway catalogue as a versioned web-client asset rather
# than a stable JSON endpoint. These national station identifiers and slugs were
# verified against that live asset on 2026-09-17. Unknown stations fail closed;
# they are never guessed from another provider's UI route.
MRBILIT_TRAIN_STATIONS: tuple[MrBilitTrainStation, ...] = (
    MrBilitTrainStation(1, "tehran", "تهران", ("THR",)),
    MrBilitTrainStation(191, "mashhad", "مشهد", ("MHD",)),
    MrBilitTrainStation(21, "isfahan", "اصفهان", ("IFN",)),
    MrBilitTrainStation(255, "shiraz", "شیراز", ("SYZ",)),
    MrBilitTrainStation(55, "tabriz", "تبریز", ("TBZ",)),
    MrBilitTrainStation(25, "ahvaz", "اهواز", ("AWZ",)),
    MrBilitTrainStation(451, "rasht", "رشت", ("RHD", "RASHT")),
    MrBilitTrainStation(167, "kerman", "کرمان", ("KER",)),
    MrBilitTrainStation(219, "yazd", "یزد", ("AZD",)),
    MrBilitTrainStation(37, "bandarabbas", "بندرعباس", ("BND", "بندر عباس")),
    MrBilitTrainStation(100, "sari", "ساری", ("SRY",)),
    MrBilitTrainStation(175, "gorgan", "گرگان", ("GBT",)),
    MrBilitTrainStation(195, "kermanshah", "کرمانشاه", ("KERSHAH",)),
    MrBilitTrainStation(448, "urmia", "ارومیه", ("OMH",)),
    MrBilitTrainStation(259, "zahedan", "زاهدان", ("ZAH",)),
    MrBilitTrainStation(161, "qom", "قم", ("QUM",)),
    MrBilitTrainStation(162, "kashan", "کاشان", ("KASHAN",)),
    MrBilitTrainStation(160, "qazvin", "قزوین", ("GZW",)),
    MrBilitTrainStation(600, "shahrekord", "شهرکرد", ("SHKORD",)),
    MrBilitTrainStation(165, "karaj", "کرج", ("KAR",)),
)


def _train_station_lookup() -> Mapping[str, MrBilitTrainStation]:
    result: dict[str, MrBilitTrainStation] = {}
    for station in MRBILIT_TRAIN_STATIONS:
        for key in (
            station.name,
            station.slug,
            str(station.id),
            *station.aliases,
        ):
            result[key.casefold()] = station
    return MappingProxyType(result)


MRBILIT_TRAIN_STATION_LOOKUP = _train_station_lookup()
