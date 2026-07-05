from django.urls import path
from .views import (
    ReportUploadView,
    ReportDetailView,
    ReportDownloadView,
    EnterGradeView,
    EnterBulkGradesView,
    ProjectGradesView,
    MyCommitteeGradesView,
    GradesSummaryView,
    GradesExportView,
    MyGradesView,
    CommitteeGradingModeView,
    DoctorGradeDraftView,
)

urlpatterns = [
    path('report/upload/',                         ReportUploadView.as_view(),      name='report-upload'),
    path('report/<str:source>/<int:pid>/',          ReportDetailView.as_view(),      name='report-detail'),
    path('report/<str:source>/<int:pid>/download/', ReportDownloadView.as_view(),    name='report-download'),
    path('enter/',                                 EnterGradeView.as_view(),        name='enter-grade'),
    path('enter/bulk/',                            EnterBulkGradesView.as_view(),   name='enter-grade-bulk'),
    path('project/<str:source>/<int:pid>/',        ProjectGradesView.as_view(),     name='project-grades'),
    path('my-committee-grades/',                   MyCommitteeGradesView.as_view(), name='my-committee-grades'),
    path('my-grades/',                             MyGradesView.as_view(),          name='my-grades'),
    path('summary/',                               GradesSummaryView.as_view(),     name='grades-summary'),
    path('export/',                                GradesExportView.as_view(),      name='grades-export'),
    # Collective grading
    path('grading-mode/',                          CommitteeGradingModeView.as_view(), name='grading-mode'),
    path('draft/',                                 DoctorGradeDraftView.as_view(),  name='grade-draft'),
]
