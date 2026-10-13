"""Deterministic match engine domain exceptions."""


class MatchEngineError(Exception):
    """Base exception for all match engine calculation and reconstruction errors."""
    def __init__(self, message: str, context: dict = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}


class InvalidIntervalError(MatchEngineError):
    """Raised when an interval violates boundary invariants."""
    pass


class InningsIndexOutOfBoundsError(MatchEngineError):
    """Raised when a requested innings index does not exist in the match."""
    pass


class OverBoundaryNotFoundError(MatchEngineError):
    """Raised when a requested boundary exceeds recorded match progression."""
    pass


class ReconciliationError(MatchEngineError):
    """Raised when computed engine totals fail scorecard reconciliation."""
    pass
