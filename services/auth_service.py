"""Authentication for the three roles: admin, operator, citizen."""
from __future__ import annotations

from database.models import User
from utils.security import verify_password


def login(session, username: str, password: str) -> User | None:
    user = session.query(User).filter(User.username == username).first()
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def register_user(session, username: str, password: str, full_name: str, role: str, email: str | None = None) -> User:
    from utils.security import hash_password

    if role not in ("admin", "operator", "citizen"):
        raise ValueError(f"Invalid role: {role!r}")
    if session.query(User).filter(User.username == username).first() is not None:
        raise ValueError("Username already exists.")
    user = User(username=username, password_hash=hash_password(password), full_name=full_name, email=email, role=role)
    session.add(user)
    session.flush()
    return user


def register_citizen(session, username: str, password: str, full_name: str, email: str | None = None) -> User:
    return register_user(session, username, password, full_name, role="citizen", email=email)
