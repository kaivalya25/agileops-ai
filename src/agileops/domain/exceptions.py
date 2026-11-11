class InvalidStatusTransitionError(Exception):
    """Raised when an invalid status transition is attempted."""


class SprintNotFoundError(LookupError):
    """Raised when assigning a ticket to an unknown sprint."""
