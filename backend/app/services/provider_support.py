from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import Field, HttpUrl

from app.domain.travel import ApiModel, TravelMode
from app.ports.travel_adapter import AdapterFactory


class ProviderSupportStatus(StrEnum):
    """Integration eligibility, not the provider's current uptime."""

    REGISTERED = "registered"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    ACCESS_RESTRICTED = "access_restricted"
    REQUIRES_HUMAN_VERIFICATION = "requires_human_verification"
    REFERRAL_ONLY = "referral_only"
    UNVERIFIED = "unverified"


class ProviderSupportRecord(ApiModel):
    provider_id: str = Field(min_length=2, max_length=40)
    name_fa: str = Field(min_length=2, max_length=80)
    mode: TravelMode
    status: ProviderSupportStatus
    reason_fa: str = Field(min_length=2, max_length=300)
    official_url: HttpUrl
    adapter_registered: bool
    verified_on: date


class ProviderSupportResponse(ApiModel):
    mode: TravelMode
    providers: list[ProviderSupportRecord]


_VERIFIED_ON = date(2026, 9, 18)
_REGISTERED_REASON = (
    "قرارداد جست‌وجوی عمومی این منبع بررسی شده و آداپتر آن فعال است."
)


def _record(
    *,
    provider_id: str,
    name_fa: str,
    mode: TravelMode,
    official_url: str,
    status: ProviderSupportStatus = ProviderSupportStatus.REGISTERED,
    reason_fa: str = _REGISTERED_REASON,
) -> ProviderSupportRecord:
    return ProviderSupportRecord(
        provider_id=provider_id,
        name_fa=name_fa,
        mode=mode,
        status=status,
        reason_fa=reason_fa,
        official_url=official_url,
        adapter_registered=status is ProviderSupportStatus.REGISTERED,
        verified_on=_VERIFIED_ON,
    )


