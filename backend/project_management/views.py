from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import os

from django.db.models import Count, Q
from .models import ProjectBoard, Task, TaskComment, TaskAttachment, ActivityLog
from .serializers import (
    ProjectBoardSerializer, TaskSerializer,
    TaskCommentSerializer, TaskAttachmentSerializer, ActivityLogSerializer,
)
import mimetypes
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser

# ── Helpers ───────────────────────────────────────────────────────────────────

MAX_BOARD_LIST_SIZE = 100
MAX_COMMENT_LIST_SIZE = 100
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
ALLOWED_ATTACHMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.png', '.jpg', '.jpeg', '.gif', '.txt'}
MIME_WHITELIST = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'image/png',
    'image/jpeg',
    'image/gif',
    'text/plain',
}


def _get_student_board(student):
    from projects.models import ProjectParticipation, StudentIdeaProposal, IdeaApplication, ProposalInvitation, TeamInvitation

    participations = ProjectParticipation.objects.filter(
        student=student,
    ).filter(
        Q(idea_application__status='registered')
        | Q(student_proposal__status='assigned')
    ).select_related('idea_application__idea', 'student_proposal')
    if participations.exists():
        participation = participations.filter(status='active').first()
        if not participation:
            return None
        if participation.student_proposal_id:
            proposal = participation.student_proposal
            board, _ = ProjectBoard.objects.get_or_create(
                proposal=proposal,
                defaults={'title': proposal.title}
            )
            return board
        if participation.idea_application_id:
            application = participation.idea_application
            board_title = application.idea.title if application.idea_id else f'Project {application.id}'
            board, _ = ProjectBoard.objects.get_or_create(
                application=application,
                defaults={'title': board_title}
            )
            return board

    proposal = StudentIdeaProposal.objects.filter(student=student, status='assigned').first()
    if not proposal:
        inv = ProposalInvitation.objects.filter(
            invitee=student, status='accepted', proposal__status='assigned'
        ).select_related('proposal').first()
        if inv:
            proposal = inv.proposal

    if proposal:
        # Use get_or_create so the board is auto-created on first access
        board, _ = ProjectBoard.objects.get_or_create(
            proposal=proposal,
            defaults={'title': proposal.title}
        )
        return board

    application = IdeaApplication.objects.filter(student=student, status='registered').first()
    if not application:
        inv = TeamInvitation.objects.filter(
            invitee=student, status='accepted', application__status='registered'
        ).select_related('application').first()
        if inv:
            application = inv.application

    if application:
        # Use get_or_create so the board is auto-created on first access
        board_title = application.idea.title if application.idea_id else f'Project {application.id}'
        board, _ = ProjectBoard.objects.get_or_create(
            application=application,
            defaults={'title': board_title}
        )
        return board

    return None


def _board_detail_queryset():
    return ProjectBoard.objects.select_related(
        'proposal__supervisor',
        'proposal__student',
        'application__idea__doctor',
        'application__student',
    ).prefetch_related(
        'proposal__co_supervisors',
        'tasks__assignee',
        'tasks__created_by',
        'tasks__comments__author',
        'tasks__attachments__uploaded_by',
    )


def _is_board_member(board, user):
    """M-06 Fix: فحص عضوية مباشر بدون تحميل كل الأعضاء"""
    from projects.participation_services import get_project_participations

    project = board.proposal or board.application
    if project:
        participations = list(get_project_participations(project))
        if participations:
            return any(p.student_id == user.id and p.status == 'active' for p in participations)

    from projects.models import ProposalInvitation, TeamInvitation
    if board.proposal:
        if board.proposal.student_id == user.id:
            return True
        return ProposalInvitation.objects.filter(
            proposal=board.proposal, status='accepted', invitee_id=user.id
        ).exists()
    elif board.application:
        if board.application.student_id == user.id:
            return True
        return TeamInvitation.objects.filter(
            application=board.application, status='accepted', invitee_id=user.id
        ).exists()
    return False


