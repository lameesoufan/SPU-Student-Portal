import json
import mimetypes
import os

from django.db import transaction
from django.http import FileResponse
from rest_framework.decorators import api_view, parser_classes, permission_classes, throttle_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.throttles import FileUploadThrottle

from .models import DynamicForm, FieldResponse, FormField, FormResponse
from .permissions import IsHod, IsStudent
from .serializers import DynamicFormSerializer, FormResponseSerializer
from .validators import validate_context, validate_form_fields


MAX_FORM_FILE_SIZE = 10 * 1024 * 1024   # 10 MB per file
MAX_FORM_UPLOAD_TOTAL_SIZE = 25 * 1024 * 1024
MAX_FORM_UPLOAD_COUNT = 10
MAX_RESPONSE_LIST_SIZE = 500

FORM_MIME_BY_EXTENSION = {
    '.pdf': {'application/pdf'},
    '.doc': {'application/msword'},
    '.docx': {'application/vnd.openxmlformats-officedocument.wordprocessingml.document'},
    '.xls': {'application/vnd.ms-excel'},
    '.xlsx': {'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'},
    '.ppt': {'application/vnd.ms-powerpoint'},
    '.pptx': {'application/vnd.openxmlformats-officedocument.presentationml.presentation'},
    '.txt': {'text/plain'},
    '.csv': {'text/csv', 'application/csv', 'application/vnd.ms-excel'},
    '.jpg': {'image/jpeg'},
    '.jpeg': {'image/jpeg'},
    '.png': {'image/png'},
    '.gif': {'image/gif'},
    '.zip': {'application/zip', 'application/x-zip-compressed'},
    '.rar': {'application/vnd.rar', 'application/x-rar-compressed'},
}
ALLOWED_FORM_FILE_EXTENSIONS = set(FORM_MIME_BY_EXTENSION)


def _validate_form_file(file):
    """Validate upload size and require the declared MIME to match the extension."""
    if file.size > MAX_FORM_FILE_SIZE:
        raise ValueError(f'File too large. Max {MAX_FORM_FILE_SIZE // (1024 * 1024)} MB.')

    extension = os.path.splitext(file.name or '')[1].lower()
    allowed_mimes = FORM_MIME_BY_EXTENSION.get(extension)
    if not allowed_mimes:
        raise ValueError(f'Unsupported file type: {extension}')

    guessed_mime, _ = mimetypes.guess_type(file.name or '')
    content_type = (getattr(file, 'content_type', None) or guessed_mime or '').split(';', 1)[0].strip().lower()
    if not content_type or content_type not in allowed_mimes:
        raise ValueError('Unsupported file type (MIME mismatch).')


def _validation_error(error):
    return Response({'error': 'Validation failed.', 'details': error}, status=400)


def _empty_form_response():
    return Response({'id': None, 'title': '', 'description': '', 'fields': []})


def _private_response(data, *, status=200):
    response = Response(data, status=status)
    response['Cache-Control'] = 'private, no-store'
    response['Pragma'] = 'no-cache'
    return response


def _can_access_response(user, response):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.role == 'hod' and response.form.department == user.department:
        return True
    if user.role == 'student' and response.student_id == user.id:
        return True
    if user.role == 'doctor':
        try:
            from project_management.models import ProjectBoard
            from projects.models import IdeaApplication, StudentIdeaProposal

            if response.proposal_id and StudentIdeaProposal.objects.filter(
                pk=response.proposal_id,
            ).filter(
                supervisor=user,
            ).exists():
                return True
            if response.proposal_id and StudentIdeaProposal.objects.filter(
                pk=response.proposal_id,
                co_supervisors=user,
            ).exists():
                return True
            if response.application_id and IdeaApplication.objects.filter(
                pk=response.application_id,
                idea__doctor=user,
            ).exists():
                return True
            if response.project_board_id:
                board = ProjectBoard.objects.filter(pk=response.project_board_id).select_related(
                    'proposal', 'application__idea'
                ).first()
                if board and board.proposal_id:
                    if board.proposal.supervisor_id == user.id or board.proposal.co_supervisors.filter(pk=user.id).exists():
                        return True
                if board and board.application_id and board.application.idea.doctor_id == user.id:
                    return True
        except Exception:
            return False
    return False


