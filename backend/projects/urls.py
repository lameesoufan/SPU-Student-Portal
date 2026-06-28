from django.urls import path
from .views import (
    submit_idea, my_ideas,
    propose_idea, my_proposal, cancel_proposal_view,
    list_doctors_for_student, list_students_for_team,
    supervisor_pending_proposals, supervisor_review,
    hod_pending_proposals, hod_review,
    hod_pending_doctor_ideas, hod_review_idea,
    browse_ideas, apply_idea, my_idea_application,
    doctor_pending_applications, doctor_review_app,
    hod_pending_applications, hod_review_app,
    my_invitations, respond_invitation,
    my_proposal_invitations, respond_proposal_invitation,
    replace_proposal_member_view, replace_application_member_view,
    student_status_management, student_status_management_stats,
    mark_participation_failed, mark_participation_withdrawn,
    reverse_participation_to_active, designate_student_status,
    participation_history, student_participation_history,
)

urlpatterns = [
    # UC-01 — Doctor
    path('api/projects/ideas/',                              my_ideas,                     name='my_ideas'),
    path('api/projects/ideas/submit/',                       submit_idea,                  name='submit_idea'),

    # UC-02 — Student proposal
    path('api/projects/proposals/submit/',                   propose_idea,                 name='propose_idea'),
    path('api/projects/proposals/mine/',                     my_proposal,                  name='my_proposal'),
    path('api/projects/proposals/<int:proposal_id>/cancel/', cancel_proposal_view,         name='cancel_proposal'),
    path('api/projects/doctors/',                            list_doctors_for_student,     name='doctors_for_student'),
    path('api/projects/students/',                           list_students_for_team,       name='students_for_team'),

    # UC-02 — Supervisor (doctor)
    path('api/projects/proposals/pending-supervisor/',       supervisor_pending_proposals, name='supervisor_pending'),
    path('api/projects/proposals/<int:proposal_id>/supervisor-review/', supervisor_review, name='supervisor_review'),

    # HoD — student proposals
    path('api/projects/proposals/pending-hod/',              hod_pending_proposals,        name='hod_pending'),
    path('api/projects/proposals/<int:proposal_id>/hod-review/', hod_review,               name='hod_review'),

    # HoD — doctor ideas review
    path('api/projects/ideas/pending-hod/',                  hod_pending_doctor_ideas,     name='hod_pending_ideas'),
    path('api/projects/ideas/<int:idea_id>/hod-review/',     hod_review_idea,              name='hod_review_idea'),

    # UC-03 — Browse & apply
    path('api/projects/ideas/browse/',                       browse_ideas,                 name='browse_ideas'),
    path('api/projects/ideas/<int:idea_id>/apply/',          apply_idea,                   name='apply_idea'),
    path('api/projects/applications/mine/',                  my_idea_application,          name='my_idea_application'),

    # UC-03 — Doctor reviews applications
    path('api/projects/applications/pending-doctor/',        doctor_pending_applications,  name='doctor_pending_apps'),
    path('api/projects/applications/<int:app_id>/doctor-review/', doctor_review_app,       name='doctor_review_app'),

    # UC-03 — HoD reviews applications
    path('api/projects/applications/pending-hod/',           hod_pending_applications,     name='hod_pending_apps'),
    path('api/projects/applications/<int:app_id>/hod-review/', hod_review_app,             name='hod_review_app'),

    # Team invitations (doctor idea applications)
    path('api/projects/invitations/mine/',                   my_invitations,               name='my_invitations'),
    path('api/projects/invitations/<int:inv_id>/respond/',   respond_invitation,           name='respond_invitation'),

    # Proposal invitations (student proposals)
    path('api/projects/proposal-invitations/mine/',                  my_proposal_invitations,        name='my_proposal_invitations'),
    path('api/projects/proposal-invitations/<int:inv_id>/respond/',  respond_proposal_invitation,    name='respond_proposal_invitation'),

    # Replace rejected members
    path('api/projects/proposals/<int:proposal_id>/replace-member/', replace_proposal_member_view,   name='replace_proposal_member'),
    path('api/projects/applications/<int:app_id>/replace-member/',   replace_application_member_view, name='replace_application_member'),

    # Dean student project participation status management
    path('api/projects/participations/status-management/', student_status_management, name='student_status_management'),
    path('api/projects/participations/status-management/stats/', student_status_management_stats, name='student_status_management_stats'),
    path('api/projects/participations/<int:participation_id>/mark-failed/', mark_participation_failed, name='mark_participation_failed'),
    path('api/projects/participations/<int:participation_id>/mark-withdrawn/', mark_participation_withdrawn, name='mark_participation_withdrawn'),
    path('api/projects/participations/<int:participation_id>/reverse-to-active/', reverse_participation_to_active, name='reverse_participation_to_active'),
    path('api/projects/participations/<int:participation_id>/history/', participation_history, name='participation_history'),
    path('api/projects/students/<int:student_id>/designate-status/', designate_student_status, name='designate_student_status'),
    path('api/projects/students/<int:student_id>/participation-history/', student_participation_history, name='student_participation_history'),
]
