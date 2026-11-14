
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status
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

from app.agents.runtime import create_agent_runtime
from app.agents.waitlist_scheduler import waitlist_expiry_loop


# ----------------------------------------
# APPLICATION LIFESPAN
# ----------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.agent_runtime = create_agent_runtime()

    message_bus = app.state.agent_runtime["message_bus"]

    print("EventSphere agents initialized successfully.")

    app.state.waitlist_expiry_task = asyncio.create_task(
        waitlist_expiry_loop(message_bus)
    )

    try:
        yield

    finally:
        app.state.waitlist_expiry_task.cancel()

        try:
            await app.state.waitlist_expiry_task
        except asyncio.CancelledError:
            print("Waitlist scheduler stopped.")


# ----------------------------------------
# FASTAPI APPLICATION
# ----------------------------------------

app = FastAPI(
    title="EventSphere API",
    description="University Event and Venue Booking System",
    version="1.0.0",
    lifespan=lifespan
)


# ----------------------------------------
# STATIC FILES
# ----------------------------------------

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)


# ----------------------------------------
# API ROUTERS
# ----------------------------------------

app.include_router(venue_router)
app.include_router(event_router)
app.include_router(ticket_router)
app.include_router(booking_router)
app.include_router(scanner_router)
app.include_router(dashboard_router)


# ----------------------------------------
# HOME PAGE
# ----------------------------------------

@app.get("/")
def home():
    return {
        "message": "Welcome to EventSphere",
        "status": "running",
        "docs": "/docs"
    }


# ----------------------------------------
# FRONTEND PAGES
# ----------------------------------------

@app.get("/ui")
def index_page():
    return FileResponse("app/templates/index.html")


@app.get("/ui/login")
def login_page():
    return FileResponse("app/templates/login.html")


@app.get("/ui/register")
def register_page():
    return FileResponse("app/templates/register.html")


@app.get("/ui/events")
def events_page():
    return FileResponse("app/templates/events.html")


@app.get("/ui/event/{event_id}")
def event_details_page(event_id: int):
    return FileResponse("app/templates/event_details.html")


@app.get("/ui/my-tickets")
def my_tickets_page():
    return FileResponse("app/templates/my_tickets.html")


@app.get("/ui/admin")
def admin_dashboard_page():
    return FileResponse("app/templates/admin_dashboard.html")

@app.get("/ui/manage-venues")
def manage_venues_page():
    return FileResponse("app/templates/venues_manage.html")

@app.get("/ui/manage-events")
def manage_events_page():
    return FileResponse("app/templates/events_manage.html")

@app.get("/ui/manage-ticket-categories/{event_id}")
def manage_ticket_categories_page(event_id: int):
    return FileResponse("app/templates/ticket_categories_manage.html")

# ----------------------------------------
# HEALTH CHECK
# ----------------------------------------

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "application": "EventSphere"
    }


@app.get("/db-health")
def database_health():
    try:
        result = check_database_connection()

        return {
            "status": "connected",
            "database": result["database_name"]
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {str(error)}"
        )


# ----------------------------------------
# AUTHENTICATION
# ----------------------------------------

@app.post("/auth/register")
def register(
    user_data: UserRegister
):
    return register_user(user_data)


@app.post("/auth/login")
def login(
    login_data: UserLogin
):
    return login_user(login_data)


@app.get("/auth/me")
def get_my_profile(
    current_user=Depends(get_current_user)
):
    return current_user


@app.post("/auth/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    current_user=Depends(get_current_user)
):
    return logout_user(credentials.credentials)


# ----------------------------------------
# ADMIN CHECK
# ----------------------------------------

@app.get("/auth/admin-check")
def admin_check(
    current_user=Depends(require_roles("ADMIN"))
):
    return {
        "message": "Admin access granted",
        "user": current_user
    }
