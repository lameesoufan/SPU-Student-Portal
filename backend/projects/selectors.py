from django.db.models import Q

from .models import ProjectIdea, StudentIdeaProposal


def get_ideas_for_doctor(doctor):
    """Return ideas submitted by this doctor or HoD."""
    return ProjectIdea.objects.filter(doctor=doctor).prefetch_related(
        'applications', 'applications__student',
        'applications__invitations', 'applications__invitations__invitee',
    ).order_by('-created_at')


def get_approved_ideas():
    """All approved doctor ideas visible to students for browsing."""
    return ProjectIdea.objects.filter(status='approved').select_related('doctor').prefetch_related(
        'applications', 'applications__invitations', 'applications__invitations__invitee',
        'applications__student',
    ).order_by('-created_at')


def get_all_ideas():
    return ProjectIdea.objects.select_related('doctor').order_by('-created_at')


def get_student_proposal(student):
    """Return the student's latest active proposal, or the latest one of any status."""
    base = StudentIdeaProposal.objects.select_related('student', 'supervisor').prefetch_related(
        'co_supervisors', 'invitations', 'invitations__invitee'
    )

    active = base.filter(
        student=student,
        status__in=['awaiting_members', 'pending_supervisor', 'pending_hod', 'assigned'],
    ).order_by('-created_at').first()
    if active:
        return active
    # Fall back to latest (rejected) so student can see history
    return base.filter(student=student).order_by('-created_at').first()


def get_pending_supervisor_proposals(supervisor):
    """Proposals waiting for this supervisor's approval."""
    return StudentIdeaProposal.objects.filter(
        Q(supervisor=supervisor) | Q(co_supervisors=supervisor),
        status='pending_supervisor',
    ).select_related('student', 'supervisor').prefetch_related(
        'co_supervisors', 'invitations', 'invitations__invitee'
    ).distinct().order_by('-created_at')


def get_pending_hod_proposals(department):
    """Proposals waiting for HoD review in a given department."""
    return StudentIdeaProposal.objects.filter(
        department=department,
        status='pending_hod',
    ).select_related('student', 'supervisor').prefetch_related(
        'co_supervisors', 'invitations', 'invitations__invitee'
    ).order_by('-created_at')


def get_pending_doctor_ideas_for_hod(department):
    """Doctor ideas pending HoD review in a given department."""
    from .models import ProjectIdea
    return ProjectIdea.objects.filter(
        department=department,
        status='pending_review',
    ).select_related('doctor').order_by('-created_at')


def get_student_idea_application(student):
    """Return the student's active IdeaApplication or None."""
    from .models import IdeaApplication
    return IdeaApplication.objects.filter(student=student).select_related(
        'student', 'idea', 'idea__doctor'
    ).prefetch_related('invitations', 'invitations__invitee').order_by('-created_at').first()


def get_pending_doctor_applications(doctor):
    """Applications on this doctor's ideas waiting for doctor approval."""
    from .models import IdeaApplication
    return IdeaApplication.objects.filter(
        idea__doctor=doctor,
        status='pending_doctor',
    ).select_related('student', 'idea', 'idea__doctor').prefetch_related(
        'invitations', 'invitations__invitee'
    ).order_by('-created_at')


def get_pending_hod_applications(department):
    """Applications waiting for HoD approval in a department."""
    from .models import IdeaApplication
    return IdeaApplication.objects.filter(
        idea__department=department,
        status='pending_hod',
    ).select_related('student', 'idea', 'idea__doctor').prefetch_related(
        'invitations', 'invitations__invitee'
    ).order_by('-created_at')
