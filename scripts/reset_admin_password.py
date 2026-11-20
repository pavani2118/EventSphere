import getpass
from pathlib import Path

from app.security import hash_password


ADMIN_EMAIL = "admin@gmail.com"
OUTPUT_PATH = (
    Path.home()
    / ".copilot"
    / "session-state"
    / "d2a6e211-52cc-45c7-b905-8800134d4db0"
    / "files"
    / "reset_admin_password.sql"
)


password = getpass.getpass("Enter the new admin password: ")
confirmation = getpass.getpass("Confirm the new admin password: ")

if password != confirmation:
    raise SystemExit("Passwords do not match.")

if len(password) < 8:
    raise SystemExit("Password must contain at least 8 characters.")

password_hash = hash_password(password)

sql = (
    "BEGIN;\n\n"
    "UPDATE users\n"
    "SET password_hash = "
    f"'{password_hash}'\n"
    f"WHERE email = '{ADMIN_EMAIL}';\n\n"
    "SELECT id, email, role, is_active\n"
    "FROM users\n"
    f"WHERE email = '{ADMIN_EMAIL}';\n\n"
    "COMMIT;\n"
)

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.write_text(sql, encoding="utf-8")
print(f"Reset SQL written to {OUTPUT_PATH}")
