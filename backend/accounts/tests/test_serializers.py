"""Unit and component tests for accounts serializers."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import AuthenticationFailed

from accounts.serializers import (
    CustomTokenObtainPairSerializer,
    CustomTokenObtainPairView,
    ImportExcelSerializer,
    UserSerializer,
)
from accounts.throttles import LoginRateThrottle


pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestCustomTokenObtainPairSerializer:
    def test_refresh_token_contains_expected_user_claims(self, user_factory):
        user = user_factory(
            username="claims_doctor",
            role="doctor",
            department="artificial_intelligence",
            must_change_password=True,
            must_change_username=True,
        )

        token = CustomTokenObtainPairSerializer.get_token(user)

        assert token["role"] == "doctor"
        assert token["username"] == "claims_doctor"
        assert token["department"] == "artificial_intelligence"
        assert token["must_change_password"] is True
        assert token["must_change_username"] is True
        assert "password" not in token.payload
        assert "email" not in token.payload

    def test_valid_credentials_return_access_and_refresh_tokens(self, student):
        serializer = CustomTokenObtainPairSerializer(
            data={
                "username": student.username,
                "password": "Strong-Test-Password-2026!",
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["access"]
        assert serializer.validated_data["refresh"]

    def test_invalid_password_is_rejected(self, student):
        serializer = CustomTokenObtainPairSerializer(
            data={
                "username": student.username,
                "password": "Incorrect-Password-2026!",
            }
        )

        with pytest.raises(AuthenticationFailed):
            serializer.is_valid(raise_exception=True)

    def test_token_view_uses_custom_serializer_and_login_throttle(self):
        assert CustomTokenObtainPairView.serializer_class is CustomTokenObtainPairSerializer
        assert CustomTokenObtainPairView.throttle_classes == [LoginRateThrottle]


class TestUserSerializer:
    def test_representation_contains_only_public_account_fields(self, doctor):
        data = UserSerializer(doctor).data

        assert data == {
            "id": doctor.pk,
            "username": doctor.username,
            "email": doctor.email,
            "role": "doctor",
        }

    def test_representation_excludes_sensitive_and_internal_fields(self, student):
        data = UserSerializer(student).data

        excluded_fields = {
            "password",
            "is_superuser",
            "is_staff",
            "is_active",
            "department",
            "must_change_password",
            "must_change_username",
            "has_changed_username",
        }

        assert excluded_fields.isdisjoint(data.keys())

    def test_rejects_an_unknown_role(self):
        serializer = UserSerializer(
            data={
                "username": "invalid_role_user",
                "email": "invalid@example.com",
                "role": "administrator",
            }
        )

        assert serializer.is_valid() is False
        assert "role" in serializer.errors

    def test_username_is_required_when_deserializing(self):
        serializer = UserSerializer(
            data={
                "email": "missing.username@example.com",
                "role": "student",
            }
        )

        assert serializer.is_valid() is False
        assert "username" in serializer.errors


class TestImportExcelSerializer:
    @pytest.mark.parametrize("role", ["student", "doctor"])
    def test_accepts_supported_roles_and_non_empty_file(self, role):
        upload = SimpleUploadedFile(
            "users.xlsx",
            b"placeholder spreadsheet content",
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        serializer = ImportExcelSerializer(data={"file": upload, "role": role})

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["role"] == role
        assert serializer.validated_data["file"].name == "users.xlsx"

    @pytest.mark.parametrize("role", ["dean", "hod", "admin", ""])
    def test_rejects_unsupported_roles(self, role):
        upload = SimpleUploadedFile("users.csv", b"username,email\nstudent,student@example.com")
        serializer = ImportExcelSerializer(data={"file": upload, "role": role})

        assert serializer.is_valid() is False
        assert "role" in serializer.errors

    def test_file_is_required(self):
        serializer = ImportExcelSerializer(data={"role": "student"})

        assert serializer.is_valid() is False
        assert "file" in serializer.errors

    def test_empty_file_is_rejected(self):
        upload = SimpleUploadedFile("empty.xlsx", b"")
        serializer = ImportExcelSerializer(data={"file": upload, "role": "student"})

        assert serializer.is_valid() is False
        assert "file" in serializer.errors
