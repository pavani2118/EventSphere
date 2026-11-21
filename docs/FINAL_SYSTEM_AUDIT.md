# EventSphere Final System Audit

## Audit summary

| Module | Status | Evidence |
| --- | --- | --- |
| Authentication | Complete for local bearer-token workflows | Registration, login, logout, active-session lookup, password hashing, and role dependencies |
| Admin | Complete | Existing dashboard, event, venue, category, and gate administration APIs |
| Organiser | Complete for current owner-scoped event workflow | Added organiser summary and booking APIs; existing create/edit/publish/cancel routes enforce ownership |
| Attendee | Complete for core booking and ticket workflows | Browse, book, cancel, tickets, QR, waitlist, and notifications |
| Waitlist | Complete for join, queue position, leave, expiry, FIFO, and notification integration | Existing status constraint remains unchanged |
| Simulated payments | Complete in the existing automatic-success workflow | Payments are calculated by the backend and `SUCCESS` is recorded with ticket generation |
| Notifications | Complete for retrieval, mark-one-read, mark-all-read, and agent creation | No external notification provider is configured |
| VenueAgent | Implemented | Availability, conflict, hire, and alternative logic |
| BookingAgent | Implemented | Capacity locking, payment, ticket generation, idempotency |
| TicketAgent | Implemented | QR validation, payment/event checks, row locking, and duplicate prevention |
| WaitlistAgent | Implemented | Join, FIFO processing, expiry, leave support, and notification integration |
| NotificationAgent | Implemented | Validated recipient, persisted notification, and agent state |
| Gate Staff | Implemented locally | Dashboard, scanner, validation, check-in, history, events, and profile |

## Known limitations

- Database-backed authentication tests remain skipped unless
  `EVENTSPHERE_TEST_DATABASE=1` is set for an isolated PostgreSQL database.
- The waitlist test database test remains skipped unless isolated PostgreSQL
  environment variables are configured.
- The existing booking workflow uses an automatic successful simulated
  payment. A separate user-selectable failed-payment state is not currently
  implemented.
- Physical mobile-camera scanning has not been verified on a physical device.
- Live deployment and Neon data have not been changed or verified during this
  audit.
- There is no external email/SMS/push notification provider.
- Organiser dashboard UI may use the new APIs without a dedicated full-page
  dashboard. Existing event-management UI remains available.

## Security verification

- Bearer-token authentication remains enabled.
- Role dependencies protect organiser, gate, and admin routes.
- Organiser event queries and mutations verify `created_by`.
- Attendee booking/ticket ownership remains enforced by existing queries.
- Gate check-in verifies staff role and locks the ticket row during update.
- SQL uses parameterized psycopg queries.
- Passwords use the existing PBKDF2-HMAC-SHA256 implementation.
- No credentials or production database values are included in this document.
