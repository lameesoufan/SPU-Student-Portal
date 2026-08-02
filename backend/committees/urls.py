"""URL configuration for the committees app."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CommitteeTemplateViewSet,
    CommitteeViewSet,
    DashboardView,
    DistributeView,
    ExportView,
    ProjectsAssignmentView,
    ExportProjectsAssignmentView,
    UpdateProjectSchedulesView,
    DoctorScheduleView,
)
from .scheduler_views import (
    RoomViewSet,
    DoctorAvailabilityView,
    DoctorDateExceptionView,
    MyAvailabilityView,
    MyDateExceptionView,
    SolverSettingsViewSet,
    SchedulingRunListView,
    SchedulingRunDetailView,
)
# Preview/Apply/Reject endpoints (added in Phase 2)
try:
    from .scheduler_views import SchedulePreviewView, ScheduleApplyView, ScheduleRejectView
    _HAS_SCHEDULE_VIEWS = True
except ImportError:
    _HAS_SCHEDULE_VIEWS = False

# Wizard endpoints (Phase 4 — unified setup + scheduling)
try:
    from .wizard_views import (
        SemesterSetupView, ScheduleAllView,
        ScheduleApplyAllView, ScheduleRejectAllView,
    )
    _HAS_WIZARD_VIEWS = True
except ImportError:
    _HAS_WIZARD_VIEWS = False


router = DefaultRouter()
router.register(r'templates',       CommitteeTemplateViewSet, basename='committee-template')
router.register(r'committees',      CommitteeViewSet,         basename='committee')
router.register(r'rooms',           RoomViewSet,              basename='room')
router.register(r'solver-settings', SolverSettingsViewSet,    basename='solver-settings')


urlpatterns = [
    # Existing endpoints
    path('',                                include(router.urls)),
    path('dashboard/',                      DashboardView.as_view(),  name='committee-dashboard'),
    path('distribute/',                     DistributeView.as_view(), name='committee-distribute'),
    path('export/',                         ExportView.as_view(),     name='committee-export'),
    path('projects-assignment/',            ProjectsAssignmentView.as_view(), name='projects-assignment'),
    path('projects-assignment/export/',     ExportProjectsAssignmentView.as_view(), name='projects-assignment-export'),
    path('update-schedules/',               UpdateProjectSchedulesView.as_view(), name='update-schedules'),

    # Doctor schedule (existing)
    path('my-schedule/',                    DoctorScheduleView.as_view(),         name='doctor-schedule'),

    # ── Scheduling endpoints (NEW) ────────────────────────────────────────
    # Doctor availability — Dean manages any doctor
    path('availability/',                   DoctorAvailabilityView.as_view(),     name='doctor-availability'),
    path('availability/<int:pk>/',          DoctorAvailabilityView.as_view(),     name='doctor-availability-detail'),
    path('availability/exceptions/',        DoctorDateExceptionView.as_view(),    name='doctor-date-exception'),
    path('availability/exceptions/<int:pk>/', DoctorDateExceptionView.as_view(),  name='doctor-date-exception-detail'),

    # Doctor availability — self-service
    path('my-availability/',                MyAvailabilityView.as_view(),         name='my-availability'),
    path('my-availability/<int:pk>/',       MyAvailabilityView.as_view(),         name='my-availability-detail'),
    path('my-availability/exceptions/',     MyDateExceptionView.as_view(),        name='my-date-exception'),
    path('my-availability/exceptions/<int:pk>/', MyDateExceptionView.as_view(),    name='my-date-exception-detail'),

    # Scheduling runs (read-only — created by preview endpoint)
    path('schedule/runs/',                  SchedulingRunListView.as_view(),      name='schedule-runs-list'),
    path('schedule/runs/<int:pk>/',         SchedulingRunDetailView.as_view(),    name='schedule-runs-detail'),

    # Preview/Apply/Reject (Phase 2)
    *(
        [
            path('schedule/preview/',       SchedulePreviewView.as_view(),        name='schedule-preview'),
            path('schedule/<int:run_id>/apply/',   ScheduleApplyView.as_view(),    name='schedule-apply'),
            path('schedule/<int:run_id>/reject/', ScheduleRejectView.as_view(),    name='schedule-reject'),
        ] if _HAS_SCHEDULE_VIEWS else []
    ),
    # Wizard endpoints (Phase 4 — unified setup + scheduling)
    *(
        [
            path('semester-setup/',        SemesterSetupView.as_view(),       name='semester-setup'),
            path('schedule-all/',          ScheduleAllView.as_view(),         name='schedule-all'),
            path('schedule-apply-all/',    ScheduleApplyAllView.as_view(),    name='schedule-apply-all'),
            path('schedule-reject-all/',   ScheduleRejectAllView.as_view(),   name='schedule-reject-all'),
        ] if _HAS_WIZARD_VIEWS else []
    ),
]
