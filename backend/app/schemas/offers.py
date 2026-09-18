from __future__ import annotations

from typing import Literal

from pydantic import AnyHttpUrl

from app.domain.travel import ApiModel


class RedirectPreview(ApiModel):
    offer_id: str
    seller_offer_id: str
    provider: str
    seller_id: str
    seller_name: str
    url: AnyHttpUrl
    target_kind: Literal["seller_search", "offer_deep_link"]
    price_recheck_required: bool
    is_external: bool = True
    notice_code: Literal["external_checkout"] = "external_checkout"
