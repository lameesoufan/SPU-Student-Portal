"""Permission-matrix tests for workflow endpoints."""

from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser

from workflow.permissions import IsHod, IsHodOrDoctor, IsStudent


pytestmark = [pytest.mark.django_db, pytest.mark.unit]


ROLE_CASES = [
    (None, False),
    ("student", False),
    ("doctor", True),
    ("hod", True),
    ("dean", False),
]


def make_request(user):
    return SimpleNamespace(user=user)


def make_role_user(user_factory, role):
    if role is None:
        return AnonymousUser()
    department = None if role == "dean" else "software_engineering"
    return user_factory(role=role, department=department)


class TestIsHodOrDoctor:
    @pytest.mark.parametrize(("role", "expected"), ROLE_CASES)
    def test_permission_matrix(self, user_factory, role, expected):
        user = make_role_user(user_factory, role)

        result = IsHodOrDoctor().has_permission(make_request(user), view=None)

        assert result is expected


class TestIsHod:
    @pytest.mark.parametrize(
        ("role", "expected"),
        [
            (None, False),
            ("student", False),
            ("doctor", False),
            ("hod", True),
            ("dean", False),
        ],
    )
    def test_permission_matrix(self, user_factory, role, expected):
        user = make_role_user(user_factory, role)

        result = IsHod().has_permission(make_request(user), view=None)

        assert result is expected


class TestIsStudent:
    @pytest.mark.parametrize(
        ("role", "expected"),
        [
            (None, False),
            ("student", True),
            ("doctor", False),
            ("hod", False),
            ("dean", False),
        ],
    )
    def test_permission_matrix(self, user_factory, role, expected):
        user = make_role_user(user_factory, role)

        result = IsStudent().has_permission(make_request(user), view=None)

        assert result is expected
