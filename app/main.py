import asyncio

from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    status
)

from fastapi.security import HTTPAuthorizationCredentials

# Database
from app.database import check_database_connection

# Authentication schemas
from app.schemas import UserRegister, UserLogin

# Authentication functions
from app.auth import (
    register_user,
    login_user,
    logout_user
)

# Authentication dependencies
from app.dependencies import (
    get_current_user,
    require_roles,
    bearer_scheme
)

# Application routers
from app.scanner import router as scanner_router
from app.bookings import router as booking_router
from app.ticket import router as ticket_router
from app.venues import router as venue_router
from app.events import router as event_router

# Agent runtime
from app.agents.runtime import create_agent_runtime

# Waitlist scheduler
from app.agents.waitlist_scheduler import waitlist_expiry_loop


# Initialize agents and scheduler when FastAPI starts.
@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.agent_runtime = create_agent_runtime()

    message_bus = app.state.agent_runtime["message_bus"]

    print("EventSphere Agent System Started")
    print("Registered Agents:")

    for agent_name in message_bus.agents:
        print(f"- {agent_name}")

    # Start automatic waitlist expiry scheduler.
    app.state.waitlist_expiry_task = asyncio.create_task(
        waitlist_expiry_loop(message_bus)
    )

    print("Waitlist Expiry Scheduler Started")

    try:
        yield

    finally:

        # Stop scheduler during application shutdown.
        app.state.waitlist_expiry_task.cancel()

        try:
            await app.state.waitlist_expiry_task

        except asyncio.CancelledError:
            pass

        print("EventSphere Agent System Stopped")


# Create FastAPI application.
app = FastAPI(
    title="EventSphere API",
    description="University Event and Venue Booking Platform",
    version="1.0.0",
    lifespan=lifespan
)


# Register routers.
app.include_router(venue_router)
app.include_router(event_router)
app.include_router(ticket_router)
app.include_router(booking_router)
app.include_router(scanner_router)


# Home endpoint.
@app.get("/")
def home():

    return {
        "message": "Welcome to EventSphere!",
        "status": "Running successfully"
    }


# Health check endpoint.
@app.get("/health")
def health_check():

    return {
        "status": "healthy"
    }


# Database health check.
@app.get("/db-health")
def database_health():

    try:
        result = check_database_connection()

        return {
            "status": "connected",
            "database": result["database_name"]
        }

    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Database connection failed"
        )


# User registration.
@app.post(
    "/auth/register",
    status_code=status.HTTP_201_CREATED
)
def register(data: UserRegister):

    user = register_user(
        data.full_name,
        data.email,
        data.password
    )

    return {
        "message": "Registration successful",
        "user": user
    }


# User login.
@app.post("/auth/login")
def login(data: UserLogin):

    return login_user(
        data.email.strip().lower(),
        data.password
    )


# Get current user profile.
@app.get("/auth/me")
def my_profile(
    current_user=Depends(get_current_user)
):

    return current_user


# User logout.
@app.post("/auth/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    current_user=Depends(get_current_user)
):

    logout_user(credentials.credentials)

    return {
        "message": "Logged out successfully"
    }


# Admin and organiser access check.
@app.get("/auth/admin-check")
def admin_check(
    current_user=Depends(
        require_roles("ADMIN", "ORGANISER")
    )
):

    return {
        "message": "Access granted",
        "user": current_user
    }