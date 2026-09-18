from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from app.domain.offer import Seller

ALIBABA_TRAIN_AVAILABILITY_URL = "https://ws.alibaba.ir/api/v2/train/available"
ALIBABA_FLIGHT_AVAILABILITY_URL = (
    "https://ws.alibaba.ir/api/v1/flights/domestic/available"
)
ALIBABA_BUS_AVAILABILITY_URL = "https://ws.alibaba.ir/api/v2/bus/available"
ALIBABA_BUS_STATIONS_URL = "https://ws.alibaba.ir/api/v1/bus/stations"
ALIBABA_BUS_SEATS_URL = "https://ws.alibaba.ir/api/v1/bus/available/seats"
ALIBABA_BUS_CANCELLATION_URL = (
    "https://ws.alibaba.ir/api/v1/bus/GetCancellationPolicy"
)
ALIBABA_SELLER = Seller(
    id="alibaba",
    name="علی‌بابا",
    rating=None,
    review_count=None,
    logo_url=(
        "https://cdn.alibaba.ir/h2/desktop/assets/images/"
        "shawl_logotype-d6b14ca0.svg"
    ),
)


@dataclass(frozen=True, slots=True)
class AlibabaTrainStation:
    id: int
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class AlibabaAirport:
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class AlibabaBusStation:
    domain_code: str
    route_code: str
    name: str


# Airports returned by Alibaba's verified domestic-airport endpoint:
# GET /api/v1/basic-info/airports/domestic/paginated
ALIBABA_DOMESTIC_AIRPORTS: Mapping[str, AlibabaAirport] = MappingProxyType(
    {
        "THR": AlibabaAirport(code="THR", name="تهران"),
        "تهران": AlibabaAirport(code="THR", name="تهران"),
        "MHD": AlibabaAirport(code="MHD", name="مشهد"),
        "مشهد": AlibabaAirport(code="MHD", name="مشهد"),
        "AWZ": AlibabaAirport(code="AWZ", name="اهواز"),
        "اهواز": AlibabaAirport(code="AWZ", name="اهواز"),
        "SYZ": AlibabaAirport(code="SYZ", name="شیراز"),
        "شیراز": AlibabaAirport(code="SYZ", name="شیراز"),
        "TBZ": AlibabaAirport(code="TBZ", name="تبریز"),
        "تبریز": AlibabaAirport(code="TBZ", name="تبریز"),
        "BND": AlibabaAirport(code="BND", name="بندرعباس"),
        "بندرعباس": AlibabaAirport(code="BND", name="بندرعباس"),
        "بندر عباس": AlibabaAirport(code="BND", name="بندرعباس"),
        "KIH": AlibabaAirport(code="KIH", name="کیش"),
        "کیش": AlibabaAirport(code="KIH", name="کیش"),
        "IFN": AlibabaAirport(code="IFN", name="اصفهان"),
        "اصفهان": AlibabaAirport(code="IFN", name="اصفهان"),
        "AZD": AlibabaAirport(code="AZD", name="یزد"),
        "یزد": AlibabaAirport(code="AZD", name="یزد"),
        "KER": AlibabaAirport(code="KER", name="کرمان"),
        "کرمان": AlibabaAirport(code="KER", name="کرمان"),
    }
)


# Verified warm cache captured from Alibaba's public station-search endpoint.
# Runtime lookup remains authoritative and expands this catalogue; these entries
# keep common Iranian cities searchable during a short provider outage.
ALIBABA_BUS_STATIONS: Mapping[str, AlibabaBusStation] = MappingProxyType(
    {
        "THR": AlibabaBusStation(
            domain_code="11320000", route_code="THR", name="تهران"
        ),
        "تهران": AlibabaBusStation(
            domain_code="11320000", route_code="THR", name="تهران"
        ),
        "MHD": AlibabaBusStation(
            domain_code="31310000", route_code="MHD", name="مشهد"
        ),
        "مشهد": AlibabaBusStation(
            domain_code="31310000", route_code="MHD", name="مشهد"
        ),
        "IFN": AlibabaBusStation(
            domain_code="21310000", route_code="IFN", name="اصفهان"
        ),
        "اصفهان": AlibabaBusStation(
            domain_code="21310000", route_code="IFN", name="اصفهان"
        ),
        "RHD": AlibabaBusStation(
            domain_code="54310000", route_code="RHD", name="رشت"
        ),
        "رشت": AlibabaBusStation(
            domain_code="54310000", route_code="RHD", name="رشت"
        ),
        "TBZ": AlibabaBusStation(
            domain_code="26310000", route_code="TBZ", name="تبریز"
        ),
        "تبریز": AlibabaBusStation(
            domain_code="26310000", route_code="TBZ", name="تبریز"
        ),
        "AZD": AlibabaBusStation(
            domain_code="93310000", route_code="AZD", name="یزد"
        ),
        "یزد": AlibabaBusStation(
            domain_code="93310000", route_code="AZD", name="یزد"
        ),
        "SYZ": AlibabaBusStation(
            domain_code="41310000", route_code="SYZ", name="شیراز"
        ),
        "شیراز": AlibabaBusStation(
            domain_code="41310000", route_code="SYZ", name="شیراز"
        ),
        "AWZ": AlibabaBusStation(
            domain_code="36310000", route_code="AWZ", name="اهواز"
        ),
        "اهواز": AlibabaBusStation(
            domain_code="36310000", route_code="AWZ", name="اهواز"
        ),
        "KER": AlibabaBusStation(
            domain_code="45310000", route_code="KER", name="کرمان"
        ),
        "کرمان": AlibabaBusStation(
            domain_code="45310000", route_code="KER", name="کرمان"
        ),
    }
)


