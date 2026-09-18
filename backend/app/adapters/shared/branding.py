from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

_HTTP_URL = TypeAdapter(AnyHttpUrl)
_AIRLINE_CODE = re.compile(r"^[A-Z0-9]{2,3}$")
_PLACEHOLDER_MARKERS = ("unknown", "placeholder", "no-image", "no_image")

ALIBABA_LOGO_HOSTS = frozenset({"cdn.alibaba.ir"})
SNAPPTRIP_LOGO_HOSTS = frozenset({"store.snapptrip.com"})
SNAPPTRIP_TRAIN_LOGO_HOSTS = frozenset({"fs.snapptrip.com"})
MRBILIT_LOGO_HOSTS = frozenset(
    {"static.mrbilit.com", "train.mrbilit.com"}
)
PAYANEHA_LOGO_HOSTS = frozenset({"www.payaneha.com", "payaneha.com"})
FADAK_LOGO_HOSTS = frozenset({"s3.ir-thr-at1.arvanstorage.ir"})
AVA_LOGO_HOSTS = frozenset({"avaair.ir"})
FLYKISH_LOGO_HOSTS = frozenset({"flykish.com", "www.flykish.com"})
_VERIFIED_ALIBABA_AIRLINE_LOGO_CODES = frozenset(
    {
        "B9", "EP", "FP", "HH", "I3", "IR", "IS", "IV", "J1", "JI",
        "JS", "NA", "NV", "QB", "RI", "SR", "VR", "W5", "Y9", "ZV",
    }
)
_ALIBABA_AIRLINE_CODE_ALIASES = {
    "CPN": "IV",
    "IRB": "B9",
    "IRU": "RI",
    "J1": "JI",
    "NSN": "NA",
}
_OFFICIAL_AIRLINE_LOGOS = {
    "AXV": (
        "https://avaair.ir/wp-content/uploads/2023/12/ava-air-logo2.png",
        AVA_LOGO_HOSTS,
    ),
    "TKN": (
        "https://flykish.com/icons/logo-192x192.png",
        FLYKISH_LOGO_HOSTS,
    ),
}

# These are official image assets exposed by the providers themselves.  They
# are intentionally kept small and explicit: when an OTA sends no company
# logo (or sends `_unknown.png`) we must not guess a third-party image or use a
# generic transport icon.  Add a name here only after the URL has been
# observed in that provider's public result/company page.
_OFFICIAL_TRAIN_LOGOS = {
    "رجا": "https://fs.snapptrip.com/images/train/uploads/raja.png",
    "فدک": (
        "https://s3.ir-thr-at1.arvanstorage.ir/new-train-public/"
        "images/logos/fadak-new-logo-full.svg"
    ),
}
_OFFICIAL_BUS_LOGOS = {
    "سیر و سفر": (
        "https://www.payaneha.com/cloob/Images/"
        "seirosafar-351064cc4bbab969d84466d460fd.jpg"
    ),
    "سیروسفر": (
        "https://www.payaneha.com/cloob/Images/"
        "seirosafar-351064cc4bbab969d84466d460fd.jpg"
    ),
    "عدل": "https://www.payaneha.com/cloob/Images/cd45018cd2c2d392209947-adl.png",
    "ایران پیما": (
        "https://www.payaneha.com/cloob/Images/"
        "d149efa19a95247ff78795-iranpeymalogo.png"
    ),
    "ترابر بی تا": (
        "https://www.payaneha.com/cloob/Images/"
        "694a7c9f0f78d846eef9d3-bitalogo.png"
    ),
    "پیک صبا": (
        "https://www.payaneha.com/cloob/Images/"
        "454c5f8c40701efdb26497-peyksabalogo.png"
    ),
    "میهن نور": (
        "https://www.payaneha.com/cloob/Images/"
        "8246b1b563a793fb329111-mihannour.png"
    ),
    "گیتی پیما": (
        "https://www.payaneha.com/cloob/Images/"
        "gitypeyma-6384734c4664b743b0a721ed425d.jpg"
    ),
    "لوان نور": (
        "https://www.payaneha.com/cloob/Images/"
        "levan100-885477364ddf8f017fa173709566.png"
    ),
    "همسفر": (
        "https://www.payaneha.com/cloob/Images/"
        "0d4f6495ad5be9b0c79c96-hamsafarlogo.png"
    ),
    "رویال سفر": "https://www.payaneha.com/images/payanehlogo/ROYAL.png",
    "رویال سفر ایرانیان": (
        "https://www.payaneha.com/images/payanehlogo/ROYAL.png"
    ),
    "ایمن سفر": (
        "https://www.payaneha.com/cloob/Images/"
        "9545ef8185d8966810a959-imensafarlogo.png"
    ),
    "آسیا سفر": (
        "https://www.payaneha.com/cloob/Images/"
        "asiasafar-9980521b42229af7b515e3ad371c.png"
    ),
    "جوان سیر ایثار": (
        "https://www.payaneha.com/cloob/Images/"
        "javan-seir-iesar-8621796e48d29e8eeba8105d622b.png"
    ),
    "آریا سفر": (
        "https://www.payaneha.com/cloob/Images/"
        "264011a837410c40fb11a2-ariasafar.jpg"
    ),
    "پیک معتمد": (
        "https://www.payaneha.com/cloob/Images/"
        "9c44c18cdd6244fdc75b2b-peykmotamedlogo.png"
    ),
}


