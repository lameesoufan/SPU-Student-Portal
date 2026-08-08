from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q

from accounts.permissions import IsDeanOrAdmin
from accounts.models import User
from accounts.throttles import ProposeIdeaThrottle
from .permissions import IsDoctor, IsDoctorOrHod, IsStudent, IsHod
from .selectors import (
    get_ideas_for_doctor, get_student_proposal, get_approved_ideas,
    get_pending_supervisor_proposals, get_pending_hod_proposals,
    get_pending_doctor_ideas_for_hod,
    get_student_idea_application, get_pending_doctor_applications, get_pending_hod_applications,
)
from .serializers import (
    ProjectIdeaSerializer, StudentIdeaProposalSerializer,
    ProposalReviewSerializer, IdeaApplicationSerializer,
    TeamInvitationSerializer, ProposalInvitationSerializer,
    ProjectParticipationManagementSerializer,
    ProjectParticipationStatusChangeSerializer,
    ProjectParticipationStatusLogSerializer,
)
from .services import (
    create_project_idea, create_student_proposal, cancel_proposal,
    supervisor_review_proposal, hod_review_proposal,
    hod_review_doctor_idea,
    apply_on_idea, doctor_review_application, hod_review_application,
    respond_to_invitation, respond_to_proposal_invitation,
    replace_proposal_member, remove_rejected_proposal_member,
    replace_rejected_supervisor, continue_with_approved_supervisor,
    revise_student_proposal,
    replace_application_member,
)
from .models import (
    StudentIdeaProposal,
    ProjectIdea,
    IdeaApplication,
    TeamInvitation,
    ProposalInvitation,
    ProposalSupervisorDecision,
    ProjectParticipation,
    ProjectParticipationStatusLog,
)
from .participation_services import (
    ParticipationStatusError,
    StudentProjectStatusService,
    resolve_registered_participation_for_student,
)


MAX_STUDENT_SEARCH_RESULTS = 20
MIN_STUDENT_SEARCH_CHARS = 2
MAX_LIST_RESPONSE_SIZE = 100
MAX_STATUS_MANAGEMENT_RESULTS = 500


def _validation_error_response(errors):
    return Response({'error': 'Validation failed.', 'details': errors}, status=400)

# helper to save dynamic form response inside an existing transaction
def _save_form_response(student, form_id, field_responses, proposal_id=None, application_id=None):
    """Save a project-creation form response only when form/link scope matches."""
    if not form_id or not isinstance(field_responses, list):
        return

    from dy_forms.models import DynamicForm
    from dy_forms.serializers import FormResponseSerializer

    form = DynamicForm.objects.filter(pk=form_id).first()
    if not form:
        return

    if proposal_id is not None:
        project = StudentIdeaProposal.objects.filter(pk=proposal_id, student=student).first()
        if not project or form.context != 'propose' or form.department != project.department:
            return
    elif application_id is not None:
        project = IdeaApplication.objects.filter(pk=application_id, student=student).select_related('idea').first()
        if not project or form.context != 'browse' or form.department != project.idea.department:
            return
    else:
        return

    serializer = FormResponseSerializer(data={
        'form': form.id,
        'proposal_id': proposal_id,
        'application_id': application_id,
        'field_responses': field_responses,
    })
    serializer.is_valid(raise_exception=True)
    serializer.save(student=student)


# ── UC-01: Doctor ideas ───────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsDoctor])
def submit_idea(request):
    serializer = ProjectIdeaSerializer(data=request.data)
    if not serializer.is_valid():
        return _validation_error_response(serializer.errors)
    
    # Extract only the fields create_project_idea accepts
    data = serializer.validated_data
    result = create_project_idea(
        doctor=request.user,
        title=data['title'],
        description=data['description'],
        department=data['department'],
        required_skills=data.get('required_skills', ''),
        max_team_size=data.get('max_team_size', 2),
    )
    if not result.get('ok'):
        return Response({'error': result.get('error', 'Duplicate submission.')}, status=409)
    return Response(
        {'message': 'Idea submitted successfully.', 'idea': ProjectIdeaSerializer(result['idea']).data},
        status=201,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsDoctorOrHod])
