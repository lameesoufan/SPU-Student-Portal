from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    IdeaApplication,
    ProjectParticipation,
    ProjectParticipationStatusLog,
    StudentIdeaProposal,
)


User = get_user_model()

NO_REGISTERED_PROJECT_ERROR = 'This student has no registered project.'


class ParticipationStatusError(ValueError):
    pass


def user_display_name(user):
    if not user:
        return ''
    return user.get_full_name() or user.username


def project_for_participation(participation):
    return participation.idea_application or participation.student_proposal


def project_filter_kwargs(project):
    if isinstance(project, IdeaApplication):
        return {'idea_application': project}
    if isinstance(project, StudentIdeaProposal):
        return {'student_proposal': project}
    raise TypeError('Unsupported project source.')


def source_for_project(project):
    if isinstance(project, IdeaApplication):
        return 'idea_application'
    if isinstance(project, StudentIdeaProposal):
        return 'student_proposal'
    raise TypeError('Unsupported project source.')


def is_registered_project_source(project):
    if isinstance(project, IdeaApplication):
        return project.status == 'registered'
    if isinstance(project, StudentIdeaProposal):
        return project.status == 'assigned'
    return False


def get_project_participations(project):
    return (
        ProjectParticipation.objects
        .filter(**project_filter_kwargs(project))
        .select_related('student', 'status_changed_by')
        .order_by('role', 'student__username', 'id')
    )


def get_active_project_participations(project):
    return get_project_participations(project).active()


def get_active_project_members(project):
    student_ids = get_active_project_participations(project).values_list('student_id', flat=True)
    return User.objects.filter(id__in=student_ids)


def team_stats_for_project(project):
    participations = list(get_project_participations(project))
    total = len(participations)
    active = sum(1 for p in participations if p.status == 'active')
    failed = sum(1 for p in participations if p.status == 'failed')
    withdrawn = sum(1 for p in participations if p.status == 'withdrawn')

    if active == 0:
        label = f'0/{total} Cancelled'
    elif active == 1 and total > 1:
        label = f'1/{total} ⚠️ Solo'
    elif active < total:
        label = f'{active}/{total} ⚠️'
    else:
        label = f'{active}/{total}'

    return {
        'active': active,
        'failed': failed,
        'withdrawn': withdrawn,
        'total': total,
        'label': label,
    }


def derive_operational_status(stats):
    total = stats['total']
    active = stats['active']
    failed = stats['failed']
    withdrawn = stats['withdrawn']

    if total == 0:
        return 'inactive'
    if active == 0 and withdrawn == total:
        return 'fully_withdrawn'
    if active == 0 and failed == total:
        return 'fully_failed'
    if active == 0:
        return 'inactive'
    if active == 1:
        return 'solo'
    if active < total:
        return 'partial_team'
    return 'active'


def recalculate_project_operational_status(project):
    stats = team_stats_for_project(project)
    operational_status = derive_operational_status(stats)
    if getattr(project, 'operational_status', None) != operational_status:
        project.operational_status = operational_status
        project.save(update_fields=['operational_status', 'updated_at'])
    return operational_status


def create_participations_for_student_proposal(proposal):
    created = []
    leader, _ = ProjectParticipation.objects.get_or_create(
        student=proposal.student,
        student_proposal=proposal,
        defaults={
            'project_source': 'student_proposal',
            'role': 'leader',
            'status': 'active',
        },
    )
    created.append(leader)

    accepted_invitations = proposal.invitations.filter(status='accepted').select_related('invitee')
    for invitation in accepted_invitations:
        participation, _ = ProjectParticipation.objects.get_or_create(
            student=invitation.invitee,
            student_proposal=proposal,
            defaults={
                'project_source': 'student_proposal',
                'role': 'member',
                'status': 'active',
            },
        )
        created.append(participation)

    recalculate_project_operational_status(proposal)
    return created


def create_participations_for_idea_application(application):
    created = []
    leader, _ = ProjectParticipation.objects.get_or_create(
        student=application.student,
        idea_application=application,
        defaults={
            'project_source': 'idea_application',
            'role': 'leader',
            'status': 'active',
        },
    )
    created.append(leader)

    accepted_invitations = application.invitations.filter(status='accepted').select_related('invitee')
    for invitation in accepted_invitations:
        participation, _ = ProjectParticipation.objects.get_or_create(
            student=invitation.invitee,
            idea_application=application,
            defaults={
                'project_source': 'idea_application',
                'role': 'member',
                'status': 'active',
            },
        )
        created.append(participation)

    recalculate_project_operational_status(application)
    return created


def current_registered_participations_for_student(student):
    return (
        ProjectParticipation.objects
        .filter(student=student)
        .filter(
            Q(idea_application__status='registered')
            | Q(student_proposal__status='assigned')
        )
        .select_related(
            'student',
            'status_changed_by',
            'idea_application__idea__doctor',
            'student_proposal__supervisor',
        )
    )


