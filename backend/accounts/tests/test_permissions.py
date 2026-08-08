"""Authorization unit tests for accounts permissions."""

from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser

from accounts.permissions import IsDeanOrAdmin


pytestmark = [pytest.mark.unit, pytest.mark.security, pytest.mark.django_db]


def permission_result(user):
    request = SimpleNamespace(user=user)
    return IsDeanOrAdmin().has_permission(request, view=None)


class TestIsDeanOrAdmin:
    def test_rejects_anonymous_user(self):
        assert permission_result(AnonymousUser()) is False

    @pytest.mark.parametrize("fixture_name", ["student", "doctor", "hod"])
    def test_rejects_non_dean_roles(self, fixture_name, request):
        user = request.getfixturevalue(fixture_name)

        assert permission_result(user) is False

    def test_allows_authenticated_dean(self, dean):
        assert dean.is_authenticated is True
        assert permission_result(dean) is True

    def test_permission_does_not_depend_only_on_superuser_flag(
        self,
        user_factory,
        django_user_model,
    ):
        user = user_factory(role="student", username="legacy_superuser")
        django_user_model.objects.filter(pk=user.pk).update(
            is_superuser=True,
            is_staff=True,
            role="student",
        )
        user.refresh_from_db()

        assert user.is_superuser is True
        assert user.role == "student"
        assert permission_result(user) is False
