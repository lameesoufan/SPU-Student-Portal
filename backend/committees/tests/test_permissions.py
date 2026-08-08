"""Permission-contract tests for committee management and scheduling views."""

from types import SimpleNamespace

import pytest
from rest_framework.permissions import IsAuthenticated

from committees import scheduler_views, views, wizard_views

pytestmark = pytest.mark.django_db


def request_for(user):
    return SimpleNamespace(user=user)


class AnonymousUser:
    is_authenticated = False
    role = None


@pytest.mark.parametrize(
    "permission_class",
    [views.IsDean, scheduler_views.IsDean],
)
class TestDeanPermissions:
    def test_rejects_anonymous(self, permission_class):
        assert permission_class().has_permission(request_for(AnonymousUser()), None) is False

    @pytest.mark.parametrize("role", ["student", "doctor", "hod"])
    def test_rejects_non_dean_roles(self, permission_class, user_factory, role):
        user = user_factory(role=role)
        assert permission_class().has_permission(request_for(user), None) is False

    def test_allows_dean(self, permission_class, dean):
        assert permission_class().has_permission(request_for(dean), None) is True


class TestDoctorOrDeanPermission:
    def test_rejects_anonymous(self):
        assert scheduler_views.IsDoctorOrDean().has_permission(
            request_for(AnonymousUser()), None
        ) is False

    def test_rejects_student(self, student):
        assert scheduler_views.IsDoctorOrDean().has_permission(request_for(student), None) is False

    @pytest.mark.parametrize("role", ["doctor", "hod", "dean"])
    def test_allows_doctor_hod_and_dean(self, user_factory, role):
        user = user_factory(role=role)
        assert scheduler_views.IsDoctorOrDean().has_permission(request_for(user), None) is True


DEAN_ONLY_VIEW_CLASSES = [
    views.CommitteeTemplateViewSet,
    views.CommitteeViewSet,
    views.DashboardView,
    views.DistributeView,
    views.ExportView,
    views.ProjectsAssignmentView,
    views.ExportProjectsAssignmentView,
    views.UpdateProjectSchedulesView,
    scheduler_views.RoomViewSet,
    scheduler_views.DoctorAvailabilityView,
    scheduler_views.DoctorDateExceptionView,
    scheduler_views.SolverSettingsViewSet,
    scheduler_views.SchedulingRunListView,
    scheduler_views.SchedulingRunDetailView,
    scheduler_views.SchedulePreviewView,
    scheduler_views.ScheduleApplyView,
    scheduler_views.ScheduleRejectView,
    wizard_views.SemesterSetupView,
    wizard_views.ScheduleAllView,
    wizard_views.ScheduleApplyAllView,
    wizard_views.ScheduleRejectAllView,
]


@pytest.mark.parametrize("view_class", DEAN_ONLY_VIEW_CLASSES)
def test_administrative_views_are_dean_only(view_class):
    permissions = view_class.permission_classes
    assert len(permissions) == 1
    assert issubclass(permissions[0], scheduler_views.IsDean) or issubclass(
        permissions[0], views.IsDean
    )


@pytest.mark.parametrize(
    "view_class",
    [scheduler_views.MyAvailabilityView, scheduler_views.MyDateExceptionView],
)
def test_self_service_availability_uses_doctor_or_dean_boundary(view_class):
    assert view_class.permission_classes == [scheduler_views.IsDoctorOrDean]


def test_doctor_schedule_requires_authentication_without_dean_only_gate():
    assert views.DoctorScheduleView.permission_classes == [IsAuthenticated]


@pytest.mark.parametrize(
    "view_class",
    [
        views.CommitteeTemplateViewSet,
        views.CommitteeViewSet,
        scheduler_views.RoomViewSet,
        scheduler_views.SolverSettingsViewSet,
    ],
)
def test_model_viewsets_do_not_fall_back_to_global_permissions(view_class):
    assert view_class.permission_classes
    assert view_class.permission_classes != [IsAuthenticated]


def test_wizard_reuses_scheduler_dean_permission_class():
    assert wizard_views.IsDean is scheduler_views.IsDean


@pytest.mark.parametrize(
    "view_class",
    [
        scheduler_views.DoctorAvailabilityView,
        scheduler_views.DoctorDateExceptionView,
        scheduler_views.SchedulingRunListView,
        scheduler_views.SchedulingRunDetailView,
        scheduler_views.SchedulePreviewView,
        scheduler_views.ScheduleApplyView,
        scheduler_views.ScheduleRejectView,
    ],
)
def test_scheduler_admin_views_use_scheduler_dean_permission(view_class):
    assert view_class.permission_classes == [scheduler_views.IsDean]
