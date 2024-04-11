# http v2 exception types
class HttpServerInitError(Exception):
    """Exception raised when there is an error during HTTP server
    initialization."""


class MissingHeaderError(ValueError):
    """Exception raised when a required header is missing in the
    HTTP request."""