def _get_board_for_member(user, board_id):
    try:
        board = ProjectBoard.objects.select_related(
            'proposal__supervisor',
            'proposal__student',
            'application__idea__doctor',
            'application__student',
        ).get(pk=board_id)
    except ProjectBoard.DoesNotExist:
        return None

    if user.role == 'student' and _is_board_member(board, user):
        return board

    if user.role in ['doctor', 'hod']:
        if board.proposal and board.proposal.supervisor_id == user.id:
            return board
        if board.proposal and board.proposal.co_supervisors.filter(pk=user.pk).exists():
            return board
        if board.application and board.application.idea.doctor_id == user.id:
            return board

    return None


def _log(board, actor, verb, detail='', task=None):
    ActivityLog.objects.create(board=board, actor=actor, verb=verb, detail=detail, task=task)


# ── Board ─────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_board(request):
    if request.user.role != 'student':
        return Response({'error': 'Students only.'}, status=403)
    board = _get_student_board(request.user)
    if not board:
        return Response({'has_project': False})
    board = _board_detail_queryset().get(pk=board.pk)
    return Response({'has_project': True, 'board': ProjectBoardSerializer(board).data})


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_board(request, board_id):
    if request.user.role != 'student':
        return Response({'error': 'Only students can update board info.'}, status=403)
        
    board = _get_board_for_member(request.user, board_id)
    if not board:
        return Response({'error': 'Not found or not a member.'}, status=404)
        
    if 'github_repo' in request.data:
        board.github_repo = request.data['github_repo']
        board.save()
        
    return Response(ProjectBoardSerializer(board).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def supervisor_boards(request):
    if request.user.role not in ['doctor', 'hod']:
        return Response({'error': 'Doctors or HoD only.'}, status=403)

    from projects.models import StudentIdeaProposal, IdeaApplication
    boards = []
    active_project_statuses = ['active', 'partial_team', 'solo']

    proposals = StudentIdeaProposal.objects.filter(
        Q(supervisor=request.user) | Q(co_supervisors=request.user),
        status='assigned',
        operational_status__in=active_project_statuses,
    ).distinct()
    for proposal in proposals[:MAX_BOARD_LIST_SIZE]:
        board, _ = ProjectBoard.objects.get_or_create(
            proposal=proposal, defaults={'title': proposal.title}
        )
        boards.append(board)

    for application in IdeaApplication.objects.filter(
        idea__doctor=request.user, status='registered'
    ).select_related('idea')[:MAX_BOARD_LIST_SIZE]:
        if len(boards) >= MAX_BOARD_LIST_SIZE:
            break
        board, _ = ProjectBoard.objects.get_or_create(
            application=application, defaults={'title': application.idea.title}
        )
        boards.append(board)

    boards = _board_detail_queryset().filter(pk__in=[board.pk for board in boards])
    return Response(ProjectBoardSerializer(boards, many=True, context={'request': request}).data)


# ── Tasks ─────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_task(request, board_id):
    board = _get_board_for_member(request.user, board_id)
    if not board:
        return Response({'error': 'Not found or not a member.'}, status=404)

    serializer = TaskSerializer(data=request.data, context={'board': board})
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    task = serializer.save(board=board, created_by=request.user)
    _log(board, request.user, 'created', task.title, task=task)
    return Response(TaskSerializer(task).data, status=201)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_task(request, board_id, task_id):
    board = _get_board_for_member(request.user, board_id)
    if not board:
        return Response({'error': 'Not found or not a member.'}, status=404)

    try:
        task = board.tasks.get(pk=task_id)
    except Task.DoesNotExist:
        return Response({'error': 'Task not found.'}, status=404)

    old_status   = task.status
    old_priority = task.priority
    old_assignee = task.assignee_id

    serializer = TaskSerializer(task, data=request.data, partial=True, context={'board': board})
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    serializer.save()
    task.refresh_from_db()

    if 'status' in request.data and task.status != old_status:
        _log(board, request.user, 'status_changed',
             f'{old_status} → {task.status}', task=task)
    if 'priority' in request.data and task.priority != old_priority:
        _log(board, request.user, 'priority_changed',
             f'{old_priority} → {task.priority}', task=task)
    if 'assignee' in request.data and task.assignee_id != old_assignee:
        verb   = 'assigned' if task.assignee_id else 'unassigned'
        detail = task.assignee.get_full_name() or task.assignee.username if task.assignee else ''
        _log(board, request.user, verb, detail, task=task)
    if 'due_date' in request.data:
        _log(board, request.user, 'due_date_set', str(task.due_date or ''), task=task)

    return Response(TaskSerializer(task).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_task(request, board_id, task_id):
    board = _get_board_for_member(request.user, board_id)
    if not board:
        return Response({'error': 'Not found or not a member.'}, status=404)

    try:
        task = board.tasks.get(pk=task_id)
    except Task.DoesNotExist:
        return Response({'error': 'Task not found.'}, status=404)

    _log(board, request.user, 'deleted', task.title)
    task.delete()
    return Response(status=204)


# ── Comments ──────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def task_comments(request, board_id, task_id):
    board = _get_board_for_member(request.user, board_id)
    if not board:
        return Response({'error': 'Not found or not a member.'}, status=404)

    try:
        task = board.tasks.get(pk=task_id)
    except Task.DoesNotExist:
        return Response({'error': 'Task not found.'}, status=404)

    if request.method == 'GET':
        comments = task.comments.select_related('author')[:MAX_COMMENT_LIST_SIZE]
        return Response(TaskCommentSerializer(comments, many=True).data)

    serializer = TaskCommentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    comment = serializer.save(task=task, author=request.user)
    _log(board, request.user, 'commented', comment.body[:100], task=task)
    return Response(TaskCommentSerializer(comment).data, status=201)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_comment(request, board_id, task_id, comment_id):
    board = _get_board_for_member(request.user, board_id)
    if not board:
        return Response({'error': 'Not found or not a member.'}, status=404)

    try:
        comment = TaskComment.objects.get(pk=comment_id, task__board=board, task_id=task_id)
    except TaskComment.DoesNotExist:
        return Response({'error': 'Comment not found.'}, status=404)

    if comment.author_id != request.user.id and request.user.role not in ['doctor', 'hod']:
        return Response({'error': 'Not allowed.'}, status=403)

    comment.delete()
    return Response(status=204)


# ── Attachments ───────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_attachment(request, board_id, task_id):

    board = _get_board_for_member(request.user, board_id)
    if not board:
        return Response({'error': 'Not found or not a member.'}, status=404)

    try:
        task = board.tasks.get(pk=task_id)
    except Task.DoesNotExist:
        return Response({'error': 'Task not found.'}, status=404)

    file = request.FILES.get('file')
    if not file:
        return Response({'error': 'No file provided.'}, status=400)

    if file.size > MAX_ATTACHMENT_SIZE:
        return Response({'error': 'File too large. Max 10 MB.'}, status=400)
    extension = os.path.splitext(file.name or '')[1].lower()
    if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
        return Response({'error': 'Unsupported file type.'}, status=400)
    mime_type, _ = mimetypes.guess_type(file.name or '')
    content_type = file.content_type if hasattr(file, 'content_type') else mime_type
    if content_type and content_type not in MIME_WHITELIST:
        return Response({'error': 'Unsupported file type (MIME mismatch).'}, status=400)
    attachment = TaskAttachment.objects.create(
        task=task,
        uploaded_by=request.user,
        file=file,
        filename=file.name,
        file_size=file.size,
    )
    _log(board, request.user, 'attachment_added', file.name, task=task)
    return Response(
        TaskAttachmentSerializer(attachment, context={'request': request}).data,
        status=201,
    )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_attachment(request, board_id, task_id, attachment_id):
    board = _get_board_for_member(request.user, board_id)
    if not board:
        return Response({'error': 'Not found or not a member.'}, status=404)

    try:
        attachment = TaskAttachment.objects.get(
            pk=attachment_id, task__board=board, task_id=task_id
        )
    except TaskAttachment.DoesNotExist:
        return Response({'error': 'Attachment not found.'}, status=404)

    if attachment.uploaded_by_id != request.user.id and request.user.role == 'student':
        return Response({'error': 'Not allowed.'}, status=403)

    _log(board, request.user, 'attachment_removed', attachment.filename, task=attachment.task)
    attachment.file.delete(save=False)
    attachment.delete()
    return Response(status=204)


# ── Activity Log ──────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def board_activity(request, board_id):
    board = _get_board_for_member(request.user, board_id)
    if not board:
        return Response({'error': 'Not found or not a member.'}, status=404)

    logs = board.activities.select_related('actor', 'task')[:50]
    return Response(ActivityLogSerializer(logs, many=True).data)


# ── HoD & Dean ────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hod_boards(request):
    """HoD view: all boards in their department (read-only)."""
    if request.user.role not in ['hod', 'dean']:
        return Response({'error': 'HoD or Dean only.'}, status=403)

    from projects.models import StudentIdeaProposal, IdeaApplication

    boards = []
    department = request.user.department
    active_project_statuses = ['active', 'partial_team', 'solo']

    if request.user.role == 'hod':
        proposals = StudentIdeaProposal.objects.filter(
            department=department, status='assigned', operational_status__in=active_project_statuses
        ).select_related('supervisor')
        applications = IdeaApplication.objects.filter(
            idea__department=department, status='registered', operational_status__in=active_project_statuses
        ).select_related('idea__doctor')
    else:
        proposals = StudentIdeaProposal.objects.filter(status='assigned', operational_status__in=active_project_statuses).select_related('supervisor')
        applications = IdeaApplication.objects.filter(status='registered', operational_status__in=active_project_statuses).select_related('idea__doctor')

    for proposal in proposals[:MAX_BOARD_LIST_SIZE]:
        board, _ = ProjectBoard.objects.get_or_create(
            proposal=proposal, defaults={'title': proposal.title}
        )
        boards.append(board)

    for application in applications[:MAX_BOARD_LIST_SIZE]:
        if len(boards) >= MAX_BOARD_LIST_SIZE:
            break
        board, _ = ProjectBoard.objects.get_or_create(
            application=application, defaults={'title': application.idea.title}
        )
        boards.append(board)

    boards = _board_detail_queryset().filter(pk__in=[board.pk for board in boards])
    return Response(ProjectBoardSerializer(boards, many=True, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hod_stats(request):
    """HoD/Dean dashboard statistics."""
    if request.user.role not in ['hod', 'dean']:
        return Response({'error': 'HoD or Dean only.'}, status=403)

    from projects.models import StudentIdeaProposal, IdeaApplication

    department = request.user.department
    active_project_statuses = ['active', 'partial_team', 'solo']

    if request.user.role == 'hod':
        proposals_count = StudentIdeaProposal.objects.filter(
            department=department, status='assigned', operational_status__in=active_project_statuses
        ).count()
        applications_count = IdeaApplication.objects.filter(
            idea__department=department, status='registered', operational_status__in=active_project_statuses
        ).count()
    else:
        proposals_count = StudentIdeaProposal.objects.filter(status='assigned', operational_status__in=active_project_statuses).count()
        applications_count = IdeaApplication.objects.filter(status='registered', operational_status__in=active_project_statuses).count()

    total_projects = proposals_count + applications_count

    if request.user.role == 'hod':
        boards_qs = ProjectBoard.objects.filter(
            Q(proposal__department=department, proposal__status='assigned', proposal__operational_status__in=active_project_statuses) |
            Q(application__idea__department=department, application__status='registered', application__operational_status__in=active_project_statuses)
        )
    else:
        boards_qs = ProjectBoard.objects.filter(
            Q(proposal__status='assigned', proposal__operational_status__in=active_project_statuses)
            | Q(application__status='registered', application__operational_status__in=active_project_statuses)
        )

    total_progress = 0
    board_count = 0

    for board in boards_qs.annotate(
        total_tasks=Count('tasks'),
        done_tasks=Count('tasks', filter=Q(tasks__status='done')),
    ):
        if board.total_tasks:
            total_progress += (board.done_tasks / board.total_tasks) * 100
            board_count += 1

    avg_progress = round(total_progress / board_count) if board_count > 0 else 0

    return Response({
        'total_projects': total_projects,
        'proposals_count': proposals_count,
        'applications_count': applications_count,
        'avg_progress': avg_progress,
        'department': department if request.user.role == 'hod' else 'All Departments',
    })
