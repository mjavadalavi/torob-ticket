from __future__ import annotations

from app.domain.offer import Seller

PAYANEHA_ORIGINS_URL = "https://www.payaneha.com/busticket/fillorigins"
PAYANEHA_DESTINATIONS_URL = "https://www.payaneha.com/busticket/filldestinations"
PAYANEHA_SEARCH_URL = "https://www.payaneha.com/busticket/ajaxsearch"
PAYANEHA_LOGO_HOSTS = frozenset({"www.payaneha.com", "payaneha.com"})

PAYANEHA_SELLER = Seller(
    id="payaneha",
    name="پایانه‌ها",
    rating=None,
    review_count=None,
    logo_url="https://www.payaneha.com/Images/payanehaicon.png",
)