def _legacy_project_member(user, project):
    """Backward-compatible membership for projects created before participation rows."""
    from projects.models import IdeaApplication, StudentIdeaProposal

    if isinstance(project, StudentIdeaProposal):
        return project.student_id == user.id or project.invitations.filter(
            invitee_id=user.id,
            status='accepted',
        ).exists()
    if isinstance(project, IdeaApplication):
        return project.student_id == user.id or project.invitations.filter(
            invitee_id=user.id,
            status='accepted',
        ).exists()
    return False


def _student_can_submit_linked_project_form(user, validated_data):
    """Fail closed unless the student belongs to the exact linked project."""
    from project_management.models import ProjectBoard
    from projects.models import IdeaApplication, StudentIdeaProposal
    from projects.participation_services import get_project_participations

    proposal_id = validated_data.get('proposal_id')
    application_id = validated_data.get('application_id')
    project_board_id = validated_data.get('project_board_id')
    supplied_links = [value for value in (proposal_id, application_id, project_board_id) if value is not None]
    if len(supplied_links) != 1:
        return False

    project = None
    if proposal_id is not None:
        project = StudentIdeaProposal.objects.filter(pk=proposal_id).first()
    elif application_id is not None:
        project = IdeaApplication.objects.filter(pk=application_id).select_related('idea').first()
    elif project_board_id is not None:
        board = ProjectBoard.objects.filter(pk=project_board_id).select_related(
            'proposal', 'application__idea'
        ).first()
        if board:
            project = board.proposal or board.application

    if project is None:
        return False
    if isinstance(project, StudentIdeaProposal) and project.status == 'rejected':
        return False
    if isinstance(project, IdeaApplication) and project.status in {'rejected', 'rejected_insufficient_members'}:
        return False

    form = validated_data.get('form')
    if form is not None:
        project_department = project.department if isinstance(project, StudentIdeaProposal) else project.idea.department
        if form.department != project_department:
            return False

    participations = list(get_project_participations(project))
    if participations:
        return any(
            participation.student_id == user.id and participation.status == 'active'
            for participation in participations
        )
    return _legacy_project_member(user, project)


# -- HoD: save/update form for their department --------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHod])
def hod_get_form(request, context):
    """GET the HoD's form for a given context."""
    try:
        validate_context(context)
    except Exception as exc:
        return _validation_error({'context': exc.detail if hasattr(exc, 'detail') else str(exc)})

    form = DynamicForm.objects.filter(
        department=request.user.department, context=context
    ).prefetch_related('fields').first()
    if not form:
        return _empty_form_response()
    return Response(DynamicFormSerializer(form).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHod])
def hod_save_form(request, context):
    """POST to create/replace the HoD's form fields for a given context."""
    try:
        validate_context(context)
        fields_data = validate_form_fields(request.data.get('fields', []))
    except Exception as exc:
        return _validation_error(exc.detail if hasattr(exc, 'detail') else str(exc))

    title = request.data.get('title', '')
    description = request.data.get('description', '')

    with transaction.atomic():
        form, _ = DynamicForm.objects.get_or_create(
            department=request.user.department,
            context=context,
            defaults={
                'hod': request.user,
                'title': title,
                'description': description,
            },
        )
        form.title = title
        form.description = description
        form.hod = request.user
        form.save()

        form.fields.all().delete()
        for idx, field_data in enumerate(fields_data):
            FormField.objects.create(
                form=form,
                label=field_data['label'],
                field_type=field_data['field_type'],
                required=field_data['required'],
                options=field_data['options'],
                order=idx,
            )

    return Response(DynamicFormSerializer(
        DynamicForm.objects.prefetch_related('fields').get(pk=form.pk)
    ).data)


# -- Student: fetch form for a department + context ----------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_get_form(request, department, context):
    """GET the dynamic form for a department+context."""
    try:
        validate_context(context)
    except Exception as exc:
        return _validation_error({'context': exc.detail if hasattr(exc, 'detail') else str(exc)})

    form = DynamicForm.objects.filter(
        department=department, context=context
    ).prefetch_related('fields').first()
    if not form:
        return _empty_form_response()
    return Response(DynamicFormSerializer(form).data)


