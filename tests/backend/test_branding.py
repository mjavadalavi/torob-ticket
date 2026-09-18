from app.adapters.alibaba.spec import ALIBABA_SELLER
from app.adapters.shared.branding import (
    SNAPPTRIP_LOGO_HOSTS,
    alibaba_airline_logo_url,
    bus_operator_logo_url,
    first_trusted_logo_url,
    train_operator_logo_url,
    trusted_logo_url,
)
from app.adapters.snapptrip.spec import SNAPPTRIP_SELLER
from app.domain.itinerary import OfferAttributes


def test_official_seller_logos_include_accessible_fallback_metadata() -> None:
    assert str(ALIBABA_SELLER.logo_url).startswith("https://cdn.alibaba.ir/")
    assert ALIBABA_SELLER.logo_alt == "نشان فروشنده علی‌بابا"
    assert ALIBABA_SELLER.logo_fallback == "عل"
    assert str(SNAPPTRIP_SELLER.logo_url).startswith(
        "https://store.snapptrip.com/"
    )
    assert SNAPPTRIP_SELLER.logo_alt == "نشان فروشنده اسنپ‌تریپ"
    assert SNAPPTRIP_SELLER.logo_fallback == "اس"


def test_payload_logo_url_rejects_placeholder_untrusted_and_malformed_values() -> None:
    assert (
        first_trusted_logo_url(
            "_unknown.png",
            "https://example.com/logo.png",
            "https://store.snapptrip.com:bad/logo.png",
            "https://[broken/logo.png",
            allowed_hosts=SNAPPTRIP_LOGO_HOSTS,
        )
        is None
    )


def test_payload_logo_url_accepts_only_allowlisted_https_asset() -> None:
    value = "https://store.snapptrip.com/assets/operators/1045.png"

    result = trusted_logo_url(value, allowed_hosts=SNAPPTRIP_LOGO_HOSTS)

    assert str(result) == value


def test_operator_metadata_has_text_fallback_without_an_image() -> None:
    attributes = OfferAttributes(operator="پارس لاریم")

    assert attributes.operator_logo_url is None
    assert attributes.operator_logo_alt == "نشان شرکت پارس لاریم"
    assert attributes.operator_logo_fallback == "پا"


def test_known_operator_catalogues_use_provider_owned_assets() -> None:
    assert str(train_operator_logo_url("رجا")) == (
        "https://fs.snapptrip.com/images/train/uploads/raja.png"
    )
    assert str(train_operator_logo_url("قطار فدک")) == (
        "https://s3.ir-thr-at1.arvanstorage.ir/new-train-public/"
        "images/logos/fadak-new-logo-full.svg"
    )
    assert str(bus_operator_logo_url("همسفر چابکسواران")) == (
        "https://www.payaneha.com/cloob/Images/"
        "0d4f6495ad5be9b0c79c96-hamsafarlogo.png"
    )
    assert str(bus_operator_logo_url("تعاونی ۱۵ ترابربی تا")) == (
        "https://www.payaneha.com/cloob/Images/"
        "694a7c9f0f78d846eef9d3-bitalogo.png"
    )
    assert bus_operator_logo_url("شرکت ناشناخته") is None


def test_airline_logo_catalog_never_synthesizes_unverified_404_urls() -> None:
    assert str(alibaba_airline_logo_url("NV")) == (
        "https://cdn.alibaba.ir/static/img/airlines/Domestic/NV.png"
    )
    assert alibaba_airline_logo_url("ISP") is None
    assert alibaba_airline_logo_url("ATS") is None
    assert str(alibaba_airline_logo_url("J1")) == (
        "https://cdn.alibaba.ir/static/img/airlines/Domestic/JI.png"
    )
    assert str(alibaba_airline_logo_url("CPN")) == (
        "https://cdn.alibaba.ir/static/img/airlines/Domestic/IV.png"
    )
    assert str(alibaba_airline_logo_url("NSN")) == (
        "https://cdn.alibaba.ir/static/img/airlines/Domestic/NA.png"
    )
    assert str(alibaba_airline_logo_url("AXV")) == (
        "https://avaair.ir/wp-content/uploads/2023/12/ava-air-logo2.png"
    )
    assert str(alibaba_airline_logo_url("TKN")) == (
        "https://flykish.com/icons/logo-192x192.png"
    )
