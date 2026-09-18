from __future__ import annotations

from abc import ABC, abstractmethod


class RedirectProvider(ABC):
    @abstractmethod
    def build_redirect_url(self, source_offer_id: str) -> str:
        """Build a verified external URL for a provider offer."""

        raise NotImplementedError