def my_ideas(request):
    ideas = get_ideas_for_doctor(request.user)[:MAX_LIST_RESPONSE_SIZE]
    return Response(ProjectIdeaSerializer(ideas, many=True).data)


# ── UC-02: Student proposals ──────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
@throttle_classes([ProposeIdeaThrottle])
def propose_idea(request):
    serializer = StudentIdeaProposalSerializer(data=request.data)
    if not serializer.is_valid():
        return _validation_error_response(serializer.errors)

    try:
        team_size = int(request.data.get('team_size', 1))
    except (TypeError, ValueError):
        return _validation_error_response({'team_size': 'Team size must be a valid number.'})

    team_size_reason = request.data.get('team_size_reason', '').strip()

    supervisor_ids = serializer.validated_data.get('supervisor_ids')
    if not supervisor_ids:
        legacy_supervisor = serializer.validated_data.get('supervisor')
        supervisor_ids = [legacy_supervisor.pk] if legacy_supervisor else []

    supervisors_by_id = {
        doctor.id: doctor
        for doctor in User.objects.filter(id__in=supervisor_ids, role__in=['doctor', 'hod'])
    }
    supervisors = [supervisors_by_id.get(supervisor_id) for supervisor_id in supervisor_ids]
    if not supervisor_ids or any(supervisor is None for supervisor in supervisors):
        return _validation_error_response({'supervisor_ids': 'Choose one or two valid supervisors.'})

    if hasattr(request.data, 'getlist'):
        member_ids = request.data.getlist('member_ids')
    else:
        member_ids = request.data.get('member_ids', [])

    form_id = request.data.get('form_id')

    import json
    raw_field_responses = request.data.get('field_responses', [])
    if isinstance(raw_field_responses, str):
        try:
            field_responses = json.loads(raw_field_responses)
        except json.JSONDecodeError:
            field_responses = []
    else:
        field_responses = raw_field_responses

    try:
        with transaction.atomic():
            result = create_student_proposal(
                student=request.user,
                supervisors=supervisors,
                title=serializer.validated_data['title'],
                description=serializer.validated_data['description'],
                department=serializer.validated_data['department'],
                team_size=team_size,
                team_size_reason=team_size_reason,
                project_type=serializer.validated_data.get('project_type', 'seasonal'),
                member_ids=member_ids,
            )
            if not result['ok']:
                return Response({'error': result['error']}, status=400)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'propose_idea unexpected error: {e}', exc_info=True)
        return Response({'error': 'An unexpected error occurred while submitting your proposal. Please try again.'}, status=500)

    # ↓↓↓ حفظ الـ form برا الـ transaction الرئيسي — إذا فشل ما يكسر الـ proposal ↓↓↓
    if form_id and field_responses:
        try:
            _save_form_response(
                student=request.user,
                form_id=form_id,
                field_responses=field_responses,
                proposal_id=result['proposal'].id,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f'Failed to save form response for proposal {result["proposal"].id}: {e}')

    return Response(
        {'message': 'Proposal submitted successfully.',
         'proposal': StudentIdeaProposalSerializer(result['proposal']).data},
        status=201,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudent])
