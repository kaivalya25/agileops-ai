from enum import Enum

class TicketStatus(str, Enum):
    NEW = "new"
    INVESTIGATING = "investigating"
    READY_FOR_DEV = "ready_for_dev"
    IN_PROGRESS = "in_progress"
    QA = "qa"
    DONE = "done"

class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TicketType(str, Enum):
    BUG = "bug"
    FEATURE = "feature"
    INCIDENT = "incident"
    TECHNICAL = "technical"
    OTHER = "other"