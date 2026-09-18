from __future__ import annotations

from app.domain.offer import Seller

SAFAR724_LOCATIONS_URL = "https://safar724.com/route/getcities"
SAFAR724_SEARCH_URL = "https://service.safar724.com/cs/api/bus/route"
SAFAR724_LOGO_HOSTS = frozenset({"cdn.safar724.com"})

SAFAR724_SELLER = Seller(
    id="safar724",
    name="سفر ۷۲۴",
    rating=None,
    review_count=None,
    # The origin redirects the mixed-case path to a lower-case one. The logo
    # proxy deliberately does not follow redirects, so keep the canonical URL
    # here and avoid turning a valid seller logo into a fallback initial.
    logo_url="https://safar724.com/content/images/logo.png",
)
