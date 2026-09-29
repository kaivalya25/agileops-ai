import json

from agileops.domain.enums import (
    TicketPriority,
    TicketStatus,
    TicketType,
)
from agileops.domain.exceptions import InvalidStatusTransitionError
from agileops.domain.models import Ticket, build_ticket_title


PROJECT_NAME = "AgileOps AI"

def get_project_name() -> str:
    return PROJECT_NAME

def main() -> None:
    print(f"Starting the Project {get_project_name()}!")

    ticket = Ticket(
        ticket_id="INC 26-0001",
        title=build_ticket_title("INC 26-0001", "Report is not refreshing since this morning"),
        description="The report on the dashboard is not updating with the latest data since this morning.",
        ticket_type=TicketType.INCIDENT,
        priority=TicketPriority.HIGH,
        business_impact="Executive reporting unavailable.",
        created_by="user123",
        assigned_to="SW_Agent"
    )
    print(ticket)

    print(
        json.dumps(
            ticket.to_dict(),
            indent = 2,
        )
    )

    print("Initial:", ticket.status)
    ticket.change_status(TicketStatus.INVESTIGATING)
    print("After change:", ticket.status)

    try:
        ticket.change_status(TicketStatus.DONE)
    except InvalidStatusTransitionError as error:
        print(f"Status change rejected: {error}")

if __name__ == "__main__":
    main()
