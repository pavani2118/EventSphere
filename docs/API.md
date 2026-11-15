# EventSphere API Inventory

All authenticated endpoints use:

```text
Authorization: Bearer <access_token>
```

FastAPI generates the authoritative interactive specification at `/docs`.

## Authentication

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | Public | Create an attendee account |
| `POST` | `/auth/login` | Public | Create a session and return an access token |
| `GET` | `/auth/me` | Authenticated | Return the current user |
| `POST` | `/auth/logout` | Authenticated | Delete the current session |
| `GET` | `/auth/admin-check` | `ADMIN` | Verify admin access |

## Events and venues

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/events/` | Public | List published events; supports category and venue filters |
| `GET` | `/events/{event_id}` | Public | View one event |
| `GET` | `/events/{event_id}/ticket-categories` | Public | List ticket categories |
| `POST` | `/events/` | `ADMIN`, `ORGANISER` | Create an event |
| `GET` | `/events/manage/all` | `ADMIN`, `ORGANISER` | List managed events |
| `PUT` | `/events/{event_id}` | `ADMIN`, `ORGANISER` | Update an event |
| `POST` | `/events/{event_id}/publish` | `ADMIN`, `ORGANISER` | Publish an event |
| `POST` | `/events/{event_id}/cancel` | `ADMIN`, `ORGANISER` | Cancel an event |
| `POST` | `/events/{event_id}/ticket-categories` | `ADMIN`, `ORGANISER` | Create a ticket category |
| `GET` | `/events/manage/{event_id}/ticket-categories` | `ADMIN`, `ORGANISER` | List managed categories |
| `POST` | `/venues/` | `ADMIN`, `ORGANISER` | Create a venue |
| `GET` | `/venues/` | Public | List venues |
| `GET` | `/venues/{venue_id}` | Public | View a venue |
| `PUT` | `/venues/{venue_id}` | `ADMIN`, `ORGANISER` | Update a venue |
| `DELETE` | `/venues/{venue_id}` | `ADMIN`, `ORGANISER` | Delete a venue |

Request schemas and response fields are available in Swagger. Event and venue
schemas enforce numeric and period validation through Pydantic.

## Booking, ticket, and waitlist APIs

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/bookings/` | `ATTENDEE` | Create a booking through BookingAgent |
| `GET` | `/bookings/my-bookings` | `ATTENDEE` | List the current user's bookings and payment data |
| `POST` | `/bookings/{booking_id}/cancel` | Owner or `ADMIN` | Cancel a confirmed booking and refund its successful payment |
| `GET` | `/tickets/my-tickets` | `ATTENDEE` | List the current user's tickets |
| `GET` | `/tickets/{ticket_id}` | Owner, `ADMIN`, `GATE_STAFF` | View one ticket |
| `GET` | `/tickets/{ticket_id}/qr` | Ticket owner | Generate the ticket QR image |
| `POST` | `/tickets/check-in` | `GATE_STAFF`, `ADMIN` | Check in a QR token |
| `POST` | `/waitlist/join` | `ATTENDEE` | Join an event waitlist |
| `GET` | `/waitlist/my-waitlist` | `ATTENDEE` | List the current user's waitlist entries |
| `POST` | `/waitlist/process/{event_id}` | `ADMIN` | Process an event waitlist |

## Venue hire, notifications, and dashboard

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/venue-hire/availability` | Authenticated | Check availability and alternatives |
| `POST` | `/venue-hire/request` | Authenticated | Submit a private-hire request |
| `GET` | `/venue-hire/my-requests` | Authenticated | List the current user's hire requests |
| `GET` | `/notifications/my-notifications` | Authenticated | List the current user's notifications |
| `PATCH` | `/notifications/{notification_id}/read` | Notification owner | Mark a notification read |
| `GET` | `/dashboard/admin/summary` | `ADMIN` | Return live dashboard totals |
| `GET` | `/dashboard/admin/agent-messages` | `ADMIN` | Return recent ACL messages |
| `GET` | `/dashboard/admin/recent-events` | `ADMIN` | Return recent events |
| `GET` | `/dashboard/admin/recent-bookings` | `ADMIN` | Return recent bookings |
| `GET` | `/health` | Public | Application health |
| `GET` | `/db-health` | Public | Database connectivity check |
| `GET` | `/scanner` | Public page; API actions require staff token | Serve the gate scanner page |
