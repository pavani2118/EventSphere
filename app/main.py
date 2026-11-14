
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    status
)
from fastapi.security import HTTPAuthorizationCredentials

from app.database import check_database_connection
from app.schemas import UserRegister, UserLogin
from app.auth import register_user, login_user, logout_user
from app.dependencies import (
    get_current_user,
    require_roles,
    bearer_scheme
)


app = FastAPI(
    title="EventSphere API",
    description="University Event and Venue Booking Platform",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "message": "Welcome to EventSphere!",
        "status": "Running successfully"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


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


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
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


@app.post("/auth/login")
def login(data: UserLogin):
    return login_user(
        data.email.strip().lower(),
        data.password
    )


@app.get("/auth/me")
def my_profile(current_user=Depends(get_current_user)):
    return current_user


@app.post("/auth/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    current_user=Depends(get_current_user)
):
    logout_user(credentials.credentials)

    return {"message": "Logged out successfully"}


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
