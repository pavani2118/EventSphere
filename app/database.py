
import os
import psycopg
from psycopg.rows import dict_row


def get_db_connection():
    sslmode = os.getenv("PGSSLMODE")

    if sslmode is None:
        sslmode = "require" if os.getenv("VERCEL") == "1" else "prefer"

    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "eventsphere_db"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.environ["PGPASSWORD"],
        sslmode=sslmode,
        row_factory=dict_row
    )


def check_database_connection():
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database() AS database_name")
            result = cursor.fetchone()

    return result