def _brand_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(
        unicodedata.normalize("NFKC", value)
        .replace("ي", "ی")
        .replace("ى", "ی")
        .replace("ك", "ک")
        .replace("\u200c", " ")
        .split()
    ).casefold()


def _catalog_logo_url(
    operator: Any,
    catalog: dict[str, str],
    *,
    allowed_hosts: Iterable[str],
) -> AnyHttpUrl | None:
    key = _brand_key(operator)
    if not key:
        return None
    padded_key = f" {key} "
    compact_key = key.replace(" ", "")
    # Long aliases must win over short names (e.g. «رویال سفر ایرانیان» over
    # «رویال سفر»).  Prefix matching handles terminal/cooperative suffixes.
    for alias, value in sorted(catalog.items(), key=lambda item: len(item[0]), reverse=True):
        normalized_alias = _brand_key(alias)
        compact_alias = normalized_alias.replace(" ", "")
        if (
            key == normalized_alias
            or key.startswith(f"{normalized_alias} ")
            or f" {normalized_alias} " in padded_key
            or compact_key.startswith(compact_alias)
            or compact_alias in compact_key
        ):
            return trusted_logo_url(value, allowed_hosts=allowed_hosts)
    return None


def trusted_logo_url(
    value: Any,
    *,
    allowed_hosts: Iterable[str],
) -> AnyHttpUrl | None:
    """Return only HTTPS image URLs hosted by an allowlisted OTA domain."""

    if not isinstance(value, str):
        return None
    candidate = value.strip()
    lowered = candidate.casefold()
    if not candidate or any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
        return None
    try:
        parsed = urlsplit(candidate)
        hostname = (parsed.hostname or "").casefold()
        port = parsed.port
    except ValueError:
        return None
    hosts = {host.casefold() for host in allowed_hosts}
    if (
        parsed.scheme.casefold() != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or hostname not in hosts
    ):
        return None
    try:
        return _HTTP_URL.validate_python(candidate)
    except ValidationError:
        return None


def first_trusted_logo_url(
    *values: Any,
    allowed_hosts: Iterable[str],
) -> AnyHttpUrl | None:
    for value in values:
        if logo_url := trusted_logo_url(value, allowed_hosts=allowed_hosts):
            return logo_url
    return None


def airline_code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    code = value.strip().upper()
    return code if _AIRLINE_CODE.fullmatch(code) else None


def alibaba_airline_logo_url(code: str | None) -> AnyHttpUrl | None:
    """Build the official logo URL used by Alibaba's own flight client."""

    verified_code = airline_code(code)
    if verified_code is None:
        return None
    # Some flight APIs expose an internal three-letter carrier code while the
    # same official Alibaba asset is keyed by its two-letter IATA code.
    if official := _OFFICIAL_AIRLINE_LOGOS.get(verified_code):
        return trusted_logo_url(official[0], allowed_hosts=official[1])
    verified_code = _ALIBABA_AIRLINE_CODE_ALIASES.get(verified_code, verified_code)
    if verified_code not in _VERIFIED_ALIBABA_AIRLINE_LOGO_CODES:
        return None
    return trusted_logo_url(
        f"https://cdn.alibaba.ir/static/img/airlines/Domestic/{verified_code}.png",
        allowed_hosts=ALIBABA_LOGO_HOSTS,
    )


def train_operator_logo_url(operator: Any) -> AnyHttpUrl | None:
    """Resolve a known railway logo from an OTA-owned public asset."""

    return _catalog_logo_url(
        operator,
        _OFFICIAL_TRAIN_LOGOS,
        allowed_hosts=SNAPPTRIP_TRAIN_LOGO_HOSTS | FADAK_LOGO_HOSTS,
    )


def bus_operator_logo_url(operator: Any) -> AnyHttpUrl | None:
    """Resolve a known bus-company logo from an OTA-owned public asset."""

    return _catalog_logo_url(
        operator,
        _OFFICIAL_BUS_LOGOS,
        allowed_hosts=PAYANEHA_LOGO_HOSTS,
    )
