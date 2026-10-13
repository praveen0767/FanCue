"""Cricket adapter domain exceptions."""


class CricketAdapterError(Exception):
    """Base exception for all cricket adapter failures."""
    def __init__(self, message: str, context: dict = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}


class FixtureNotFoundError(CricketAdapterError):
    """Raised when a requested match fixture file does not exist on disk."""
    pass


class ChecksumMismatchError(CricketAdapterError):
    """Raised when fixture file SHA-256 does not match recorded provenance."""
    pass


class CricsheetFormatError(CricketAdapterError):
    """Raised when Cricsheet JSON root structure is malformed or unsupported."""
    pass


class MissingCriticalFieldError(CricketAdapterError):
    """Raised when a required scoring or sequence field is absent."""
    pass


class CricsheetDeliveryArithmeticError(CricketAdapterError):
    """Raised when delivery runs (batter + extras) do not equal total runs."""
    pass
