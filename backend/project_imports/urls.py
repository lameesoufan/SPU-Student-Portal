from django.urls import path

from .views import DownloadTemplateView, ImportHistoryView, ImportProjectsView, ImportRowsView


urlpatterns = [
    path('projects/', ImportProjectsView.as_view(), name='import-projects'),
    path('template/', DownloadTemplateView.as_view(), name='import-template'),
    path('history/', ImportHistoryView.as_view(), name='import-history'),
    path('history/<uuid:session_id>/rows/', ImportRowsView.as_view(), name='import-rows'),
]
