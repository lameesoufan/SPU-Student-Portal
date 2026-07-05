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


router = DefaultRouter()
router.register(r'templates',  CommitteeTemplateViewSet, basename='committee-template')
router.register(r'committees', CommitteeViewSet,         basename='committee')


urlpatterns = [
    path('',                                include(router.urls)),
    path('dashboard/',                      DashboardView.as_view(),  name='committee-dashboard'),
    path('distribute/',                     DistributeView.as_view(), name='committee-distribute'),
    path('export/',                         ExportView.as_view(),     name='committee-export'),
    path('projects-assignment/',            ProjectsAssignmentView.as_view(), name='projects-assignment'),
    path('projects-assignment/export/',     ExportProjectsAssignmentView.as_view(), name='projects-assignment-export'),
    path('update-schedules/',               UpdateProjectSchedulesView.as_view(), name='update-schedules'),
    path('my-schedule/',                    DoctorScheduleView.as_view(),         name='doctor-schedule'),
]