def my_proposal(request):
    proposal = get_student_proposal(request.user)
    if not proposal:
        return Response(None)
    return Response(StudentIdeaProposalSerializer(proposal).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def cancel_proposal_view(request, proposal_id):
    try:
        proposal = StudentIdeaProposal.objects.get(pk=proposal_id, student=request.user)
    except StudentIdeaProposal.DoesNotExist:
        return Response({'error': 'Proposal not found.'}, status=404)
    result = cancel_proposal(proposal=proposal, student=request.user)
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    return Response({'message': 'Proposal cancelled successfully.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudent])
def list_doctors_for_student(request):
    """Return all doctors for the supervisor dropdown."""
    doctors = User.objects.filter(role__in=['doctor', 'hod']).values('id', 'username', 'first_name', 'last_name', 'department')[:MAX_LIST_RESPONSE_SIZE]
    result = [
        {
            'id': d['id'],
            'name': f"{d['first_name']} {d['last_name']}".strip() or d['username'],
            'department': d['department'],
        }
        for d in doctors
    ]
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudent])
def list_students_for_team(request):
    """Return all students (except self) for team member search."""
    q = request.query_params.get('q', '').strip()
    if len(q) < MIN_STUDENT_SEARCH_CHARS:
        return Response([])

    qs = User.objects.filter(role='student').exclude(pk=request.user.pk).filter(
        Q(username__icontains=q) |
        Q(first_name__icontains=q) |
        Q(last_name__icontains=q)
    ).values('username', 'first_name', 'last_name')[:MAX_STUDENT_SEARCH_RESULTS]
    result = [
        {
            'username': s['username'],
            'name': f"{s['first_name']} {s['last_name']}".strip() or s['username'],
            'display': f"{s['first_name']} {s['last_name']}".strip() + f" ({s['username']})" if (s['first_name'] or s['last_name']) else s['username'],
        }
        for s in qs
    ]
    return Response(result)


# ── Supervisor review ─────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsDoctorOrHod])
def supervisor_pending_proposals(request):
    proposals = get_pending_supervisor_proposals(request.user)[:MAX_LIST_RESPONSE_SIZE]
    return Response(StudentIdeaProposalSerializer(proposals, many=True).data)



@api_view(['POST'])
@permission_classes([IsAuthenticated, IsDoctorOrHod])
def supervisor_review(request, proposal_id):
    try:
        proposal = StudentIdeaProposal.objects.filter(
            pk=proposal_id,
        ).filter(
            Q(
                supervisor_decisions__supervisor=request.user,
                supervisor_decisions__is_active=True,
                supervisor_decisions__status='pending',
            )
            | Q(supervisor_decisions__isnull=True, supervisor=request.user)
            | Q(supervisor_decisions__isnull=True, co_supervisors=request.user)
        ).distinct().get()
    except StudentIdeaProposal.DoesNotExist:
        return Response({'error': 'Proposal not found.'}, status=404)

    serializer = ProposalReviewSerializer(data=request.data)
    if not serializer.is_valid():
        return _validation_error_response(serializer.errors)

    result = supervisor_review_proposal(
        proposal=proposal,
        reviewer=request.user,
        action=serializer.validated_data['action'],
        rejection_reason=serializer.validated_data.get('rejection_reason', ''),
    )
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    return Response(StudentIdeaProposalSerializer(result['proposal']).data)


# ── HoD review ────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHod])
def hod_pending_proposals(request):
    proposals = get_pending_hod_proposals(request.user.department)[:MAX_LIST_RESPONSE_SIZE]
    return Response(StudentIdeaProposalSerializer(proposals, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHod])
def hod_review(request, proposal_id):
    try:
        proposal = StudentIdeaProposal.objects.get(pk=proposal_id, department=request.user.department)
    except StudentIdeaProposal.DoesNotExist:
        return Response({'error': 'Proposal not found.'}, status=404)

    serializer = ProposalReviewSerializer(data=request.data)
    if not serializer.is_valid():
        return _validation_error_response(serializer.errors)

    result = hod_review_proposal(
        proposal=proposal,
        action=serializer.validated_data['action'],
        rejection_reason=serializer.validated_data.get('rejection_reason', ''),
    )
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    return Response(StudentIdeaProposalSerializer(result['proposal']).data)


# ── HoD review of doctor ideas ────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHod])
def hod_pending_doctor_ideas(request):
    ideas = get_pending_doctor_ideas_for_hod(request.user.department)[:MAX_LIST_RESPONSE_SIZE]
    return Response(ProjectIdeaSerializer(ideas, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHod])
def hod_review_idea(request, idea_id):
    try:
        idea = ProjectIdea.objects.get(pk=idea_id, department=request.user.department)
    except ProjectIdea.DoesNotExist:
        return Response({'error': 'Idea not found.'}, status=404)

    serializer = ProposalReviewSerializer(data=request.data)
    if not serializer.is_valid():
        return _validation_error_response(serializer.errors)

    result = hod_review_doctor_idea(
        idea=idea,
        action=serializer.validated_data['action'],
        rejection_reason=serializer.validated_data.get('rejection_reason', ''),
    )
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    return Response(ProjectIdeaSerializer(result['idea']).data)


# ── UC-03: Browse & apply on doctor ideas ────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudent])
def browse_ideas(request):
    """Return all approved ideas for students to browse."""
    ideas = get_approved_ideas()[:MAX_LIST_RESPONSE_SIZE]
    return Response(ProjectIdeaSerializer(ideas, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def apply_idea(request, idea_id):
    try:
        idea = ProjectIdea.objects.get(pk=idea_id)
    except ProjectIdea.DoesNotExist:
        return Response({'error': 'Idea not found.'}, status=404)

    try:
        team_size = int(request.data.get('team_size', 1))
    except (TypeError, ValueError):
        return _validation_error_response({'team_size': 'Team size must be a valid number.'})

    team_size_reason = request.data.get('team_size_reason', '').strip()

    if hasattr(request.data, 'getlist'):
        member_ids = request.data.getlist('member_ids')
    else:
        member_ids = request.data.get('member_ids', [])

    form_id = request.data.get('form_id')

    import json
    raw_field_responses = request.data.get('field_responses', [])
    if isinstance(raw_field_responses, str):
        try:
            field_responses = json.loads(raw_field_responses)
        except json.JSONDecodeError:
            field_responses = []
    else:
        field_responses = raw_field_responses

    project_type = request.data.get('project_type') or getattr(idea, 'project_type', None) or 'seasonal'
    if not project_type or project_type not in ('seasonal', 'graduation_1', 'graduation_2'):
        return _validation_error_response({'project_type': 'A valid project type is required.'})

    try:
        with transaction.atomic():
            result = apply_on_idea(student=request.user, idea=idea, team_size=team_size, team_size_reason=team_size_reason, member_ids=member_ids, project_type=project_type)
            if not result['ok']:
                return Response({'error': result['error']}, status=400)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'apply_idea unexpected error: {e}', exc_info=True)
        return Response({'error': 'An unexpected error occurred while applying. Please try again.'}, status=500)

    # ↓↓↓ حفظ الـ form برا الـ transaction — إذا فشل ما يكسر الـ application ↓↓↓
    if form_id and field_responses:
        try:
            _save_form_response(
                student=request.user,
                form_id=form_id,
                field_responses=field_responses,
                application_id=result['application'].id,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f'Failed to save form response for application {result["application"].id}: {e}')

    return Response(IdeaApplicationSerializer(result['application']).data, status=201)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudent])
