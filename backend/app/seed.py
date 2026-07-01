"""Database seeding — inserts demo users on first run, skips if data exists."""

import bcrypt

from app.database import get_db_connection


def _hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

DEMO_USERS = [
    {
        "email": "admin@company.com",
        "password": "admin123",
        "full_name": "Admin User",
        "role": "hr_admin",
        "department": "hr",
    },
    {
        "email": "john@company.com",
        "password": "john123",
        "full_name": "John Doe",
        "role": "employee",
        "department": "engineering",
    },
    {
        "email": "sarah@company.com",
        "password": "sarah123",
        "full_name": "Sarah Smith",
        "role": "manager",
        "department": "sales",
    },
    {
        "email": "priya@company.com",
        "password": "priya123",
        "full_name": "Priya Sharma",
        "role": "employee",
        "department": "hr",
    },
]


async def seed_users() -> None:
    """Insert demo users if the ``users`` table is empty.

    Idempotent — checks for existing rows before inserting anything.
    Uses parameterized queries (``$1``, ``$2``, …) — no string formatting.
    """
    conn = await get_db_connection()
    try:
        # Check whether users already exist
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
        if count > 0:
            print(f"{count} users already exist, skipping seed")
            return

        # Insert demo users with bcrypt-hashed passwords
        for user in DEMO_USERS:
            hashed = _hash_password(user["password"])
            await conn.execute(
                "INSERT INTO users (email, hashed_password, full_name, role, department) "
                "VALUES ($1, $2, $3, $4, $5)",
                user["email"],
                hashed,
                user["full_name"],
                user["role"],
                user["department"],
            )
            print(f"Created user: {user['email']}")

        print(f"{len(DEMO_USERS)} demo users seeded")
    finally:
        await conn.close()
