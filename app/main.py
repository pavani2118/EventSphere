
import asyncio
import hmac
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import check_database_connection
from app.schemas import UserRegister, UserLogin
from app.auth import register_user, login_user, logout_user
from app.dependencies import get_current_user, require_roles, bearer_scheme

from app.scanner import router as scanner_router
from app.bookings import router as booking_router
from app.ticket import router as ticket_router
from app.venues import router as venue_router
from app.events import router as event_router
from app.dashboard import router as dashboard_router
from app.venue_hire import router as venue_hire_router
from app.waitlist import router as waitlist_router
from app.notifications import router as notifications_router
from app.agents.runtime import create_agent_runtime
from app.agents.message import ACLMessage, Performative
from app.agents.waitlist_scheduler import waitlist_expiry_loop


logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"
TEMPLATE_DIR = BASE_DIR / "app" / "templates"


def is_vercel_environment():
    return os.getenv("VERCEL") == "1"


def get_agent_runtime():
    runtime = getattr(app.state, "agent_runtime", None)

    if runtime is None:
        runtime = create_agent_runtime(load_persisted_state=True)
        app.state.agent_runtime = runtime

    return runtime


# ========================================
# APPLICATION LIFESPAN
# ========================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.agent_runtime = create_agent_runtime(
        load_persisted_state=True
    )

    message_bus = app.state.agent_runtime["message_bus"]

    print("EventSphere agents initialized successfully.")

    app.state.waitlist_expiry_task = None

    if not is_vercel_environment():
        app.state.waitlist_expiry_task = asyncio.create_task(
            waitlist_expiry_loop(message_bus)
        )

    try:
        yield

    finally:
        if app.state.waitlist_expiry_task is not None:
            app.state.waitlist_expiry_task.cancel()

            try:
                await app.state.waitlist_expiry_task
            except asyncio.CancelledError:
                print("Waitlist scheduler stopped.")


# ========================================
# FASTAPI APPLICATION
# ========================================

app = FastAPI(
    title="EventSphere API",
    description="University Event and Venue Booking System",
    version="1.0.0",
    lifespan=lifespan
)


# ========================================
# STATIC FILES
# ========================================

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static"
)


# ========================================
# API ROUTERS
# ========================================
app.include_router(venue_router)
app.include_router(event_router)
app.include_router(ticket_router)
app.include_router(booking_router)
app.include_router(scanner_router)
app.include_router(dashboard_router)
app.include_router(venue_hire_router)
app.include_router(waitlist_router)
app.include_router(notifications_router)
# ========================================
# HOME PAGE
# ========================================

@app.get("/")
def home():
    return {
        "message": "Welcome to EventSphere!",
        "status": "running",
        "docs": "/docs"
    }


# ========================================
# FRONTEND PAGE ROUTES
# ========================================

@app.get("/ui")
def index_page():
    return FileResponse(TEMPLATE_DIR / "index.html")


@app.get("/ui/login")
def login_page():
    return FileResponse(TEMPLATE_DIR / "login.html")


@app.get("/ui/register")
def register_page():
    return FileResponse(TEMPLATE_DIR / "register.html")

@app.get("/ui/venue-hire")
def venue_hire_page():
    return FileResponse(TEMPLATE_DIR / "venue-hire.html")
@app.get("/ui/events")
def events_page():
    return FileResponse(TEMPLATE_DIR / "events.html")


@app.get("/ui/event/{event_id}")
def event_details_page(event_id: int):
    return FileResponse(TEMPLATE_DIR / "event_details.html")


@app.get("/ui/my-tickets")
def my_tickets_page():
    return FileResponse(TEMPLATE_DIR / "my_tickets.html")

@app.get("/ui/my-bookings")
def my_bookings_page():
    return FileResponse(TEMPLATE_DIR / "my_bookings.html")

@app.get("/ui/my-waitlist")
def my_waitlist_page():
    return FileResponse(TEMPLATE_DIR / "my_waitlist.html")

@app.get("/ui/notifications")
def notifications_page():
    return FileResponse(TEMPLATE_DIR / "notifications.html")


@app.get("/ui/admin")
def admin_dashboard_page():
    return FileResponse(TEMPLATE_DIR / "admin_dashboard.html")


@app.get("/ui/manage-venues")
def manage_venues_page():
    return FileResponse(TEMPLATE_DIR / "venues_manage.html")


@app.get("/ui/manage-events")
def manage_events_page():
    return FileResponse(TEMPLATE_DIR / "events_manage.html")


@app.get("/ui/manage-ticket-categories/{event_id}")
def manage_ticket_categories_page(event_id: int):
    return FileResponse(
        TEMPLATE_DIR / "ticket_categories_manage.html"
    )

# ========================================
# HEALTH CHECK
# ========================================

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "application": "EventSphere"
    }


@app.post("/cron/waitlist-expiry")
def trigger_waitlist_expiry(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    )
):
    cron_secret = os.getenv("CRON_SECRET")

    if not cron_secret:
        raise HTTPException(
            status_code=503,
            detail="CRON_SECRET is not configured."
        )

    if (
        credentials is None
        or not hmac.compare_digest(
            credentials.credentials,
            cron_secret
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid cron credentials.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    message = ACLMessage(
        sender="WaitlistScheduler",
        receiver="WaitlistAgent",
        performative=Performative.INFORM,
        content={
            "action": "EXPIRE_WAITLIST",
            "trigger": "EXTERNAL_CRON"
        }
    )
    response = get_agent_runtime()["message_bus"].send(message)

    if response.performative != Performative.AGREE:
        raise HTTPException(
            status_code=502,
            detail="Waitlist expiry processing failed."
        )

    return {
        "status": "completed",
        "expired_count": response.content.get("expired_count", 0),
        "conversation_id": response.conversation_id
    }


@app.get("/db-health")
def database_health():

    try:
        result = check_database_connection()

        return {
            "status": "connected",
            "database": result["database_name"]
        }

    except Exception:
        logger.exception("Database health check failed.")
        raise HTTPException(
            status_code=500,
            detail="Database connection failed."
        )


# ========================================
# AUTHENTICATION
# ========================================

# Registration: HTTP 201 Created
@app.post("/auth/register", status_code=201)
def register(user_data: UserRegister):

    return register_user(
        user_data.full_name,
        user_data.email,
        user_data.password
    )


# Login: HTTP 200 OK
@app.post("/auth/login")
def login(login_data: UserLogin):

    return login_user(
        login_data.email,
        login_data.password
    )


# Get logged-in user profile
@app.get("/auth/me")
def get_my_profile(
    current_user=Depends(get_current_user)
):
    return current_user


# Logout
@app.post("/auth/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    current_user=Depends(get_current_user)
):
    return logout_user(credentials.credentials)


# ========================================
# ADMIN CHECK
# ========================================

@app.get("/auth/admin-check")
def admin_check(
    current_user=Depends(require_roles("ADMIN"))
):
    return {
        "message": "Admin access granted",
        "user": current_user
    }