def my_idea_application(request):
    app = get_student_idea_application(request.user)
    if not app:
        return Response(None)
    return Response(IdeaApplicationSerializer(app).data)


# ── Doctor reviews applications on their ideas ────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsDoctorOrHod])
def doctor_pending_applications(request):
    apps = get_pending_doctor_applications(request.user)[:MAX_LIST_RESPONSE_SIZE]
    return Response(IdeaApplicationSerializer(apps, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsDoctorOrHod])
def doctor_review_app(request, app_id):
    try:
        app = IdeaApplication.objects.get(pk=app_id, idea__doctor=request.user)
    except IdeaApplication.DoesNotExist:
        return Response({'error': 'Application not found.'}, status=404)

    serializer = ProposalReviewSerializer(data=request.data)
    if not serializer.is_valid():
        return _validation_error_response(serializer.errors)

    result = doctor_review_application(
        application=app,
        action=serializer.validated_data['action'],
        rejection_reason=serializer.validated_data.get('rejection_reason', ''),
    )
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    return Response(IdeaApplicationSerializer(result['application']).data)


# ── HoD reviews applications ──────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHod])
def hod_pending_applications(request):
    apps = get_pending_hod_applications(request.user.department)[:MAX_LIST_RESPONSE_SIZE]
    return Response(IdeaApplicationSerializer(apps, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHod])