# Only identifiers observed in Alibaba's public web search contract live here.
# Unknown values fail explicitly instead of guessing a provider-specific ID.
ALIBABA_TRAIN_STATIONS: Mapping[str, AlibabaTrainStation] = MappingProxyType(
    {
        "THR": AlibabaTrainStation(id=1, code="THR", name="تهران"),
        "تهران": AlibabaTrainStation(id=1, code="THR", name="تهران"),
        "MHD": AlibabaTrainStation(id=191, code="MHD", name="مشهد"),
        "مشهد": AlibabaTrainStation(id=191, code="MHD", name="مشهد"),
        "IFN": AlibabaTrainStation(id=21, code="IFN", name="اصفهان"),
        "اصفهان": AlibabaTrainStation(id=21, code="IFN", name="اصفهان"),
        "SYZ": AlibabaTrainStation(id=255, code="SYZ", name="شیراز"),
        "شیراز": AlibabaTrainStation(id=255, code="SYZ", name="شیراز"),
        "TBZ": AlibabaTrainStation(id=55, code="TBZ", name="تبریز"),
        "تبریز": AlibabaTrainStation(id=55, code="TBZ", name="تبریز"),
        "AWZ": AlibabaTrainStation(id=25, code="AWZ", name="اهواز"),
        "اهواز": AlibabaTrainStation(id=25, code="AWZ", name="اهواز"),
        "RASHT": AlibabaTrainStation(id=451, code="RASHT", name="رشت"),
        "رشت": AlibabaTrainStation(id=451, code="RASHT", name="رشت"),
        "KER": AlibabaTrainStation(id=167, code="KER", name="کرمان"),
        "کرمان": AlibabaTrainStation(id=167, code="KER", name="کرمان"),
        "AZD": AlibabaTrainStation(id=219, code="AZD", name="یزد"),
        "یزد": AlibabaTrainStation(id=219, code="AZD", name="یزد"),
        "BND": AlibabaTrainStation(id=37, code="BND", name="بندرعباس"),
        "بندرعباس": AlibabaTrainStation(id=37, code="BND", name="بندرعباس"),
        "SRY": AlibabaTrainStation(id=100, code="SRY", name="ساری"),
        "ساری": AlibabaTrainStation(id=100, code="SRY", name="ساری"),
        "GBT": AlibabaTrainStation(id=175, code="GBT", name="گرگان"),
        "گرگان": AlibabaTrainStation(id=175, code="GBT", name="گرگان"),
        "KERSHAH": AlibabaTrainStation(id=195, code="KERSHAH", name="کرمانشاه"),
        "کرمانشاه": AlibabaTrainStation(id=195, code="KERSHAH", name="کرمانشاه"),
        "OMH": AlibabaTrainStation(id=448, code="OMH", name="ارومیه"),
        "ارومیه": AlibabaTrainStation(id=448, code="OMH", name="ارومیه"),
        "ZAH": AlibabaTrainStation(id=259, code="ZAH", name="زاهدان"),
        "زاهدان": AlibabaTrainStation(id=259, code="ZAH", name="زاهدان"),
        "QUM": AlibabaTrainStation(id=161, code="QUM", name="قم"),
        "قم": AlibabaTrainStation(id=161, code="QUM", name="قم"),
        "KASHAN": AlibabaTrainStation(id=162, code="KASHAN", name="کاشان"),
        "کاشان": AlibabaTrainStation(id=162, code="KASHAN", name="کاشان"),
        "GZW": AlibabaTrainStation(id=160, code="GZW", name="قزوین"),
        "قزوین": AlibabaTrainStation(id=160, code="GZW", name="قزوین"),
        "SHKORD": AlibabaTrainStation(id=600, code="SHKORD", name="شهرکرد"),
        "شهرکرد": AlibabaTrainStation(id=600, code="SHKORD", name="شهرکرد"),
    }
)
