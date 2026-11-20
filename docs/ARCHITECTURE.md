# EventSphere Architecture and Diagrams

These diagrams describe the architecture implemented in the repository. The
message bus is an in-process Python component; no external broker, payment
provider, email provider, or SMS provider is configured.

## System architecture

```mermaid
flowchart LR
    Browser[HTML CSS Bootstrap JavaScript] --> FastAPI[FastAPI application]
    FastAPI --> Routers[Auth event venue booking ticket waitlist hire dashboard routers]
    Routers --> Bus[In-process ACL MessageBus]
    FastAPI --> Static[Static files and HTML templates]
    Bus --> Agents[Five domain agents]
    Agents --> PostgreSQL[(PostgreSQL)]
    FastAPI --> PostgreSQL
    Scheduler[Waitlist expiry scheduler] --> Bus
    Health[/health] --> FastAPI
```

## Agent architecture

```mermaid
flowchart TB
    API[FastAPI routers and API gateways] --> Bus[ACL MessageBus]
    Bus --> Venue[VenueAgent\navailability, hire, conflicts, pricing]
    Bus --> Booking[BookingAgent\nvalidation, payment, booking, QR tickets]
    Bus --> Ticket[TicketAgent\nownership, QR validation, check-in]
    Bus --> Waitlist[WaitlistAgent\njoin, FIFO processing, expiry, idempotency]
    Bus --> Notification[NotificationAgent\npersist user notifications]
    Scheduler[WaitlistScheduler] -->|INFORM EXPIRE_WAITLIST| Bus
    Waitlist -->|REQUEST CREATE_BOOKING| Bus
    Booking -->|INFORM SEND_NOTIFICATION| Bus
    Bus --> Logs[(agent_messages)]
    Venue --> State[(agent_states)]
    Booking --> State
    Ticket --> State
    Waitlist --> State
    Notification --> State
```

All ACL messages contain `sender`, `receiver`, `performative`, `content`,
`conversation_id`, and `timestamp`. Supported performatives are `REQUEST`,
`AGREE`, `REFUSE`, `PROPOSE`, `INFORM`, and `FAILURE`.

## Database ER diagram

The following entities and relationships are the tables referenced by the
application SQL and the applied waitlist idempotency migration. Confirm exact
constraint names against the deployment database before production migration.

```mermaid
erDiagram
    USERS ||--o{ USER_SESSIONS : has
    USERS ||--o{ BOOKINGS : makes
    USERS ||--o{ VENUE_HIRE_REQUESTS : submits
    USERS ||--o{ WAITLIST : joins
    USERS ||--o{ NOTIFICATIONS : receives
    USERS ||--o{ TICKETS : checks_in
    VENUES ||--o{ EVENTS : hosts
    VENUES ||--o{ VENUE_HIRE_REQUESTS : requested_for
    EVENTS ||--o{ TICKET_CATEGORIES : contains
    EVENTS ||--o{ BOOKINGS : receives
    EVENTS ||--o{ WAITLIST : has
    BOOKINGS ||--o{ PAYMENTS : has
    BOOKINGS ||--o{ TICKETS : issues
    TICKET_CATEGORIES ||--o{ TICKETS : classifies
    WAITLIST o|--o{ BOOKINGS : fulfills

    USERS {
        bigint id PK
        text email
        text role
        boolean is_active
    }
    USER_SESSIONS {
        bigint user_id FK
        text token_hash
        timestamp expires_at
    }
    VENUES {
        bigint id PK
        text name
        integer capacity
        numeric hourly_rate
    }
    EVENTS {
        bigint id PK
        bigint venue_id FK
        text status
        timestamp start_time
        timestamp end_time
    }
    TICKET_CATEGORIES {
        bigint id PK
        bigint event_id FK
        numeric price
        integer quantity
    }
    BOOKINGS {
        bigint id PK
        bigint user_id FK
        bigint event_id FK
        bigint waitlist_id FK
        numeric total_amount
        text status
    }
    PAYMENTS {
        bigint id PK
        bigint booking_id FK
        text status
        numeric amount
    }
    TICKETS {
        bigint id PK
        bigint booking_id FK
        bigint category_id FK
        text status
        timestamp checked_in_at
    }
    VENUE_HIRE_REQUESTS {
        bigint id PK
        bigint user_id FK
        bigint venue_id FK
        text status
    }
    WAITLIST {
        bigint id PK
        bigint user_id FK
        bigint event_id FK
        integer quantity
        text status
    }
    NOTIFICATIONS {
        bigint id PK
        bigint user_id FK
        boolean is_read
    }
    AGENT_MESSAGES {
        bigint id PK
        text sender
        text receiver
        text performative
        uuid conversation_id
    }
    AGENT_STATES {
        text agent_name PK
        jsonb state
        timestamp updated_at
    }
```

## Runtime lifecycle

`app.main` creates the agent runtime during FastAPI startup, optionally
restores persisted agent state, starts the waitlist expiry task for local
development, and cancels the task during shutdown. When the Vercel runtime
marker is present, the infinite task is not started; an authenticated
`POST /cron/waitlist-expiry` request sends the same `INFORM /
EXPIRE_WAITLIST` message through the MessageBus. PostgreSQL credentials are
supplied through environment variables; no credentials are stored in the
repository.
