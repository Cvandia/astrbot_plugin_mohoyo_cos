from httpx import HTTPError


class RequestError(HTTPError):
    """Exception raised when an HTTP request fails."""
