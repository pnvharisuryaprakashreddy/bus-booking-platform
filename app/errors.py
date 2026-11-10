class DomainError(Exception):
    """A business-rule failure with a stable error code and HTTP status."""

    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)
