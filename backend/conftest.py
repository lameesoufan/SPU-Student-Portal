"""Shared pytest fixtures for all backend applications."""

from collections.abc import Callable

import pytest
from rest_framework.test import APIClient


TEST_PASSWORD = 'Strong-Test-Password-2026!'


@pytest.fixture
def api_client() -> APIClient:
    """Return an unauthenticated DRF client."""
    return APIClient()


@pytest.fixture
def user_factory(django_user_model) -> Callable:
    """Create users with safe defaults while allowing every field to be overridden."""
    sequence = {'value': 0}

    def create_user(**overrides):
        sequence['value'] += 1
        number = sequence['value']
        role = overrides.pop('role', 'student')
        username = overrides.pop('username', f'{role}_{number}')
        email = overrides.pop('email', f'{username}@example.com')
        password = overrides.pop('password', TEST_PASSWORD)

        return django_user_model.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
            **overrides,
        )

    return create_user


@pytest.fixture
def student(user_factory):
    return user_factory(role='student', department='software_engineering')


@pytest.fixture
def doctor(user_factory):
    return user_factory(role='doctor', department='software_engineering')


@pytest.fixture
def hod(user_factory):
    return user_factory(role='hod', department='software_engineering')


@pytest.fixture
def dean(user_factory):
    return user_factory(role='dean', department=None)


def _authenticated_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def student_client(student) -> APIClient:
    return _authenticated_client(student)


@pytest.fixture
def doctor_client(doctor) -> APIClient:
    return _authenticated_client(doctor)


@pytest.fixture
def hod_client(hod) -> APIClient:
    return _authenticated_client(hod)


@pytest.fixture
def dean_client(dean) -> APIClient:
    return _authenticated_client(dean)
