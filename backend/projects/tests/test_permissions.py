"""Unit tests for role-based permissions in the projects application."""

from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser

from projects.permissions import IsDoctor, IsDoctorOrHod, IsHod, IsStudent


pytestmark = pytest.mark.unit


def request_for(user):
    return SimpleNamespace(user=user)


@pytest.mark.parametrize(
    "permission_class",
    [IsDoctor, IsDoctorOrHod, IsStudent, IsHod],
)
def test_project_permissions_reject_anonymous_users(permission_class):
    permission = permission_class()

    assert permission.has_permission(request_for(AnonymousUser()), None) is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("permission_class", "role", "expected"),
    [
        (IsDoctor, "student", False),
        (IsDoctor, "doctor", True),
        (IsDoctor, "hod", True),
        (IsDoctor, "dean", False),
        (IsDoctorOrHod, "student", False),
        (IsDoctorOrHod, "doctor", True),
        (IsDoctorOrHod, "hod", True),
        (IsDoctorOrHod, "dean", False),
        (IsStudent, "student", True),
        (IsStudent, "doctor", False),
        (IsStudent, "hod", False),
        (IsStudent, "dean", False),
        (IsHod, "student", False),
        (IsHod, "doctor", False),
        (IsHod, "hod", True),
        (IsHod, "dean", False),
    ],
)
def test_project_permissions_enforce_expected_role(
    permission_class,
    role,
    expected,
    user_factory,
):
    user = user_factory(
        role=role,
        department=None if role == "dean" else "software_engineering",
        username=f"permission_{permission_class.__name__.lower()}_{role}",
    )

    assert permission_class().has_permission(request_for(user), None) is expected