def student_has_active_registered_project(student):
    participations = current_registered_participations_for_student(student)
    if participations.exists():
        return participations.active().exists()

    # Backward-compatible fallback for tests/data created before participation rows.
    return (
        IdeaApplication.objects.filter(student=student, status='registered').exists()
        or StudentIdeaProposal.objects.filter(student=student, status='assigned').exists()
        or IdeaApplication.objects.filter(
            invitations__invitee=student,
            invitations__status='accepted',
            status='registered',
        ).exists()
        or StudentIdeaProposal.objects.filter(
            invitations__invitee=student,
            invitations__status='accepted',
            status='assigned',
        ).exists()
    )


def resolve_registered_participation_for_student(student_id):
    student = User.objects.get(pk=student_id)
    participations = current_registered_participations_for_student(student)
    if not participations.exists():
        raise ParticipationStatusError(NO_REGISTERED_PROJECT_ERROR)
    return participations.order_by('-status', '-updated_at', '-id').first()


def action_type_for_status(new_status):
    return {
        'failed': 'student_project_status_marked_failed',
        'withdrawn': 'student_project_status_marked_withdrawn',
        'active': 'student_project_status_reversed_to_active',
    }[new_status]


def validate_transition(previous_status, new_status):
    if previous_status == new_status:
        raise ParticipationStatusError(f'Student is already {new_status}.')
    if previous_status == 'active' and new_status in ('failed', 'withdrawn'):
        return
    if previous_status in ('failed', 'withdrawn') and new_status == 'active':
        return
    raise ParticipationStatusError('Invalid status transition. Reverse to active before applying a different inactive status.')


class StudentProjectStatusService:
    @staticmethod
    def mark_as_failed(participation_id, reason, changed_by, notes=''):
        return StudentProjectStatusService.change_status(
            participation_id=participation_id,
            new_status='failed',
            reason=reason,
            changed_by=changed_by,
            notes=notes,
        )

    @staticmethod
    def mark_as_withdrawn(participation_id, reason, changed_by, notes=''):
        return StudentProjectStatusService.change_status(
            participation_id=participation_id,
            new_status='withdrawn',
            reason=reason,
            changed_by=changed_by,
            notes=notes,
        )

    @staticmethod
    def reverse_to_active(participation_id, reason, changed_by, notes=''):
        return StudentProjectStatusService.change_status(
            participation_id=participation_id,
            new_status='active',
            reason=reason,
            changed_by=changed_by,
            notes=notes,
        )

    @staticmethod
    @transaction.atomic
    def change_status(participation_id, new_status, reason, changed_by, notes=''):
        # Get participation with lock (no select_related with nullable fields)
        participation = (
            ProjectParticipation.objects
            .select_for_update()
            .select_related('student')  # Only non-nullable field
            .get(pk=participation_id)
        )
        
        # Load related objects after acquiring lock
        if participation.status_changed_by_id:
            _ = participation.status_changed_by  # Force load
        if participation.idea_application_id:
            _ = participation.idea_application.idea.doctor  # Force load
        if participation.student_proposal_id:
            _ = participation.student_proposal.supervisor  # Force load
        project = project_for_participation(participation)
        if project is None or not is_registered_project_source(project):
            raise ParticipationStatusError(NO_REGISTERED_PROJECT_ERROR)

        if isinstance(project, IdeaApplication):
            IdeaApplication.objects.select_for_update().filter(pk=project.pk).first()
        else:
            StudentIdeaProposal.objects.select_for_update().filter(pk=project.pk).first()

        previous_status = participation.status
        validate_transition(previous_status, new_status)

        before_stats = team_stats_for_project(project)
        before_operational_status = getattr(project, 'operational_status', 'active')

        participation.status = new_status
        participation.status_reason = reason or ''
        participation.status_notes = notes or ''
        participation.status_changed_at = timezone.now()
        participation.status_changed_by = changed_by
        participation.save(update_fields=[
            'status',
            'status_reason',
            'status_notes',
            'status_changed_at',
            'status_changed_by',
            'updated_at',
        ])

        after_operational_status = recalculate_project_operational_status(project)
        after_stats = team_stats_for_project(project)

        ProjectParticipationStatusLog.objects.create(
            participation=participation,
            student=participation.student,
            project_source=participation.project_source,
            idea_application=participation.idea_application,
            student_proposal=participation.student_proposal,
            previous_status=previous_status,
            new_status=new_status,
            reason=reason or '',
            notes=notes or '',
            changed_by=changed_by,
            action_type=action_type_for_status(new_status),
            metadata={
                'team_size_before': before_stats,
                'team_size_after': after_stats,
                'project_operational_status_before': before_operational_status,
                'project_operational_status_after': after_operational_status,
            },
        )

        participation.refresh_from_db()
        return participation