# -- Student: submit form response ---------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
@parser_classes([MultiPartParser, FormParser, JSONParser])
@throttle_classes([FileUploadThrottle])
def submit_form_response(request):
    """POST a student's filled form response."""
    files = list(request.FILES.items())
    if len(files) > MAX_FORM_UPLOAD_COUNT:
        return _validation_error({'files': f'Too many uploaded files. Max {MAX_FORM_UPLOAD_COUNT}.'})
    if sum(file.size for _, file in files) > MAX_FORM_UPLOAD_TOTAL_SIZE:
        return _validation_error({
            'files': f'Total upload size is too large. Max {MAX_FORM_UPLOAD_TOTAL_SIZE // (1024 * 1024)} MB.'
        })
    for key, file in files:
        try:
            _validate_form_file(file)
        except ValueError as exc:
            return _validation_error({key: str(exc)})

    data = request.data
    # In multipart/form-data, field_responses arrives as a JSON string.
    if isinstance(data.get('field_responses'), str):
        try:
            parsed_field_responses = json.loads(data.get('field_responses'))
            if not isinstance(parsed_field_responses, list):
                return _validation_error({'field_responses': 'Field responses must be a list.'})
            if hasattr(data, 'dict'):
                data = data.dict()
            else:
                data = dict(data)
            data['field_responses'] = parsed_field_responses
        except (json.JSONDecodeError, ValueError, TypeError):
            return _validation_error({'field_responses': 'Invalid JSON.'})

    serializer = FormResponseSerializer(data=data, context={'request': request})
    if not serializer.is_valid():
        return _validation_error(serializer.errors)

    form = serializer.validated_data['form']
    allowed_file_keys = {
        f'field_file_{field_id}'
        for field_id in form.fields.filter(field_type='file').values_list('id', flat=True)
    }
    unexpected_file_keys = sorted(set(request.FILES.keys()) - allowed_file_keys)
    if unexpected_file_keys:
        return _validation_error({'files': 'Unexpected upload field.'})

    if not _student_can_submit_linked_project_form(request.user, serializer.validated_data):
        return Response({'error': 'You are not an active participant in this project.'}, status=403)

    response = serializer.save(student=request.user)
    return _private_response(
        FormResponseSerializer(response, context={'request': request}).data,
        status=201,
    )


# -- Retrieve responses --------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHod])
def hod_list_responses(request, context):
    """GET all form responses for the HoD's department + context."""
    try:
        validate_context(context)
    except Exception as exc:
        return _validation_error({'context': exc.detail if hasattr(exc, 'detail') else str(exc)})

    responses = FormResponse.objects.filter(
        form__department=request.user.department,
        form__context=context,
    ).select_related('student', 'form').prefetch_related('field_responses__field')[:MAX_RESPONSE_LIST_SIZE]
    return _private_response(FormResponseSerializer(
        responses,
        many=True,
        context={'request': request},
    ).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_response_by_proposal(request, proposal_id):
    """GET the form response linked to a specific proposal."""
    resp = FormResponse.objects.select_related('form', 'student').prefetch_related(
        'field_responses__field'
    ).filter(proposal_id=proposal_id).order_by('-submitted_at').first()
    if not resp or not _can_access_response(request.user, resp):
        return Response({'detail': 'Not found.'}, status=404)
    return _private_response(FormResponseSerializer(resp, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_response_by_application(request, application_id):
    """GET the form response linked to a specific idea application."""
    resp = FormResponse.objects.select_related('form', 'student').prefetch_related(
        'field_responses__field'
    ).filter(application_id=application_id).order_by('-submitted_at').first()
    if not resp or not _can_access_response(request.user, resp):
        return Response({'detail': 'Not found.'}, status=404)
    return _private_response(FormResponseSerializer(resp, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_field_response_file(request, field_response_id):
    """Download a submitted form file only when the response itself is accessible."""
    answer = FieldResponse.objects.select_related('response__form', 'response__student').filter(
        pk=field_response_id,
    ).first()
    if not answer or not answer.file or not _can_access_response(request.user, answer.response):
        return Response({'detail': 'Not found.'}, status=404)

    try:
        file_handle = answer.file.open('rb')
    except (FileNotFoundError, OSError, ValueError):
        return Response({'detail': 'Not found.'}, status=404)

    filename = os.path.basename(answer.file.name)
    content_type, _ = mimetypes.guess_type(filename)
    response = FileResponse(
        file_handle,
        as_attachment=True,
        filename=filename,
        content_type=content_type or 'application/octet-stream',
    )
    response['Cache-Control'] = 'private, no-store'
    response['Pragma'] = 'no-cache'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