PROVIDER_SUPPORT_CATALOG: tuple[ProviderSupportRecord, ...] = (
    # Train providers supplied for verification.
    _record(
        provider_id="flytoday",
        name_fa="فلای‌تودی",
        mode=TravelMode.TRAIN,
        official_url="https://www.flytodayir.com/train",
        status=ProviderSupportStatus.UPSTREAM_UNAVAILABLE,
        reason_fa="سرویس قطار در بررسی زنده، پاسخ صریحِ در دسترس نبودن سرویس بالادستی داد.",
    ),
    _record(
        provider_id="mrbilit",
        name_fa="مستربلیط",
        mode=TravelMode.TRAIN,
        official_url="https://mrbilit.com/train-ticket",
    ),
    _record(
        provider_id="alibaba",
        name_fa="علی‌بابا",
        mode=TravelMode.TRAIN,
        official_url="https://www.alibaba.ir/train-ticket",
    ),
    _record(
        provider_id="raja",
        name_fa="رجا",
        mode=TravelMode.TRAIN,
        official_url="https://www.raja.ir/",
        status=ProviderSupportStatus.ACCESS_RESTRICTED,
        reason_fa="درخواست موجودی اصلاح‌شده و رمزنگاری‌شده در بررسی زنده با HTTP 403 رد شد.",
    ),
    _record(
        provider_id="snapptrip",
        name_fa="اسنپ‌تریپ",
        mode=TravelMode.TRAIN,
        official_url="https://www.snapptrip.com/train",
    ),
    _record(
        provider_id="booking",
        name_fa="بوکینگ",
        mode=TravelMode.TRAIN,
        official_url="https://www.booking.ir/rails/",
        status=ProviderSupportStatus.UPSTREAM_UNAVAILABLE,
        reason_fa="قرارداد عمومی قطار در بررسی زنده با خطای HTTP 500 پاسخ داد.",
    ),
    _record(
        provider_id="ghasedak24",
        name_fa="قاصدک ۲۴",
        mode=TravelMode.TRAIN,
        official_url="https://ghasedak24.com/train-ticket",
        status=ProviderSupportStatus.UPSTREAM_UNAVAILABLE,
        reason_fa="منبع در بررسی زنده اعلام کرد مرکز دادهٔ قطار قطع است.",
    ),
    _record(
        provider_id="fadak",
        name_fa="قطارهای فدک",
        mode=TravelMode.TRAIN,
        official_url="https://www.fadaktrains.com/train",
        status=ProviderSupportStatus.UNVERIFIED,
        reason_fa="قرارداد عمومی و پایدار جست‌وجوی موجودی هنوز به‌صورت زنده تأیید نشده است.",
    ),
    # Flight providers supplied for verification.
    _record(
        provider_id="flytoday",
        name_fa="فلای‌تودی",
        mode=TravelMode.FLIGHT,
        official_url="https://www.flytodayir.com/flight",
    ),
    _record(
        provider_id="mrbilit",
        name_fa="مستربلیط",
        mode=TravelMode.FLIGHT,
        official_url="https://mrbilit.com/plane-ticket",
    ),
    _record(
        provider_id="alibaba",
        name_fa="علی‌بابا",
        mode=TravelMode.FLIGHT,
        official_url="https://www.alibaba.ir/",
    ),
    _record(
        provider_id="safarmarket",
        name_fa="سفرمارکت",
        mode=TravelMode.FLIGHT,
        official_url="https://safarmarket.com/flights",
        status=ProviderSupportStatus.REQUIRES_HUMAN_VERIFICATION,
        reason_fa="جست‌وجوی پرواز به reCAPTCHA تولیدشده نیاز دارد و بدون دور زدن کنترل دسترسی ثبت نمی‌شود.",
    ),
    _record(
        provider_id="booking",
        name_fa="بوکینگ",
        mode=TravelMode.FLIGHT,
        official_url="https://www.booking.ir/flights/",
    ),
    _record(
        provider_id="snapptrip",
        name_fa="اسنپ‌تریپ",
        mode=TravelMode.FLIGHT,
        official_url="https://www.snapptrip.com/flights",
    ),
    _record(
        provider_id="eligasht",
        name_fa="الی‌گشت",
        mode=TravelMode.FLIGHT,
        official_url="https://www.eligasht.com/",
        status=ProviderSupportStatus.UNVERIFIED,
        reason_fa="قرارداد عمومی و پایدار جست‌وجوی موجودی هنوز به‌صورت زنده تأیید نشده است.",
    ),
    _record(
        provider_id="snapp_flights",
        name_fa="اسنپ فلایت",
        mode=TravelMode.FLIGHT,
        official_url="https://flights.snapp.ir/",
        status=ProviderSupportStatus.UNVERIFIED,
        reason_fa="قرارداد عمومی و پایدار جست‌وجوی موجودی هنوز به‌صورت زنده تأیید نشده است.",
    ),
    _record(
        provider_id="trip",
        name_fa="تریپ",
        mode=TravelMode.FLIGHT,
        official_url="https://www.trip.ir/",
        status=ProviderSupportStatus.UNVERIFIED,
        reason_fa="قرارداد عمومی و پایدار جست‌وجوی موجودی هنوز به‌صورت زنده تأیید نشده است.",
    ),
    # Bus providers supplied for verification.
    _record(
        provider_id="mrbilit",
        name_fa="مستربلیط",
        mode=TravelMode.BUS,
        official_url="https://mrbilit.com/bus-ticket",
    ),
    _record(
        provider_id="alibaba",
        name_fa="علی‌بابا",
        mode=TravelMode.BUS,
        official_url="https://www.alibaba.ir/bus-ticket",
    ),
    _record(
        provider_id="safar724",
        name_fa="سفر ۷۲۴",
        mode=TravelMode.BUS,
        official_url="https://safar724.com/",
    ),
    _record(
        provider_id="snapptrip",
        name_fa="اسنپ‌تریپ",
        mode=TravelMode.BUS,
        official_url="https://www.snapptrip.com/bus",
    ),
    _record(
        provider_id="flytoday",
        name_fa="فلای‌تودی",
        mode=TravelMode.BUS,
        official_url="https://www.flytoday.ir/bus",
    ),
    _record(
        provider_id="payaneh_ir",
        name_fa="پایانه.ir",
        mode=TravelMode.BUS,
        official_url="https://payaneh.ir/",
        status=ProviderSupportStatus.UNVERIFIED,
        reason_fa="قرارداد عمومی و پایدار جست‌وجوی موجودی هنوز به‌صورت زنده تأیید نشده است.",
    ),
    _record(
        provider_id="ghasedak24",
        name_fa="قاصدک ۲۴",
        mode=TravelMode.BUS,
        official_url="https://ghasedak24.com/bus-ticket",
        status=ProviderSupportStatus.UNVERIFIED,
        reason_fa="قرارداد عمومی و پایدار جست‌وجوی موجودی هنوز به‌صورت زنده تأیید نشده است.",
    ),
    _record(
        provider_id="safarmarket",
        name_fa="سفرمارکت",
        mode=TravelMode.BUS,
        official_url="https://safarmarket.com/buses",
        status=ProviderSupportStatus.REFERRAL_ONLY,
        reason_fa="این صفحه فقط کاربر را به قاصدک ۲۴ ارجاع می‌دهد و منبع مستقل موجودی نیست.",
    ),
    _record(
        provider_id="bazargah",
        name_fa="بازارگاه",
        mode=TravelMode.BUS,
        official_url="https://bazargah.com/bus-ticket",
        status=ProviderSupportStatus.UNVERIFIED,
        reason_fa="قرارداد عمومی و پایدار جست‌وجوی موجودی هنوز به‌صورت زنده تأیید نشده است.",
    ),
    _record(
        provider_id="payaneha",
        name_fa="پایانه‌ها",
        mode=TravelMode.BUS,
        official_url="https://www.payaneha.com/",
    ),
)


def validate_provider_support_registry(adapter_factory: AdapterFactory) -> None:
    """Fail startup when the live registry and audited catalog drift apart."""

    actual_pairs = {
        (mode, adapter.provider)
        for mode in TravelMode
        for adapter in adapter_factory.adapters_for(mode)
    }
    registered_pairs = {
        (record.mode, record.provider_id)
        for record in PROVIDER_SUPPORT_CATALOG
        if record.adapter_registered
    }
    if actual_pairs != registered_pairs:
        missing = sorted(
            f"{mode.value}/{provider}"
            for mode, provider in registered_pairs - actual_pairs
        )
        unexpected = sorted(
            f"{mode.value}/{provider}"
            for mode, provider in actual_pairs - registered_pairs
        )
        raise RuntimeError(
            "Provider support catalog does not match registered adapters; "
            f"missing={missing}, unexpected={unexpected}."
        )


class ProviderSupportService:
    """Expose the audited provider integration scope."""

    def __init__(self) -> None:
        self._catalog = PROVIDER_SUPPORT_CATALOG

    def list_for_mode(self, mode: TravelMode) -> ProviderSupportResponse:
        return ProviderSupportResponse(
            mode=mode,
            providers=[record for record in self._catalog if record.mode is mode],
        )
