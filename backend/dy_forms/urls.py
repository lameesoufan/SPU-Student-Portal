from django.urls import path

from .views import (
    download_field_response_file,
    get_response_by_application,
    get_response_by_proposal,
    hod_get_form,
    hod_list_responses,
    hod_save_form,
    student_get_form,
    submit_form_response,
)

urlpatterns = [
    path('api/dy-forms/hod/<str:context>/', hod_get_form, name='hod_get_form'),
    path('api/dy-forms/hod/<str:context>/save/', hod_save_form, name='hod_save_form'),
    path('api/dy-forms/hod/<str:context>/responses/', hod_list_responses, name='hod_list_responses'),

    path('api/dy-forms/responses/submit/', submit_form_response, name='submit_form_response'),
    path(
        'api/dy-forms/responses/files/<int:field_response_id>/',
        download_field_response_file,
        name='dynamic_form_file_download',
    ),

    path(
        'api/dy-forms/responses/proposal/<int:proposal_id>/',
        get_response_by_proposal,
        name='response_by_proposal',
    ),
    path(
        'api/dy-forms/responses/application/<int:application_id>/',
        get_response_by_application,
        name='response_by_application',
    ),

    path('api/dy-forms/<str:department>/<str:context>/', student_get_form, name='student_get_form'),
]
