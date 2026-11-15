# Academic Submission Structure

This document is a report outline grounded in the implemented EventSphere
source. Replace the screenshot placeholders with captures from a configured
test database; do not use fabricated data.

## 1. Introduction

EventSphere is a university event and venue-booking platform that combines
event administration, ticket booking, QR-based admission, waitlists,
notifications, and private venue hire in one web application.

## 2. Problem statement

Manual event and venue processes make it difficult to enforce capacity,
coordinate venue schedules, process demand after sell-out, and validate
admission securely.

## 3. Aim and objectives

The aim is to build a role-aware university event platform using FastAPI,
PostgreSQL, and a cooperating agent architecture. Objectives are listed in the
project [README](../README.md).

## 4. Scope

### In scope

- attendee registration, login, booking, cancellation, tickets, QR display,
  waitlists, notifications, and venue-hire requests;
- organiser/admin venue and event management;
- gate-staff QR check-in;
- simulated payment and refund records; and
- ACL message routing and persistent agent state.

### Out of scope

- real payment-provider settlement;
- production email/SMS delivery;
- a complete database bootstrap schema in this repository;
- deployed production operations; and
- a documented manual-admin venue-hire escalation policy.

## 5. Functional requirements

1. Users can authenticate and receive bearer sessions.
2. Administrators and organisers can manage event inventory.
3. Attendees can book available tickets.
4. The system prevents overselling and duplicate waitlist fulfillment.
5. Tickets have secure QR tokens and one-time check-in.
6. Users can view notifications and venue-hire history.
7. Gate staff can validate tickets.
8. Administrators can inspect live dashboard and agent data.

## 6. Non-functional requirements

- parameterized SQL and ownership checks;
- transaction-safe booking, cancellation, check-in, and waitlist operations;
- responsive Bootstrap pages;
- persistent agent state and message logging;
- clear API error responses; and
- no secrets committed to source control.

## 7. System and agent architecture

Use the Mermaid diagram and agent descriptions in the project
[README](../README.md). Explain that API routers send ACL messages through the
in-process MessageBus and that agents do not directly invoke one another.

## 8. Use-case descriptions

- **Register and login:** an attendee creates an account and receives a
  bearer session.
- **Book event tickets:** the BookingAgent locks a category, checks remaining
  capacity, creates a simulated payment, confirms the booking, and generates
  tickets.
- **Check in:** gate staff submit a QR token; TicketAgent locks the ticket and
  changes `VALID` to `USED` once.
- **Join and process waitlist:** an attendee joins a published event; the
  WaitlistAgent processes waiting entries FIFO when capacity is available.
- **Hire a venue:** an authenticated user checks a period and submits a
  request subject to capacity, conflict, and turnaround rules.

## 9. Database design

Use [DATABASE.md](DATABASE.md) for the table and relationship description.
Capture an ER diagram from the verified PostgreSQL schema before final
submission because the repository does not include a complete schema dump.

## 10. Implementation

Describe FastAPI routers, Pydantic validation, psycopg transactions, Bootstrap
templates, browser JavaScript, the ACL bus, and the waitlist scheduler.

## 11. Testing and results

Record the exact command, date, environment, and result. The current local
verification includes compilation and unit/route tests, but PostgreSQL-backed
tests require configured database credentials. Do not report the database
integration suite as passing until it has been run against a disposable test
database.

## 12. Limitations

- no tracked complete schema bootstrap;
- no real payment gateway;
- no production deployment verification;
- no formal manual venue-hire escalation rule; and
- browser workflow verification requires authenticated test accounts and
  database data.

## 13. Future improvements

- add versioned schema bootstrap migrations;
- add a formal admin review queue for manual venue-hire decisions;
- integrate a real payment provider and email delivery service;
- add CI with a disposable PostgreSQL service;
- add structured audit logging and metrics; and
- add automated end-to-end browser tests.

## 14. Conclusion

EventSphere demonstrates an integrated university event-management workflow
with role-based access, PostgreSQL-backed consistency, QR admission, and
cooperating domain agents. Final deployment and database verification remain
operational steps rather than claims of completed production deployment.
