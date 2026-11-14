
from fastapi import FastAPI, HTTPException
from app.database import check_database_connection

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
    return {
        "status": "healthy"
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
            detail="Database connection failed. Check PostgreSQL settings."
        )
