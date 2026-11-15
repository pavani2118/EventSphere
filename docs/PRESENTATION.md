# EventSphere University Presentation Outline

## Slide 1: Title

EventSphere — University Event and Venue Booking System.

## Slide 2: Problem

Explain fragmented event administration, ticket capacity risks, manual
admission validation, venue scheduling conflicts, and sell-out demand.

## Slide 3: Objectives

Present the goals of authenticated event management, safe booking, QR
check-in, venue hire, notifications, and waitlist automation.

## Slide 4: System overview

Show the browser frontend, FastAPI application, PostgreSQL database, and
runtime lifecycle.

## Slide 5: Technologies

- Python and FastAPI
- PostgreSQL and psycopg
- Pydantic
- Bootstrap, HTML, CSS, and JavaScript
- Pytest and HTTPX

## Slide 6: Architecture

Insert the system architecture diagram from
[ARCHITECTURE.md](ARCHITECTURE.md).

## Slide 7: Five-agent approach

Introduce VenueAgent, BookingAgent, TicketAgent, WaitlistAgent, and
NotificationAgent. Explain ACL messages and the in-process MessageBus.

## Slide 8: Booking workflow

Demonstrate event selection, category availability, simulated payment,
booking confirmation, ticket generation, and notification persistence.

## Slide 9: Waitlist and reliability

Explain FIFO processing, expiry, `waitlist_id` idempotency, active-entry
uniqueness, and transaction-safe retries.

## Slide 10: QR admission

Demonstrate ticket ownership, gate-staff authorization, valid check-in, and
duplicate check-in rejection.

## Slide 11: Venue hire and administration

Show availability checks, pricing, venue-hire history, management pages, and
dashboard data. Use only authentic screenshots.

## Slide 12: Testing

Present the exact automated test count and environment, compilation result,
browser checks, and any skipped or blocked integration tests.

## Slide 13: Deployment

Explain Render startup, PostgreSQL environment variables, migration review,
`/health`, and the distinction between prepared and verified deployment.

## Slide 14: Limitations and future work

Mention simulated payments, no production notification provider, schema
bootstrap limitations, and future admin escalation/observability work.

## Slide 15: Conclusion

Summarize the implemented platform and its contribution to coordinated
university event operations.
