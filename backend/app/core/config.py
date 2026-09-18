from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from os import getenv


def _cors_origins_from_environment() -> tuple[str, ...]:
    raw_origins = getenv(
        "TOROB_TRAVEL_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())


def _redirect_hosts_by_provider_from_environment() -> Mapping[str, tuple[str, ...]]:
    raw_bindings = getenv(
        "TOROB_TRAVEL_REDIRECT_HOSTS_BY_PROVIDER",
        (
            "alibaba=www.alibaba.ir|alibaba.ir;"
            "flytoday=www.flytodayir.com|flytodayir.com;"
            "snapptrip=www.snapptrip.com|snapptrip.com;"
            "mrbilit=mrbilit.com|www.mrbilit.com;"
            "safar724=safar724.com|www.safar724.com;"
            "booking=www.booking.ir|booking.ir;"
            "payaneha=www.payaneha.com|payaneha.com"
        ),
    )
    bindings: dict[str, tuple[str, ...]] = {}
    for raw_binding in raw_bindings.split(";"):
        provider, separator, raw_hosts = raw_binding.partition("=")
        provider = provider.strip().casefold()
        hosts = tuple(
            host.strip().rstrip(".").casefold()
            for host in raw_hosts.split("|")
            if host.strip().rstrip(".")
        )
        if not separator or not provider or not hosts:
            raise ValueError(
                "TOROB_TRAVEL_REDIRECT_HOSTS_BY_PROVIDER must use "
                "provider=host|host;provider=host syntax."
            )
        if provider in bindings:
            raise ValueError(f"Duplicate redirect provider binding: {provider}.")
        bindings[provider] = hosts
    return bindings


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    project_name: str = field(
        default_factory=lambda: getenv("TOROB_TRAVEL_PROJECT_NAME", "Torob Travel API")
    )
    environment: str = field(
        default_factory=lambda: getenv("TOROB_TRAVEL_ENVIRONMENT", "development")
    )
    api_prefix: str = "/api/v1"
    cors_origins: tuple[str, ...] = field(default_factory=_cors_origins_from_environment)
    adapter_timeout_seconds: float = field(
        default_factory=lambda: float(getenv("TOROB_TRAVEL_ADAPTER_TIMEOUT_SECONDS", "8"))
    )
    location_timeout_seconds: float = field(
        default_factory=lambda: float(
            getenv("TOROB_TRAVEL_LOCATION_TIMEOUT_SECONDS", "2")
        )
    )
    search_max_concurrency: int = field(
        default_factory=lambda: int(
            getenv("TOROB_TRAVEL_SEARCH_MAX_CONCURRENCY", "16")
        )
    )
    search_admission_timeout_seconds: float = field(
        default_factory=lambda: float(
            getenv("TOROB_TRAVEL_SEARCH_ADMISSION_TIMEOUT_SECONDS", "0.1")
        )
    )
    adapter_search_cache_ttl_seconds: float = field(
        default_factory=lambda: float(
            getenv("TOROB_TRAVEL_ADAPTER_SEARCH_CACHE_TTL_SECONDS", "30")
        )
    )
    adapter_search_cache_max_entries: int = field(
        default_factory=lambda: int(
            getenv("TOROB_TRAVEL_ADAPTER_SEARCH_CACHE_MAX_ENTRIES", "256")
        )
    )
    search_job_ttl_seconds: int = field(
        default_factory=lambda: int(
            getenv("TOROB_TRAVEL_SEARCH_JOB_TTL_SECONDS", "600")
        )
    )
    search_job_max_entries: int = field(
        default_factory=lambda: int(
            getenv("TOROB_TRAVEL_SEARCH_JOB_MAX_ENTRIES", "200")
        )
    )
    search_job_max_concurrency: int = field(
        default_factory=lambda: int(
            getenv("TOROB_TRAVEL_SEARCH_JOB_MAX_CONCURRENCY", "8")
        )
    )
    offer_ttl_seconds: int = field(
        default_factory=lambda: int(getenv("TOROB_TRAVEL_OFFER_TTL_SECONDS", "900"))
    )
    offer_repository_max_entries: int = field(
        default_factory=lambda: int(
            getenv("TOROB_TRAVEL_OFFER_REPOSITORY_MAX_ENTRIES", "5000")
        )
    )
    api_worker_count: int = field(
        default_factory=lambda: int(getenv("TOROB_TRAVEL_API_WORKERS", "1"))
    )
    redirect_hosts_by_provider: Mapping[str, tuple[str, ...]] = field(
        default_factory=_redirect_hosts_by_provider_from_environment
    )


settings = Settings()
