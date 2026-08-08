"""Shared utilities for the University Project Management Locust suite.

The read/stress profiles use JWTs prepared by prepare_load_users.py. Student
virtual users receive distinct dedicated identities, while Doctor/HoD/Dean use
one dedicated account per role. This prevents an artificial per-user throttle
bottleneck while keeping the application's real throttling enabled.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from gevent.lock import Semaphore
from locust import HttpUser, events
from locust.exception import StopUser

LOAD_DIR = Path(__file__).resolve().parent
load_dotenv(LOAD_DIR / ".env")
TOKEN_FILE = LOAD_DIR / os.getenv("LOAD_TOKEN_FILE", ".runtime_tokens.json")

_STUDENT_LOCK = Semaphore()
_STUDENT_INDEX = 0
_TOKEN_BUNDLE: dict[str, Any] | None = None


def _load_token_bundle() -> dict[str, Any]:
    global _TOKEN_BUNDLE
    if _TOKEN_BUNDLE is not None:
        return _TOKEN_BUNDLE
    if not TOKEN_FILE.exists():
        raise RuntimeError(
            "Load-test runtime tokens are missing. Run "
            f"`python {LOAD_DIR / 'prepare_load_users.py'}` first, or use run-load.ps1/sh."
        )
    try:
        payload = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read load-test token file {TOKEN_FILE}: {exc}") from exc
    if not isinstance(payload.get("students"), list) or not isinstance(payload.get("roles"), dict):
        raise RuntimeError(f"Invalid token bundle format in {TOKEN_FILE}.")
    _TOKEN_BUNDLE = payload
    return payload


def _next_student_identity() -> dict[str, str]:
    global _STUDENT_INDEX
    bundle = _load_token_bundle()
    students = bundle.get("students") or []
    with _STUDENT_LOCK:
        if _STUDENT_INDEX >= len(students):
            raise StopUser(
                "Student identity pool exhausted. Increase LOAD_STUDENT_COUNT in load-tests/.env "
                "and rerun the profile."
            )
        identity = students[_STUDENT_INDEX]
        _STUDENT_INDEX += 1
    return identity


def _role_identity(role: str) -> dict[str, str]:
    bundle = _load_token_bundle()
    identity = (bundle.get("roles") or {}).get(role)
    if not identity:
        raise StopUser(
            f"No prepared JWT for role {role!r}. Run prepare_load_users.py again."
        )
    return identity


class AuthenticatedApiUser(HttpUser):
    """Base user that attaches a prepared JWT before any API task runs."""

    abstract = True
    host = os.getenv("LOAD_TEST_HOST", "http://127.0.0.1:8000")
    role = ""
    access_token = ""
    identity_username = ""

    def on_start(self) -> None:
        identity = _next_student_identity() if self.role == "student" else _role_identity(self.role)
        token = str(identity.get("token", "")).strip()
        username = str(identity.get("username", "")).strip()
        if not token:
            raise StopUser(f"Prepared identity {username or self.role!r} has no JWT.")
        self.access_token = token
        self.identity_username = username
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    def get_json(
        self,
        path: str,
        *,
        name: str | None = None,
        expected: tuple[int, ...] = (200,),
        params: dict[str, Any] | None = None,
    ) -> Any | None:
        with self.client.get(
            path,
            params=params,
            name=name or f"GET {path}",
            catch_response=True,
        ) as response:
            if response.status_code not in expected:
                response.failure(f"unexpected HTTP {response.status_code}")
                return None
            try:
                data = response.json()
            except ValueError:
                response.failure("expected JSON response")
                return None
            response.success()
            return data


@events.test_start.add_listener
def _validate_runtime_identities(environment, **_kwargs) -> None:
    try:
        bundle = _load_token_bundle()
    except RuntimeError as exc:
        print(f"\n[load-tests] {exc}\n")
        environment.runner.quit()
        environment.process_exit_code = 2
        return

    student_count = len(bundle.get("students") or [])
    roles = bundle.get("roles") or {}
    missing_roles = [role for role in ("doctor", "hod", "dean") if not roles.get(role)]
    if missing_roles:
        print(f"\n[load-tests] Missing prepared roles: {', '.join(missing_roles)}\n")
        environment.runner.quit()
        environment.process_exit_code = 2
        return
    print(f"\n[load-tests] Prepared identities: {student_count} students + doctor/hod/dean.\n")


@events.quitting.add_listener
def _quality_gate(environment, **_kwargs) -> None:
    """Return non-zero when the configured performance gate fails."""

    stats = environment.stats.total
    if stats.num_requests <= 0:
        return

    max_failure_ratio = float(os.getenv("LOAD_MAX_FAILURE_RATIO", "0.02"))
    max_p95_ms = int(os.getenv("LOAD_MAX_P95_MS", "800"))
    max_p99_ms = int(os.getenv("LOAD_MAX_P99_MS", "1500"))

    p95 = stats.get_response_time_percentile(0.95) or 0
    p99 = stats.get_response_time_percentile(0.99) or 0

    failures: list[str] = []
    if stats.fail_ratio > max_failure_ratio:
        failures.append(f"failure ratio {stats.fail_ratio:.2%} > {max_failure_ratio:.2%}")
    if p95 > max_p95_ms:
        failures.append(f"p95 {p95:.0f} ms > {max_p95_ms} ms")
    if p99 > max_p99_ms:
        failures.append(f"p99 {p99:.0f} ms > {max_p99_ms} ms")

    if failures:
        environment.process_exit_code = 1
        print("\n[load-tests] PERFORMANCE GATE FAILED: " + "; ".join(failures))
    else:
        print(
            "\n[load-tests] Performance gate passed: "
            f"failures={stats.fail_ratio:.2%}, p95={p95:.0f}ms, p99={p99:.0f}ms"
        )
