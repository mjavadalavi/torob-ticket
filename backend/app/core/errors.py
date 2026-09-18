from __future__ import annotations


class ApplicationError(Exception):
    """Base error for expected application failures."""

    status_code = 500
    code = "application_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ResourceNotFoundError(ApplicationError):
    status_code = 404
    code = "resource_not_found"


class AdapterUnavailableError(ApplicationError):
    status_code = 503
    code = "adapter_unavailable"


class SearchQueueFullError(ApplicationError):
    status_code = 503
    code = "search_queue_full"
