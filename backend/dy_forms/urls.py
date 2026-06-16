from django.urls import path
from .views import (
    hod_get_form, hod_save_form,
    student_get_form, submit_form_response,
    hod_list_responses,
    get_response_by_proposal, get_response_by_application,
)

urlpatterns = [
    # HoD manages their form
    path('api/dy-forms/hod/<str:context>/',        hod_get_form,   name='hod_get_form'),
    path('api/dy-forms/hod/<str:context>/save/',   hod_save_form,  name='hod_save_form'),
    path('api/dy-forms/hod/<str:context>/responses/', hod_list_responses, name='hod_list_responses'),

    # Student submits response
    path('api/dy-forms/responses/submit/',         submit_form_response, name='submit_form_response'),

    # Retrieve responses by proposal / application
    path('api/dy-forms/responses/proposal/<int:proposal_id>/',       get_response_by_proposal,     name='response_by_proposal'),
    path('api/dy-forms/responses/application/<int:application_id>/', get_response_by_application,  name='response_by_application'),

    # Student fetches form for a department. Keep this after fixed response routes.
    path('api/dy-forms/<str:department>/<str:context>/', student_get_form, name='student_get_form'),
]
