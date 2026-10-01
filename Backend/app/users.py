import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.history import backend_directory
from app.schemas import AccountSessionResponse, AuthenticatedUser

PASSWORD_ITERATIONS = 210_000


class UserAlreadyExistsError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


class UserAccountStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._users: list[dict[str, str | None]] = []
        self._sessions: list[dict[str, str]] = []
        self._lock = Lock()
        self._load()

    @classmethod
    def from_environment(cls) -> "UserAccountStore":
        return cls(path=user_account_store_path())

    def register(
        self,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> AccountSessionResponse:
        normalized_email = normalize_email(email)
        salt, password_hash = hash_password(password)

        with self._lock:
            if self._user_by_email_locked(normalized_email) is not None:
                raise UserAlreadyExistsError("Account already exists.")

            user_id = str(uuid4())
            user = {
                "id": user_id,
                "email": normalized_email,
                "displayName": normalize_display_name(display_name),
                "travelerId": f"user:{user_id}",
                "passwordSalt": salt,
                "passwordHash": password_hash,
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
            self._users.append(user)
            session = self._create_session_locked(user)
            self._persist_locked()

        return session

    def login(self, email: str, password: str) -> AccountSessionResponse:
        normalized_email = normalize_email(email)

        with self._lock:
            user = self._user_by_email_locked(normalized_email)
            if user is None or not verify_password(password, user):
                raise InvalidCredentialsError("Invalid email or password.")

            session = self._create_session_locked(user)
            self._persist_locked()

        return session

    def authenticate(self, access_token: str | None) -> AuthenticatedUser | None:
        if not access_token:
            return None

        token_hash = hash_access_token(access_token)
        with self._lock:
            session = next(
                (
                    item
                    for item in self._sessions
                    if item.get("tokenHash") == token_hash
                ),
                None,
            )
            if session is None:
                return None

            user = self._user_by_id_locked(session["userId"])
            if user is None:
                return None

            return authenticated_user(user)

    def _user_by_email_locked(
        self,
        email: str,
    ) -> dict[str, str | None] | None:
        return next(
            (user for user in self._users if user.get("email") == email),
            None,
        )

    def _user_by_id_locked(
        self,
        user_id: str,
    ) -> dict[str, str | None] | None:
        return next(
            (user for user in self._users if user.get("id") == user_id),
            None,
        )

    def _create_session_locked(
        self,
        user: dict[str, str | None],
    ) -> AccountSessionResponse:
        access_token = secrets.token_urlsafe(32)
        self._sessions.append(
            {
                "tokenHash": hash_access_token(access_token),
                "userId": require_string(user, "id"),
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
        )
        return AccountSessionResponse(
            accessToken=access_token,
            user=authenticated_user(user),
        )

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        users = payload.get("users", []) if isinstance(payload, dict) else []
        sessions = payload.get("sessions", []) if isinstance(payload, dict) else []

        if isinstance(users, list):
            self._users = [
                user for user in users if isinstance(user, dict)
            ]

        if isinstance(sessions, list):
            self._sessions = [
                session for session in sessions if isinstance(session, dict)
            ]

    def _persist_locked(self) -> None:
        if self._path is None:
            return

        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sessions": self._sessions,
            "users": self._users,
        }
        temporary_path = self._path.with_name(f"{self._path.name}.tmp")
        temporary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary_path.replace(self._path)


def user_account_store_path() -> Path:
    configured_path = os.environ.get("USER_ACCOUNT_STORE_PATH", "").strip()
    if configured_path:
        path = Path(configured_path)
        if not path.is_absolute():
            path = backend_directory() / path

        return path

    return backend_directory() / ".data" / "user_accounts.json"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_display_name(display_name: str | None) -> str | None:
    normalized = (display_name or "").strip()
    return normalized or None


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    normalized_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(normalized_salt),
        PASSWORD_ITERATIONS,
    ).hex()
    return normalized_salt, digest


def verify_password(password: str, user: dict[str, str | None]) -> bool:
    salt = require_string(user, "passwordSalt")
    expected_hash = require_string(user, "passwordHash")
    _, actual_hash = hash_password(password, salt=salt)
    return secrets.compare_digest(actual_hash, expected_hash)


def hash_access_token(access_token: str) -> str:
    return hashlib.sha256(access_token.encode("utf-8")).hexdigest()


def authenticated_user(user: dict[str, str | None]) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=require_string(user, "id"),
        email=require_string(user, "email"),
        displayName=user.get("displayName"),
        travelerId=require_string(user, "travelerId"),
    )


def require_string(user: dict[str, str | None], key: str) -> str:
    value = user.get(key)
    if not isinstance(value, str) or not value:
        raise InvalidCredentialsError("Stored account data is invalid.")

    return value
