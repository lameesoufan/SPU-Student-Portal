"""Prepare realistic identities and JWTs for Locust API load tests.

Run this only against a development/staging database. It creates or refreshes a
pool of dedicated Student users and writes short-lived runtime credentials to a
local JSON file that is ignored by Git. Doctor/HoD/Dean accounts are not
created: they are validated from load-tests/.env and their JWTs are generated
locally as well.

Generating JWTs locally is intentional: the read/stress suite measures the
authenticated API and should not be dominated by the separate login throttle.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

LOAD_DIR = Path(__file__).resolve().parent
BACKEND_DIR = LOAD_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
load_dotenv(LOAD_DIR / ".env")

import django  # noqa: E402

django.setup()

from django.contrib.auth import authenticate  # noqa: E402
from django.db import transaction  # noqa: E402
from rest_framework_simplejwt.tokens import RefreshToken  # noqa: E402

from accounts.models import DEPARTMENTS, User  # noqa: E402

TOKEN_FILE = LOAD_DIR / os.getenv("LOAD_TOKEN_FILE", ".runtime_tokens.json")


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value == "CHANGE_ME":
        raise SystemExit(
            f"[load-tests] {name} is missing. Set it in {LOAD_DIR / '.env'}."
        )
    return value


def _jwt_for(user: User) -> str:
    if not user.is_active:
        raise SystemExit(f"[load-tests] User {user.username!r} is inactive.")
    return str(RefreshToken.for_user(user).access_token)


def _validate_existing_role(role: str) -> dict[str, str]:
    prefix = f"LOAD_{role.upper()}"
    username = _required_env(f"{prefix}_USERNAME")
    password = _required_env(f"{prefix}_PASSWORD")
    user = authenticate(username=username, password=password)
    if user is None:
        raise SystemExit(
            f"[load-tests] Cannot authenticate {role} account {username!r}. "
            "Check the username/password in load-tests/.env."
        )
    if str(user.role).lower() != role:
        raise SystemExit(
            f"[load-tests] {username!r} has role {user.role!r}, expected {role!r}."
        )
    return {"username": username, "token": _jwt_for(user)}


def _prepare_students() -> list[dict[str, str]]:
    count = int(os.getenv("LOAD_STUDENT_COUNT", "220"))
    if count < 1:
        raise SystemExit("[load-tests] LOAD_STUDENT_COUNT must be at least 1.")

    prefix = os.getenv("LOAD_STUDENT_PREFIX", "load_student_").strip() or "load_student_"
    password = _required_env("LOAD_STUDENT_PASSWORD")
    department = os.getenv("LOAD_STUDENT_DEPARTMENT", "software_engineering").strip()
    valid_departments = {key for key, _label in DEPARTMENTS}
    if department not in valid_departments:
        raise SystemExit(
            f"[load-tests] Invalid LOAD_STUDENT_DEPARTMENT={department!r}. "
            f"Use one of: {', '.join(sorted(valid_departments))}."
        )

    width = max(3, len(str(count)))
    prepared: list[dict[str, str]] = []

    for number in range(1, count + 1):
        username = f"{prefix}{number:0{width}d}"
        with transaction.atomic():
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "role": "student",
                    "department": department,
                    "is_active": True,
                    "must_change_password": False,
                    "must_change_username": False,
                },
            )

            changed_fields: list[str] = []
            desired = {
                "role": "student",
                "department": department,
                "is_active": True,
                "must_change_password": False,
                "must_change_username": False,
            }
            for field, value in desired.items():
                if getattr(user, field) != value:
                    setattr(user, field, value)
                    changed_fields.append(field)

            if created or not user.check_password(password):
                user.set_password(password)
                changed_fields.append("password")

            if changed_fields:
                user.save(update_fields=sorted(set(changed_fields)))

        prepared.append({"username": username, "token": _jwt_for(user)})

    return prepared


def main() -> None:
    print("[load-tests] Preparing dedicated Student identity pool...")
    students = _prepare_students()

    print("[load-tests] Validating Doctor / HoD / Dean accounts...")
    roles = {
        role: _validate_existing_role(role)
        for role in ("doctor", "hod", "dean")
    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "students": students,
        "roles": roles,
    }
    TOKEN_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(
        f"[load-tests] Ready: {len(students)} Student identities + "
        "Doctor/HoD/Dean JWTs."
    )
    print(f"[load-tests] Runtime token file: {TOKEN_FILE}")


if __name__ == "__main__":
    main()