def hod_review_app(request, app_id):
    try:
        app = IdeaApplication.objects.get(pk=app_id, idea__department=request.user.department)
    except IdeaApplication.DoesNotExist:
        return Response({'error': 'Application not found.'}, status=404)

    serializer = ProposalReviewSerializer(data=request.data)
    if not serializer.is_valid():
        return _validation_error_response(serializer.errors)

    result = hod_review_application(
        application=app,
        action=serializer.validated_data['action'],
        rejection_reason=serializer.validated_data.get('rejection_reason', ''),
    )
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    return Response(IdeaApplicationSerializer(result['application']).data)


# ── Team invitations ──────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudent])
def my_invitations(request):
    invitations = TeamInvitation.objects.filter(
        invitee=request.user, status='pending',
    ).select_related(
        'application__idea__doctor',
        'application__student',
    ).prefetch_related(
        'application__invitations__invitee',
    )
    return Response(TeamInvitationSerializer(invitations, many=True).data)



@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def respond_invitation(request, inv_id):
    try:
        inv = TeamInvitation.objects.get(pk=inv_id, invitee=request.user)
    except TeamInvitation.DoesNotExist:
        return Response({'error': 'Invitation not found.'}, status=404)

    action = request.data.get('action')
    if action not in ('accept', 'reject'):
        return Response({'error': 'action must be accept or reject.'}, status=400)

    result = respond_to_invitation(invitation=inv, action=action)
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    return Response(TeamInvitationSerializer(result['invitation']).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudent])
def my_proposal_invitations(request):
    """Pending invitations to join a student's own proposal team."""
    invitations = ProposalInvitation.objects.filter(
        invitee=request.user, status='pending',
    ).select_related('proposal__student')
    return Response(ProposalInvitationSerializer(invitations, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def respond_proposal_invitation(request, inv_id):
    try:
        inv = ProposalInvitation.objects.get(pk=inv_id, invitee=request.user)
    except ProposalInvitation.DoesNotExist:
        return Response({'error': 'Invitation not found.'}, status=404)

    action = request.data.get('action')
    if action not in ('accept', 'reject'):
        return Response({'error': 'action must be accept or reject.'}, status=400)

    result = respond_to_proposal_invitation(
        invitation=inv,
        action=action,
        rejection_reason=request.data.get('rejection_reason', ''),
    )
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    return Response(ProposalInvitationSerializer(result['invitation']).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def replace_proposal_member_view(request, proposal_id):
    try:
        proposal = StudentIdeaProposal.objects.get(pk=proposal_id, student=request.user)
    except StudentIdeaProposal.DoesNotExist:
        return Response({'error': 'Proposal not found.'}, status=404)

    old_id = request.data.get('old_member_id', '').strip()
    new_id = request.data.get('new_member_id', '').strip()
    if not old_id or not new_id:
        return Response({'error': 'old_member_id and new_member_id are required.'}, status=400)

    result = replace_proposal_member(proposal=proposal, old_member_id=old_id, new_member_id=new_id)
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    return Response({'message': 'Member replaced successfully.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def remove_rejected_proposal_member_view(request, proposal_id):
    try:
        proposal = StudentIdeaProposal.objects.get(pk=proposal_id, student=request.user)
    except StudentIdeaProposal.DoesNotExist:
        return Response({'error': 'Proposal not found.'}, status=404)

    member_id = str(request.data.get('member_id', '')).strip()
    if not member_id:
        return Response({'error': 'member_id is required.'}, status=400)

    result = remove_rejected_proposal_member(
        proposal=proposal,
        member_id=member_id,
        team_size_reason=request.data.get('team_size_reason', ''),
    )
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    return Response(StudentIdeaProposalSerializer(result['proposal']).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def replace_rejected_supervisor_view(request, proposal_id):
    try:
        proposal = StudentIdeaProposal.objects.get(pk=proposal_id, student=request.user)
    except StudentIdeaProposal.DoesNotExist:
        return Response({'error': 'Proposal not found.'}, status=404)

    old_supervisor_id = request.data.get('old_supervisor_id')
    new_supervisor_id = request.data.get('new_supervisor_id')
    try:
        new_supervisor = User.objects.get(pk=new_supervisor_id, role__in=['doctor', 'hod'])
    except (User.DoesNotExist, TypeError, ValueError):
        return Response({'error': 'A valid replacement supervisor is required.'}, status=400)

    result = replace_rejected_supervisor(
        proposal=proposal,
        old_supervisor_id=old_supervisor_id,
        new_supervisor=new_supervisor,
    )
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    return Response(StudentIdeaProposalSerializer(result['proposal']).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def continue_with_approved_supervisor_view(request, proposal_id):
    try:
        proposal = StudentIdeaProposal.objects.get(pk=proposal_id, student=request.user)
    except StudentIdeaProposal.DoesNotExist:
        return Response({'error': 'Proposal not found.'}, status=404)

    result = continue_with_approved_supervisor(
        proposal=proposal,
        approved_supervisor_id=request.data.get('approved_supervisor_id'),
    )
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    return Response(StudentIdeaProposalSerializer(result['proposal']).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def revise_student_proposal_view(request, proposal_id):
    try:
        proposal = StudentIdeaProposal.objects.get(pk=proposal_id, student=request.user)
    except StudentIdeaProposal.DoesNotExist:
        return Response({'error': 'Proposal not found.'}, status=404)

    result = revise_student_proposal(
        proposal=proposal,
        title=request.data.get('title', ''),
        description=request.data.get('description', ''),
    )
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    return Response(StudentIdeaProposalSerializer(result['proposal']).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def replace_application_member_view(request, app_id):
    try:
        application = IdeaApplication.objects.get(pk=app_id, student=request.user)
    except IdeaApplication.DoesNotExist:
        return Response({'error': 'Application not found.'}, status=404)

    old_id = request.data.get('old_member_id', '').strip()
    new_id = request.data.get('new_member_id', '').strip()
    if not old_id or not new_id:
        return Response({'error': 'old_member_id and new_member_id are required.'}, status=400)

    result = replace_application_member(application=application, old_member_id=old_id, new_member_id=new_id)
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    return Response({'message': 'Member replaced successfully.'})


def _status_management_queryset(params):
    qs = (
        ProjectParticipation.objects
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
        .distinct()
    )

    search = params.get('search', '').strip()
    if search:
        qs = qs.filter(
            Q(student__first_name__icontains=search)
            | Q(student__last_name__icontains=search)
            | Q(student__username__icontains=search)
            | Q(idea_application__idea__title__icontains=search)
            | Q(student_proposal__title__icontains=search)
        )

    university_id = params.get('university_id', '').strip()
    if university_id:
        qs = qs.filter(student__username__icontains=university_id)

    status_filter = params.get('status', '').strip()
    if status_filter in ('active', 'failed', 'withdrawn'):
        qs = qs.filter(status=status_filter)

    department = params.get('department', '').strip()
    if department:
        qs = qs.filter(
            Q(idea_application__idea__department=department)
            | Q(student_proposal__department=department)
        )

    project = params.get('project', '').strip()
    if project:
        qs = qs.filter(
            Q(idea_application__idea__title__icontains=project)
            | Q(student_proposal__title__icontains=project)
        )

    project_type = params.get('project_type', '').strip()
    if project_type:
        qs = qs.filter(
            Q(idea_application__project_type=project_type)
            | Q(student_proposal__project_type=project_type)
        )

    supervisor = params.get('supervisor', '').strip()
    if supervisor:
        qs = qs.filter(
            Q(idea_application__idea__doctor__username__icontains=supervisor)
            | Q(idea_application__idea__doctor__first_name__icontains=supervisor)
            | Q(idea_application__idea__doctor__last_name__icontains=supervisor)
            | Q(student_proposal__supervisor__username__icontains=supervisor)
            | Q(student_proposal__supervisor__first_name__icontains=supervisor)
            | Q(student_proposal__supervisor__last_name__icontains=supervisor)
        )

    project_source = params.get('project_source', '').strip()
    if project_source in ('idea_application', 'student_proposal'):
        qs = qs.filter(project_source=project_source)

    return qs.order_by('student__username', 'id')


def _project_alert(project, source):
    if source == 'idea_application':
        title = project.idea.title
        department = project.idea.department
        project_type = project.project_type or project.idea.project_type
    else:
        title = project.title
        department = project.department
        project_type = project.project_type
    return {
        'source': source,
        'id': project.id,
        'title': title,
        'department': department,
        'project_type': project_type,
        'operational_status': project.operational_status,
    }


def _status_management_stats(qs):
    idea_ids = list(qs.filter(idea_application__isnull=False).values_list('idea_application_id', flat=True).distinct())
    proposal_ids = list(qs.filter(student_proposal__isnull=False).values_list('student_proposal_id', flat=True).distinct())

    idea_projects = IdeaApplication.objects.filter(id__in=idea_ids, status='registered').select_related('idea')
    proposal_projects = StudentIdeaProposal.objects.filter(id__in=proposal_ids, status='assigned')
    all_projects = list(idea_projects) + list(proposal_projects)

    def project_count(status):
        return sum(1 for project in all_projects if project.operational_status == status)

    alerts = {
        'partial_projects': [_project_alert(project, 'idea_application') for project in idea_projects if project.operational_status == 'partial_team'],
        'solo_projects': (
            [_project_alert(project, 'idea_application') for project in idea_projects if project.operational_status == 'solo']
            + [_project_alert(project, 'student_proposal') for project in proposal_projects if project.operational_status == 'solo']
        ),
        'fully_withdrawn_projects': (
            [_project_alert(project, 'idea_application') for project in idea_projects if project.operational_status == 'fully_withdrawn']
            + [_project_alert(project, 'student_proposal') for project in proposal_projects if project.operational_status == 'fully_withdrawn']
        ),
        'fully_failed_projects': (
            [_project_alert(project, 'idea_application') for project in idea_projects if project.operational_status == 'fully_failed']
            + [_project_alert(project, 'student_proposal') for project in proposal_projects if project.operational_status == 'fully_failed']
        ),
        'inactive_projects': (
            [_project_alert(project, 'idea_application') for project in idea_projects if project.operational_status == 'inactive']
            + [_project_alert(project, 'student_proposal') for project in proposal_projects if project.operational_status == 'inactive']
        ),
    }
    alerts['partial_projects'].extend(
        [_project_alert(project, 'student_proposal') for project in proposal_projects if project.operational_status == 'partial_team']
    )

    return {
        'active_students': qs.filter(status='active').count(),
        'failed_students': qs.filter(status='failed').count(),
        'withdrawn_students': qs.filter(status='withdrawn').count(),
        'partial_projects': project_count('partial_team'),
        'solo_projects': project_count('solo'),
        'fully_withdrawn_projects': project_count('fully_withdrawn'),
        'fully_failed_projects': project_count('fully_failed'),
        'inactive_projects': project_count('inactive'),
        'alerts': alerts,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsDeanOrAdmin])
def student_status_management(request):
    qs = _status_management_queryset(request.query_params)
    rows = qs[:MAX_STATUS_MANAGEMENT_RESULTS]
    return Response({
        'results': ProjectParticipationManagementSerializer(rows, many=True).data,
        'count': qs.count(),
        'limit': MAX_STATUS_MANAGEMENT_RESULTS,
        'stats': _status_management_stats(qs),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsDeanOrAdmin])
def student_status_management_stats(request):
    qs = _status_management_queryset(request.query_params)
    return Response(_status_management_stats(qs))


def _status_change_response(request, participation_id, action):
    serializer = ProjectParticipationStatusChangeSerializer(data=request.data)
    if not serializer.is_valid():
        return _validation_error_response(serializer.errors)

    reason = serializer.validated_data.get('reason', '')
    notes = serializer.validated_data.get('notes', '')
    try:
        if action == 'failed':
            participation = StudentProjectStatusService.mark_as_failed(
                participation_id=participation_id,
                reason=reason,
                notes=notes,
                changed_by=request.user,
            )
        elif action == 'withdrawn':
            participation = StudentProjectStatusService.mark_as_withdrawn(
                participation_id=participation_id,
                reason=reason,
                notes=notes,
                changed_by=request.user,
            )
        else:
            participation = StudentProjectStatusService.reverse_to_active(
                participation_id=participation_id,
                reason=reason,
                notes=notes,
                changed_by=request.user,
            )
    except ProjectParticipation.DoesNotExist:
        return Response({'error': 'Participation not found.'}, status=404)
    except ParticipationStatusError as exc:
        return Response({'error': str(exc)}, status=400)

    return Response(ProjectParticipationManagementSerializer(participation).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsDeanOrAdmin])
def mark_participation_failed(request, participation_id):
    return _status_change_response(request, participation_id, 'failed')


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsDeanOrAdmin])
def mark_participation_withdrawn(request, participation_id):
    return _status_change_response(request, participation_id, 'withdrawn')


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsDeanOrAdmin])
def reverse_participation_to_active(request, participation_id):
    return _status_change_response(request, participation_id, 'active')


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsDeanOrAdmin])
def designate_student_status(request, student_id):
    serializer = ProjectParticipationStatusChangeSerializer(data=request.data)
    if not serializer.is_valid():
        return _validation_error_response(serializer.errors)
    status_value = request.data.get('status')
    if status_value not in ('failed', 'withdrawn', 'active'):
        return Response({'error': 'status must be active, failed, or withdrawn.'}, status=400)
    try:
        participation = resolve_registered_participation_for_student(student_id)
    except User.DoesNotExist:
        return Response({'error': 'Student not found.'}, status=404)
    except ParticipationStatusError as exc:
        return Response({'error': str(exc)}, status=400)
    return _status_change_response(request, participation.id, status_value)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def participation_history(request, participation_id):
    if request.user.role != 'dean':
        participation = ProjectParticipation.objects.filter(pk=participation_id, student=request.user).first()
        if not participation:
            return Response({'error': 'Forbidden'}, status=403)

    logs = (
        ProjectParticipationStatusLog.objects
        .filter(participation_id=participation_id)
        .select_related('student', 'changed_by', 'idea_application__idea', 'student_proposal')
    )
    return Response(ProjectParticipationStatusLogSerializer(logs, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_participation_history(request, student_id):
    if request.user.role != 'dean' and request.user.id != student_id:
        return Response({'error': 'Forbidden'}, status=403)

    logs = (
        ProjectParticipationStatusLog.objects
        .filter(student_id=student_id)
        .select_related('student', 'changed_by', 'idea_application__idea', 'student_proposal')
    )
    return Response(ProjectParticipationStatusLogSerializer(logs, many=True).data)
